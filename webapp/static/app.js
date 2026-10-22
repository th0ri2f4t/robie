// R.O.B.I.E. Mission Control — client v3 (commands, manual pad, click-to-drive, fallback sim)
const $ = id => document.getElementById(id);
let ws, estopArmed = false, mockTimer = null, mockWorld = null, attempts = 0;
let pose = { x: 0, y: 0 }, trail = [], waypoint = null, hasPose = false;
const gasLog = [];

/* ---------- animated numbers ---------- */
const tweens = new Map();
function animNum(el, target, decimals = 0) {
  const from = tweens.get(el.id) ?? target;
  tweens.set(el.id, target);
  const t0 = performance.now(), dur = 450;
  (function step(t) {
    const k = Math.min((t - t0) / dur, 1), ease = 1 - Math.pow(1 - k, 3);
    el.textContent = (from + (target - from) * ease).toFixed(decimals);
    if (k < 1) requestAnimationFrame(step);
  })(performance.now());
}

/* ---------- gas chart ---------- */
Chart.defaults.font.family = "'Inter', sans-serif";
const gasChart = new Chart($('gasChart').getContext('2d'), {
  type: 'line',
  data: { labels: [], datasets: [
    { label: 'MQ-4', data: [], borderColor: '#34d399', borderWidth: 1.8, pointRadius: 0, tension: 0.35, fill: true,
      backgroundColor: c => { const g = c.chart.ctx.createLinearGradient(0, 0, 0, 140);
        g.addColorStop(0, 'rgba(52,211,153,0.18)'); g.addColorStop(1, 'rgba(52,211,153,0)'); return g; } },
    { label: 'MQ-6', data: [], borderColor: '#22d3ee', borderWidth: 1.8, pointRadius: 0, tension: 0.35, fill: true,
      backgroundColor: c => { const g = c.chart.ctx.createLinearGradient(0, 0, 0, 140);
        g.addColorStop(0, 'rgba(34,211,238,0.14)'); g.addColorStop(1, 'rgba(34,211,238,0)'); return g; } } ] },
  options: { animation: false, responsive: true, maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' },
    plugins: { legend: { display: false },
      tooltip: { backgroundColor: 'rgba(19,26,38,0.95)', borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1, cornerRadius: 8, padding: 10 } },
    scales: { x: { display: false },
      y: { min: 0, max: 4095, grid: { color: 'rgba(255,255,255,0.04)' }, border: { display: false },
        ticks: { color: '#8b86a0', font: { size: 10, weight: 600 }, stepSize: 2000 } } } }
});

/* ---------- patrol map ---------- */
const cvs = $('poseCanvas'), cx = cvs.getContext('2d');
const VIEW_M = 7;
function resize() {
  const r = cvs.parentElement.getBoundingClientRect();
  cvs.width = r.width * devicePixelRatio; cvs.height = r.height * devicePixelRatio;
  cx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  drawMap();
}
addEventListener('resize', resize);
const m2px = (x, y) => ({ px: cvs.clientWidth / 2 + (x / VIEW_M) * (cvs.clientWidth / 2 - 20),
                         py: cvs.clientHeight / 2 - (y / VIEW_M) * (cvs.clientHeight / 2 - 20) });
const px2m = (px, py) => ({ x: (px - cvs.clientWidth / 2) / (cvs.clientWidth / 2 - 20) * VIEW_M,
                            y: (cvs.clientHeight / 2 - py) / (cvs.clientHeight / 2 - 20) * VIEW_M });

