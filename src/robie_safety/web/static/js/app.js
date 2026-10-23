import { RosBridge, yawFromQuaternion } from './ros_bridge.js';
import { CONFIG, sendStop, sendReset, publishGoal, holdButton } from './common.js';
import { SlamMap } from './slam_map.js';
import { CadViewer } from './cad_viewer.js';

const $ = (s) => document.querySelector(s);
const state = { mode: 'auto', motor: null, safety: {}, lastPoseAt: 0, lastMapAt: 0, gas: {}, stopLatched: false };

// ---------------------------------------------------------------------------
// ROS connection
// ---------------------------------------------------------------------------
const ros = new RosBridge(CONFIG.rosbridgeUrl);
ros.addEventListener('state', (e) => {
  const { state: s, detail } = e.detail;
  setLink('ros', s === 'connected' ? 'ok' : s === 'connecting' ? 'wait' : 'bad',
    s === 'connected' ? 'ROS connected' : s === 'connecting' ? 'Connecting to ROS…' : `ROS offline${detail ? ` (${detail})` : ''}`);
  $('#reconnect').hidden = s === 'connected' || s === 'connecting';
  if (s !== 'connected') stopTeleop();
});
$('#reconnect').addEventListener('click', () => ros.reconnect());

// ---------------------------------------------------------------------------
// Map, pose, 3D
// ---------------------------------------------------------------------------
const slam = new SlamMap($('#map-canvas'));
const viewer = new CadViewer($('#cad-view'), { onStatus: (t) => { $('#cad-note').textContent = t; } });

ros.subscribe(...CONFIG.topics.map, (msg) => {
  slam.setMap(msg);
  viewer.updateMap(slam);
  state.lastMapAt = performance.now();
  $('#map-empty').hidden = true;
  $('#map-meta').textContent = `${msg.info.width} × ${msg.info.height} cells, ${(msg.info.resolution * 100).toFixed(0)} cm each`;
}, { throttle_rate: 1000, queue_length: 1 });

ros.subscribe(...CONFIG.topics.pose, (msg) => {
  const p = msg.pose.position, yaw = yawFromQuaternion(msg.pose.orientation);
  slam.setPose(p.x, p.y, yaw);
  viewer.setPose(p.x, p.y, yaw);
  state.lastPoseAt = performance.now();
  $('#pose-readout').textContent = `x ${p.x.toFixed(2)} m   y ${p.y.toFixed(2)} m   heading ${(yaw * 180 / Math.PI).toFixed(0)}°`;
}, { throttle_rate: 50, queue_length: 1 });      // up to 20 Hz

slam.addEventListener('goal', (e) => {
  const g = e.detail;
  if (!publishGoal(ros, g.x, g.y, slam.pose)) { toast('Goal not sent: ROS is offline.', 'bad'); return; }
  slam.setGoal(g);
  logEvent('nav', `Goal sent to x ${g.x.toFixed(2)}, y ${g.y.toFixed(2)} m${g.unknown ? ' (unexplored area)' : ''}`);
});
// Show goals from anywhere (this page, the 3D view, RViz): the goal topic is the single source of truth.
ros.subscribe(...CONFIG.topics.goal, (msg) => {
  const p = msg.pose.position;
  slam.setGoal({ x: p.x, y: p.y });
}, { queue_length: 1 });
slam.addEventListener('rejected', (e) => toast(e.detail, 'warn'));

$('#map-fit').addEventListener('click', () => slam.fit());
$('#map-follow').addEventListener('change', (e) => { slam.followRobot = e.target.checked; });
$('#cad-follow').addEventListener('change', (e) => viewer.setFollow(e.target.checked));

// ---------------------------------------------------------------------------
// STOP / RESET
// Stop path 1: POST straight to safety_node (no-cors "simple request": no preflight, fastest).
// Stop path 2: same-origin proxy /api/estop on this server.
// Stop path 3: publish motor_enable=false over rosbridge.
// Reset only ever goes through safety_node, never through a topic.
// ---------------------------------------------------------------------------
async function triggerStop(source = 'button') {
  stopTeleop();
  $('#stop-btn').classList.add('is-firing');
  const { path, ms } = await sendStop(ros);
  $('#stop-btn').classList.remove('is-firing');
  if (path) {
    state.stopLatched = true;
    $('#stop-result').textContent = `Stop sent via ${path} in ${ms} ms.`;
    logEvent('safety', `Stop sent from dashboard (${source}) via ${path}, ${ms} ms`);
  } else {
    $('#stop-result').textContent = 'Stop could not reach the robot. Check the Wi-Fi link and cut power if it is still moving.';
    logEvent('safety', 'Stop FAILED: no path to the robot');
    toast('Stop could not reach the robot.', 'bad');
  }
  renderSafety();
}

$('#stop-btn').addEventListener('click', () => triggerStop('button'));
window.addEventListener('keydown', (e) => {
  if (e.target.matches('input, textarea, select')) return;
  if (e.code === 'Space' || e.code === 'Escape') { e.preventDefault(); triggerStop(e.code === 'Space' ? 'space bar' : 'Esc key'); }
});

// Reset needs a 1 s press-and-hold so it can't be clicked by accident.
holdButton($('#reset-btn'), 1000, async () => {
  if (await sendReset()) { state.stopLatched = false; $('#stop-result').textContent = 'Reset sent. Motors re-enable when the safety node confirms.'; logEvent('safety', 'Reset sent from dashboard'); }
  else { $('#stop-result').textContent = 'Reset could not reach the safety node.'; toast('Reset failed: safety node unreachable.', 'bad'); }
});

// ---------------------------------------------------------------------------
// Safety state "wd=1 web=0 estop=0 bf=0 br=0"
// ---------------------------------------------------------------------------
const SAFETY_ROWS = [
  ['wd', 'Watchdog', (v) => v === '1' ? ['ok', 'Healthy'] : ['bad', 'Tripped']],
  ['web', 'Dashboard stop', (v) => v === '1' ? ['bad', 'Latched'] : ['ok', 'Clear']],
  ['estop', 'Hardware stop', (v) => v === '1' ? ['bad', 'Pressed'] : ['ok', 'Clear']],
  ['bf', 'Front bumper', (v) => v === '1' ? ['bad', 'Contact'] : ['ok', 'Clear']],
  ['br', 'Rear bumper', (v) => v === '1' ? ['bad', 'Contact'] : ['ok', 'Clear']],
];
ros.subscribe(...CONFIG.topics.safety, (msg) => {
  const next = Object.fromEntries(String(msg.data).trim().split(/\s+/).map((kv) => kv.split('=')));
  for (const [k, label, fn] of SAFETY_ROWS) {
    if (state.safety[k] !== undefined && next[k] !== undefined && state.safety[k] !== next[k]) {
      logEvent('safety', `${label}: ${fn(next[k])[1].toLowerCase()}`);
    }
  }
  state.safety = next; state.safetyAt = performance.now();
  if (next.web === '0') state.stopLatched = false;
  renderSafety();
});

function renderSafety() {
  const box = $('#safety-list'); box.innerHTML = '';
  const fresh = state.safetyAt && performance.now() - state.safetyAt < 3000;
  for (const [k, label, fn] of SAFETY_ROWS) {
    const v = state.safety[k];
    const [cls, text] = v === undefined || !fresh ? ['unknown', 'No data'] : fn(v);
    const li = document.createElement('li');
    li.innerHTML = `<span class="dot ${cls}"></span><span>${label}</span><span class="val">${text}</span>`;
    box.appendChild(li);
  }
}
setInterval(renderSafety, 1000);
renderSafety();

ros.subscribe(...CONFIG.topics.motor, (msg) => {
  if (state.motor !== null && state.motor !== msg.data) logEvent('safety', `Motors ${msg.data ? 'enabled' : 'disabled'}`);
  state.motor = msg.data;
  const el = $('#motor-state');
  el.textContent = msg.data ? 'Enabled' : 'Disabled';
  el.dataset.state = msg.data ? 'ok' : 'bad';
});

ros.subscribe(...CONFIG.topics.battery, (msg) => {
  $('#battery').textContent = `${Number(msg.data).toFixed(2)} V`;
}, { throttle_rate: 1000 });

// ---------------------------------------------------------------------------
// Events: "C,conf,x,y" crack, "G,ppm" or "G,mq4,mq6" gas
// ---------------------------------------------------------------------------
ros.subscribe(...CONFIG.topics.event, (msg) => {
  const parts = String(msg.data).split(',').map((s) => s.trim());
  const kind = parts[0]?.toUpperCase();
  if (kind === 'C') {
    const conf = parseFloat(parts[1]), x = parseFloat(parts[2]), y = parseFloat(parts[3]);
    logEvent('crack', `Crack detected, ${(conf * (conf <= 1 ? 100 : 1)).toFixed(0)}% confidence at (${parts[2]}, ${parts[3]})`);
    showCrack(conf, x, y);
  } else if (kind === 'G') {
    if (parts.length >= 3) { state.gas.mq4 = parseFloat(parts[1]); state.gas.mq6 = parseFloat(parts[2]); }
    else { state.gas.single = parseFloat(parts[1]); }
    state.gas.at = Date.now();
    renderGas();
    logEvent('gas', parts.length >= 3 ? `Gas: MQ-4 ${parts[1]} ppm, MQ-6 ${parts[2]} ppm` : `Gas reading ${parts[1]} ppm`);
  } else {
    logEvent('info', String(msg.data));
  }
});