function drawMap() {
  const w = cvs.clientWidth, h = cvs.clientHeight;
  cx.clearRect(0, 0, w, h);
  cx.fillStyle = 'rgba(205,180,246,0.07)';
  const step = Math.min(w, h) / 14;
  for (let gx = step / 2; gx < w; gx += step)
    for (let gy = step / 2; gy < h; gy += step) { cx.beginPath(); cx.arc(gx, gy, 1, 0, 7); cx.fill(); }
  cx.strokeStyle = 'rgba(205,180,246,0.09)'; cx.lineWidth = 1;
  cx.beginPath(); cx.moveTo(w / 2, 8); cx.lineTo(w / 2, h - 8); cx.moveTo(8, h / 2); cx.lineTo(w - 8, h / 2); cx.stroke();
  for (let i = 1; i < trail.length; i++) {
    const a = m2px(trail[i - 1].x, trail[i - 1].y), b = m2px(trail[i].x, trail[i].y);
    cx.strokeStyle = `rgba(205,180,246,${0.06 + 0.5 * (i / trail.length)})`;
    cx.lineWidth = 1.6; cx.beginPath(); cx.moveTo(a.px, a.py); cx.lineTo(b.px, b.py); cx.stroke();
  }
  if (waypoint) {
    const q = m2px(waypoint.x, waypoint.y);
    const pulse = 6 + Math.sin(performance.now() / 300) * 3;
    cx.fillStyle = 'rgba(251,191,36,0.25)'; cx.beginPath(); cx.arc(q.px, q.py, pulse + 6, 0, 7); cx.fill();
    cx.fillStyle = '#fbbf24'; cx.beginPath(); cx.arc(q.px, q.py, 5, 0, 7); cx.fill();
    cx.strokeStyle = 'rgba(251,191,36,0.6)'; cx.lineWidth = 1.5;
    cx.beginPath(); cx.arc(q.px, q.py, 10, 0, 7); cx.stroke();
  }
  if (hasPose) {
    const r = m2px(pose.x, pose.y);
    const glow = cx.createRadialGradient(r.px, r.py, 0, r.px, r.py, 26);
    glow.addColorStop(0, 'rgba(205,180,246,0.4)'); glow.addColorStop(1, 'rgba(205,180,246,0)');
    cx.fillStyle = glow; cx.beginPath(); cx.arc(r.px, r.py, 26, 0, 7); cx.fill();
    cx.fillStyle = '#cdb4f6'; cx.beginPath(); cx.arc(r.px, r.py, 6, 0, 7); cx.fill();
    cx.strokeStyle = '#1a1030'; cx.lineWidth = 2; cx.stroke();
  }
}
cvs.addEventListener('click', e => {
  const rect = cvs.getBoundingClientRect();
  const m = px2m(e.clientX - rect.left, e.clientY - rect.top);
  waypoint = m; drawMap();
  if (window.ROBIE_BG3D) window.ROBIE_BG3D.setWaypoint(m.x, m.y);
  sendCmd(`W,${m.x.toFixed(2)},${m.y.toFixed(2)}`);
  toast('cmd', `Waypoint set — driving to x ${m.x.toFixed(2)} · y ${m.y.toFixed(2)}`, 'info');
});

/* ---------- toasts / pills / events ---------- */
function toast(type, body) {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const head = type === 'leak' ? '⚠ LEAK DETECTED' : type === 'crack' ? '✕ CRACK DETECTED' : '◈ COMMAND';
  t.innerHTML = `<div class="t-head">${head}</div><div class="t-body">${body}</div>`;
  $('toasts').appendChild(t);
  requestAnimationFrame(() => requestAnimationFrame(() => t.classList.add('show')));
  setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 400); }, 4200);
  while ($('toasts').children.length > 4) $('toasts').firstChild.remove();
}
function setPill(id, trig) {
  $(`pill-${id}`).className = 'safety-pill ' + (trig ? 'triggered' : 'clear');
  $(`state-${id}`).textContent = trig ? (id === 'estop' ? 'ENGAGED' : 'OBSTACLE') : 'CLEAR';
}
let eventCount = 0;
function addEvent(type, value, x, y) {
  if (eventCount++ === 0) $('events').innerHTML = '';
  const el = document.createElement('div');
  el.className = `event-item ${type.toLowerCase()}`;
  el.innerHTML = `<span class="dot"></span><span class="type">${type}</span>
    <span class="meta">conf ${(+value * 100).toFixed(0)}% · (${x}, ${y}) · ${new Date().toLocaleTimeString()}</span>`;
  $('events').prepend(el);
  while ($('events').children.length > 30) $('events').lastChild.remove();
}

/* ---------- commands (ws first, fallback sim second) ---------- */
function sendCmd(d) {
  if (ws && ws.readyState === 1) ws.send(d);
  else if (mockWorld) mockWorld.command(d);
  else console.log('[demo] cmd:', d);
}
function toggleEstop() {
  estopArmed = !estopArmed;
  const b = $('btnEstop');
  b.textContent = estopArmed ? '⏻ Release E-Stop' : '⏻ Remote E-Stop';
  b.classList.toggle('active', estopArmed);
  sendCmd(`E,${estopArmed ? 1 : 0}`);
  toast('cmd', estopArmed ? 'Remote E-STOP engaged' : 'E-STOP released');
}
$('btnEstop').addEventListener('click', toggleEstop);
$('btnCsv').addEventListener('click', () => {
  const rows = ['t_ms,mq4,mq6'].concat(gasLog.map(r => r.join(',')));
  const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'robie_gas_' + new Date().toISOString().replace(/[:.]/g, '-') + '.csv';
  a.click();
  URL.revokeObjectURL(a.href);
});

/* ---------- manual drive pad (hold to drive) ---------- */
document.querySelectorAll('.padbtn').forEach(b => {
  const cmd = b.dataset.cmd;
  const down = e => { e.preventDefault(); sendCmd(cmd); };
  const up = () => { if (cmd !== 'A,1') sendCmd('D,0,0,0'); };
  b.addEventListener('pointerdown', down);
  b.addEventListener('pointerup', up);
  b.addEventListener('pointerleave', up);
});

/* ---------- packet handler ---------- */
function handlePacket(msg) {
  const p = msg.split(',');
  switch (p[0]) {
    case 'T': setPill('estop', p[1] === '1'); setPill('bumpf', p[2] === '1'); setPill('bumpr', p[3] === '1'); break;
    case 'H': $('hb').textContent = 'live · ' + Math.round(+p[1] / 1000) + 's'; break;
    case 'B': {
      animNum($('battery'), +p[1], 2);
      const pct = Math.max(0, Math.min(100, ((+p[1] - 10.5) / (12.6 - 10.5)) * 100));
      $('batteryPct').textContent = pct.toFixed(0) + '% capacity';
      const bar = $('battbar'); bar.style.width = pct + '%';
      bar.style.background = pct < 20 ? 'var(--danger)' : pct < 50 ? 'var(--warning)' : 'var(--success)';
      break;
    }
    case 'G': {
      const a = +p[1], b = +p[2];
      gasLog.push([Date.now(), a, b]); if (gasLog.length > 5000) gasLog.shift();
      animNum($('mq4'), a); animNum($('mq6'), b);
      const setBar = (id, v) => { const f = $(id); f.style.width = Math.min(100, v / 4095 * 100) + '%';
        f.style.background = v > 2500 ? 'var(--warning)' : (id === 'mq4bar' ? 'var(--success)' : 'var(--accent)'); };
      setBar('mq4bar', a); setBar('mq6bar', b);
      const d = gasChart.data;
      d.labels.push(''); d.datasets[0].data.push(a); d.datasets[1].data.push(b);
      if (d.labels.length > 80) { d.labels.shift(); d.datasets.forEach(s => s.data.shift()); }
      gasChart.update('none'); break;
    }
    case 'P':
      pose = { x: +p[1], y: +p[2] }; hasPose = true;
      trail.push(pose); if (trail.length > 400) trail.shift();
      $('coords').textContent = `x ${pose.x.toFixed(2)} · y ${pose.y.toFixed(2)}`;
      if (window.ROBIE_BG3D) window.ROBIE_BG3D.setPose(+p[1], +p[2], +p[3]);
      drawMap(); break;
    case 'L': addEvent('LEAK', p[1], p[2], p[3]);
      if (window.ROBIE_BG3D) window.ROBIE_BG3D.pulse('leak', +p[2], +p[3]);
      toast('leak', `Hydrocarbon plume localised — severity ${(p[1] * 100).toFixed(0)}% at (${p[2]}, ${p[3]})`); break;
    case 'C': addEvent('CRACK', p[1], p[2], p[3]);
      if (window.ROBIE_BG3D) window.ROBIE_BG3D.pulse('crack', +p[2], +p[3]);
      toast('crack', `Pipe crack detected — confidence ${(p[1] * 100).toFixed(0)}% at (${p[2]}, ${p[3]})`); break;
    case 'Z':
      if (window.ROBIE_BG3D) window.ROBIE_BG3D.scanData(p[1]);
      break;
  }
}