function renderGas() {
  const g = state.gas;
  $('#gas-mq4').textContent = Number.isFinite(g.mq4) ? `${g.mq4.toFixed(0)} ppm` : (Number.isFinite(g.single) ? `${g.single.toFixed(0)} ppm` : 'No data');
  $('#gas-mq6').textContent = Number.isFinite(g.mq6) ? `${g.mq6.toFixed(0)} ppm` : (Number.isFinite(g.single) ? 'Combined above' : 'No data');
}

const LOG_LABEL = { gas: 'Gas', crack: 'Crack', safety: 'Safety', nav: 'Navigation', info: 'Info' };
function logEvent(kind, text) {
  const list = $('#event-log');
  const li = document.createElement('li');
  li.className = `ev ev-${kind}`;
  const t = new Date();
  li.innerHTML = `<time>${t.toLocaleTimeString([], { hour12: false })}</time><span class="kind">${LOG_LABEL[kind] || kind}</span><span class="msg"></span>`;
  li.querySelector('.msg').textContent = text;
  list.prepend(li);
  while (list.children.length > CONFIG.maxEvents) list.lastElementChild.remove();
  $('#log-empty').hidden = true;
}
$('#log-clear').addEventListener('click', () => { $('#event-log').innerHTML = ''; $('#log-empty').hidden = false; });

// ---------------------------------------------------------------------------
// Camera
// ---------------------------------------------------------------------------
const cam = $('#camera');
let camRetry = null;
function loadCamera() {
  clearTimeout(camRetry);
  cam.src = `${CONFIG.cameraUrl}?t=${Date.now()}`;
}
cam.addEventListener('load', () => { setLink('cam', 'ok', 'Camera streaming'); $('#cam-empty').hidden = true; });
cam.addEventListener('error', () => {
  setLink('cam', 'bad', 'Camera offline');
  $('#cam-empty').hidden = false;
  camRetry = setTimeout(loadCamera, 3000);
});
loadCamera();

let crackTimer = null;
function showCrack(conf, x, y) {
  const o = $('#crack-overlay');
  const pct = (conf * (conf <= 1 ? 100 : 1)).toFixed(0);
  o.querySelector('.label').textContent = `Crack ${pct}%`;
  const W = cam.naturalWidth || 640, H = cam.naturalHeight || 480;
  const nx = x <= 1 ? x : x / W, ny = y <= 1 ? y : y / H;
  const mark = o.querySelector('.mark');
  if (Number.isFinite(nx) && Number.isFinite(ny)) {
    mark.style.left = `${nx * 100}%`; mark.style.top = `${ny * 100}%`; mark.hidden = false;
  } else mark.hidden = true;
  o.hidden = false;
  clearTimeout(crackTimer);
  crackTimer = setTimeout(() => { o.hidden = true; }, 3000);
}

// ---------------------------------------------------------------------------
// Modes and manual driving
// ---------------------------------------------------------------------------
function setMode(m) {
  state.mode = m;
  document.body.dataset.mode = m;
  for (const b of document.querySelectorAll('[data-set-mode]')) b.setAttribute('aria-pressed', String(b.dataset.setMode === m));
  slam.setManual(m === 'manual');
  $('#mode-state').textContent = m === 'manual' ? 'Manual' : 'Autonomous';
  $('#teleop').hidden = m !== 'manual';
  $('#map-hint').textContent = m === 'manual' ? 'Click the map to send R.O.B.I.E. there. Drag to pan, scroll to zoom.' : 'Drag to pan, scroll to zoom. Switch to manual to send goals.';
  if (m !== 'manual') stopTeleop();
  logEvent('nav', `Mode set to ${m === 'manual' ? 'manual' : 'autonomous'}`);
}
for (const b of document.querySelectorAll('[data-set-mode]')) b.addEventListener('click', () => setMode(b.dataset.setMode));

// Teleop: commands only flow while a key/button is held; release, blur or disconnect sends zero.
const held = new Set();
const KEYMAP = { KeyW: 'fwd', ArrowUp: 'fwd', KeyS: 'back', ArrowDown: 'back', KeyA: 'left', KeyD: 'right', KeyQ: 'rotl', KeyE: 'rotr', ArrowLeft: 'rotl', ArrowRight: 'rotr' };
let teleopTimer = null;