/* ---------- fallback world (offline demo with full command support) ---------- */
const randn = () => (Math.random() + Math.random() + Math.random() - 1.5) * 1.6;
function makeMockWorld() {
  const w = {
    mode: 'patrol', th: 0, x: 2, y: 0, target: [0, 0], vel: [0, 0, 0],
    estop: false, resume: false,
    command(msg) {
      const p = msg.split(',');
      if (p[0] === 'W' && p.length === 3) { w.target = [+p[1], +p[2]]; w.mode = 'goto'; w.resume = true; }
      else if (p[0] === 'E' && p.length === 2) w.estop = p[1] === '1';
      else if (p[0] === 'D' && p.length === 4) { w.vel = [+p[1], +p[2], +p[3]]; w.mode = 'manual'; }
      else if (p[0] === 'A' && p[1] === '1') { w.mode = 'patrol'; w.th = Math.atan2(w.y, w.x); }
    },
    step(dt) {
      if (w.estop) return;
      if (w.mode === 'patrol') { w.th += 0.35 * dt; w.x = 2 * Math.cos(w.th); w.y = 2 * Math.sin(w.th); }
      else if (w.mode === 'goto') {
        const dx = w.target[0] - w.x, dy = w.target[1] - w.y, d = Math.hypot(dx, dy);
        if (d < 0.08) { if (w.resume) { w.mode = 'patrol'; w.th = Math.atan2(w.y, w.x); } }
        else { const s = Math.min(0.9 * dt, d); w.x += dx / d * s; w.y += dy / d * s; w.th = Math.atan2(dy, dx); }
      } else if (w.mode === 'manual') { w.x += w.vel[0] * dt; w.y += w.vel[1] * dt; w.th += w.vel[2] * dt; }
    }
  };
  return w;
}
function startBrowserMock() {
  if (mockTimer) return;
  $('connText').textContent = 'demo mode';
  $('connDot').classList.add('on');
  const world = makeMockWorld();
  mockWorld = world;
  let t = 0, batt = 12.6, leak = false, leakUntil = 0;
  mockTimer = setInterval(() => {
    t += 0.1;
    world.step(0.1);
    handlePacket(`P,${world.x.toFixed(2)},${world.y.toFixed(2)},${world.th.toFixed(2)}`);
    if (!leak && Math.random() < 0.004) { leak = true; leakUntil = t + 6; }
    if (leak && t > leakUntil) leak = false;
    const sp = leak ? 2200 : 0;
    handlePacket(`T,${world.estop ? 1 : 0},${Math.random() < 0.015 ? 1 : 0},0`);
    batt = Math.max(10.5, batt - 0.0004);
    handlePacket(`B,${batt.toFixed(2)}`);
    handlePacket(`H,${Math.round(t * 1000)}`);
    handlePacket(`G,${Math.round(800 + randn() * 40 + sp * (0.7 + Math.random() * 0.3))},${Math.round(650 + randn() * 35 + sp * (0.3 + Math.random() * 0.3))}`);
    if (leak && Math.random() < 0.15) handlePacket(`L,${(0.5 + Math.random() * 0.5).toFixed(2)},${world.x.toFixed(2)},${world.y.toFixed(2)}`);
    if (Math.random() < 0.003) handlePacket(`C,${(0.6 + Math.random() * 0.39).toFixed(2)},${world.x.toFixed(2)},${world.y.toFixed(2)}`);
  }, 100);
  setInterval(() => { if (mockTimer) connect(); }, 10000);
}
function stopMock() { if (mockTimer) { clearInterval(mockTimer); mockTimer = null; mockWorld = null; } }

/* ---------- websocket ---------- */
function connect() {
  try { ws = new WebSocket(`ws://${location.host}/ws`); } catch { startBrowserMock(); return; }
  ws.onopen = () => { attempts = 0; stopMock();
    $('connDot').classList.add('on'); $('connText').textContent = 'live'; };
  ws.onclose = () => {
    $('connDot').classList.remove('on');
    attempts++;
    if (attempts >= 3) { $('connText').textContent = 'offline'; startBrowserMock(); }
    else { $('connText').textContent = 'reconnecting…'; setTimeout(connect, 1500); }
  };
  ws.onmessage = ev => handlePacket(ev.data);
}

resize(); connect();