function teleopTwist() {
  const v = parseFloat($('#speed').value), w = v * 3;
  const x = (held.has('fwd') ? v : 0) - (held.has('back') ? v : 0);
  const y = (held.has('left') ? v : 0) - (held.has('right') ? v : 0);
  const z = (held.has('rotl') ? w : 0) - (held.has('rotr') ? w : 0);
  return { linear: { x, y, z: 0 }, angular: { x: 0, y: 0, z } };
}
function teleopSend() {
  if (state.mode !== 'manual' || state.stopLatched) { stopTeleop(); return; }
  ros.publish(...CONFIG.topics.cmdVel, teleopTwist());
}
function teleopChanged() {
  for (const b of document.querySelectorAll('[data-drive]')) b.classList.toggle('is-active', held.has(b.dataset.drive));
  if (held.size && !teleopTimer) { teleopSend(); teleopTimer = setInterval(teleopSend, 1000 / CONFIG.teleopHz); }
  if (!held.size) stopTeleop();
}
function stopTeleop() {
  const wasActive = teleopTimer || held.size;
  held.clear(); clearInterval(teleopTimer); teleopTimer = null;
  for (const b of document.querySelectorAll('[data-drive]')) b.classList.remove('is-active');
  if (wasActive) ros.publish(...CONFIG.topics.cmdVel, { linear: { x: 0, y: 0, z: 0 }, angular: { x: 0, y: 0, z: 0 } });
}
window.addEventListener('keydown', (e) => {
  if (state.mode !== 'manual' || e.repeat || e.target.matches('input, textarea, select')) return;
  const a = KEYMAP[e.code]; if (!a) return;
  e.preventDefault(); held.add(a); teleopChanged();
});
window.addEventListener('keyup', (e) => { const a = KEYMAP[e.code]; if (a && held.delete(a)) teleopChanged(); });
window.addEventListener('blur', stopTeleop);
document.addEventListener('visibilitychange', () => { if (document.hidden) stopTeleop(); });
for (const b of document.querySelectorAll('[data-drive]')) {
  b.addEventListener('pointerdown', (e) => { e.preventDefault(); b.setPointerCapture(e.pointerId); held.add(b.dataset.drive); teleopChanged(); });
  for (const ev of ['pointerup', 'pointercancel', 'lostpointercapture']) b.addEventListener(ev, () => { if (held.delete(b.dataset.drive)) teleopChanged(); });
}
$('#speed').addEventListener('input', (e) => { $('#speed-val').textContent = `${parseFloat(e.target.value).toFixed(2)} m/s`; });

// ---------------------------------------------------------------------------
// Link indicators, server health, data freshness
// ---------------------------------------------------------------------------
function setLink(id, cls, title) {
  const el = document.querySelector(`[data-link="${id}"]`);
  if (!el) return;
  el.dataset.state = cls; el.title = title;
  el.querySelector('.txt').textContent = title;
}

async function pollServer() {
  try {
    const r = await fetch('/api/status', { cache: 'no-store' });
    const s = await r.json();
    setLink('safety', s.safety_node ? 'ok' : 'bad', s.safety_node ? 'Safety node reachable' : 'Safety node not reachable');
  } catch { setLink('safety', 'bad', 'Dashboard server not responding'); }
}
setInterval(pollServer, 3000); pollServer();

setInterval(() => {
  const now = performance.now();
  const poseAge = state.lastPoseAt ? (now - state.lastPoseAt) / 1000 : Infinity;
  $('#pose-age').textContent = poseAge === Infinity ? 'No pose yet' : poseAge < 1 ? 'Pose live' : `Pose ${poseAge.toFixed(0)} s old`;
  $('#pose-age').dataset.state = poseAge < 1 ? 'ok' : poseAge < 5 ? 'wait' : 'bad';
  if (state.gas.at && Date.now() - state.gas.at > 10000) $('#gas-age').textContent = `Last reading ${Math.round((Date.now() - state.gas.at) / 1000)} s ago`;
  else $('#gas-age').textContent = state.gas.at ? 'Live' : 'Waiting for readings';
  viewer.updateMap(slam);
}, 500);

// ---------------------------------------------------------------------------
let toastTimer = null;
function toast(text, kind = 'warn') {
  const t = $('#toast'); t.textContent = text; t.dataset.kind = kind; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 3500);
}

ros.connect();
setMode('auto');
renderGas();
