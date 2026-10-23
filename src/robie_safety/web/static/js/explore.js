// R.O.B.I.E. 3D + SLAM page: lidar reconstruction, full 2D SLAM map, click-to-move on either, save map, STOP.
// World frame = ROS map frame (Z up, metres).
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RosBridge, yawFromQuaternion } from './ros_bridge.js';
import { SlamMap } from './slam_map.js';
import { loadRobotModel } from './cad_viewer.js';
import { CONFIG, sendStop, sendReset, publishGoal, holdButton } from './common.js';

const $ = (s) => document.querySelector(s);
const VOXEL = 0.05;            // lidar hits are binned into 5 cm cells
const MAX_HITS = 80000;        // ring buffer of wall cells built from the lidar
const FRESH = new THREE.Color('#e2c8ff'), OLD = new THREE.Color('#6a55a6');   // lilac -> violet as cells age
const FADE_S = 90;             // seconds for a lidar cell to fade from fresh to old

// ---------------------------------------------------------------------------
// TF buffer (latest transform per child frame; enough for display)
// ---------------------------------------------------------------------------
class TfBuffer {
  constructor() { this.tf = new Map(); }
  ingest(msg) {
    for (const t of msg.transforms || []) {
      const child = t.child_frame_id.replace(/^\//, ''), parent = t.header.frame_id.replace(/^\//, '');
      const p = t.transform.translation, q = t.transform.rotation;
      const m = new THREE.Matrix4().compose(new THREE.Vector3(p.x, p.y, p.z), new THREE.Quaternion(q.x, q.y, q.z, q.w), new THREE.Vector3(1, 1, 1));
      this.tf.set(child, { parent, m, at: performance.now() });
    }
  }
  // matrix taking points in `source` into `target`, or null if the chain is incomplete
  lookup(target, source) {
    source = source.replace(/^\//, '');
    const M = new THREE.Matrix4();
    let f = source;
    for (let i = 0; i < 12 && f !== target; i++) {
      const e = this.tf.get(f);
      if (!e) return null;
      M.premultiply(e.m);
      f = e.parent;
    }
    return f === target ? M : null;
  }
}

// ---------------------------------------------------------------------------
// The 3D scene
// ---------------------------------------------------------------------------
class Explore3D extends EventTarget {
  constructor(container) {
    super();
    this.container = container;
    this.wallH = 0.6;
    this.follow = true;
    this.clickToMove = false;
    this.pose = null;           // {x,y,yaw}
    this.shownPose = null;
    this.goal = null;

    const r = this.renderer = new THREE.WebGLRenderer({ antialias: true });
    r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    r.outputColorSpace = THREE.SRGBColorSpace;
    r.setClearColor(0x140f24);
    container.appendChild(r.domElement);

    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.Fog(0x140f24, 12, 40);
    this.camera = new THREE.PerspectiveCamera(50, 1, 0.02, 200);
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(-2.2, -2.6, 2.4);
    this.controls = new OrbitControls(this.camera, r.domElement);
    this.controls.enableDamping = true;
    this.controls.maxPolarAngle = Math.PI * 0.495;
    this.controls.target.set(0, 0, 0.1);
    this.controls.addEventListener('start', () => { this._orbiting = true; });
    this.controls.addEventListener('end', () => { this._orbiting = false; });

    this.scene.add(new THREE.HemisphereLight(0xf1e9ff, 0x1d1436, 1.05));
    const sun = new THREE.DirectionalLight(0xffffff, 1.4); sun.position.set(3, -4, 8); this.scene.add(sun);

    this.grid = new THREE.GridHelper(40, 80, 0x4a3b78, 0x2a2048); this.grid.rotation.x = Math.PI / 2; this.scene.add(this.grid);

    // floor = SLAM map texture
    this.floor = null; this.mapVersion = -1;

    // walls extruded from the SLAM occupancy grid
    const unit = new THREE.BoxGeometry(1, 1, 1); unit.translate(0, 0, 0.5);
    this.mapWalls = new THREE.InstancedMesh(unit, new THREE.MeshStandardMaterial({ color: 0xb9a6e8, roughness: 0.85, transparent: true, opacity: 0.45 }), 60000);
    this.mapWalls.count = 0; this.mapWalls.frustumCulled = false; this.scene.add(this.mapWalls);

    // walls built from lidar hits (the reconstruction)
    this.hits = new THREE.InstancedMesh(unit, new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.45, emissive: 0x24123f }), MAX_HITS);
    this.hits.count = 0; this.hits.frustumCulled = false;
    this.hits.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.hits.setColorAt(0, FRESH); this.scene.add(this.hits);
    this.voxels = new Map(); this.slotKey = new Array(MAX_HITS); this.slotSeen = new Float32Array(MAX_HITS); this.slotPos = new Float32Array(MAX_HITS * 2);
    this.nextSlot = 0; this.used = 0;

    // live scan: bright points at the scan plane
    this.scanGeo = new THREE.BufferGeometry();
    this.scanGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(4096 * 3), 3));
    this.scanGeo.setDrawRange(0, 0);
    this.scan = new THREE.Points(this.scanGeo, new THREE.PointsMaterial({ color: 0xff9fd8, size: 4, sizeAttenuation: false }));
    this.scan.frustumCulled = false; this.scene.add(this.scan);

    // robot + trail
    this.robot = new THREE.Group(); this.scene.add(this.robot);
    loadRobotModel(this.robot).then((t) => this.dispatchEvent(new CustomEvent('status', { detail: t })));
    this.trailPts = [];
    this.trail = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0xffe39a }));
    this.trail.frustumCulled = false; this.scene.add(this.trail);

    // goal marker + path
    this.goalGroup = new THREE.Group(); this.goalGroup.visible = false;
    const ring = new THREE.Mesh(new THREE.RingGeometry(0.09, 0.14, 40), new THREE.MeshBasicMaterial({ color: 0x9ff0d0, side: THREE.DoubleSide }));
    ring.position.z = 0.004; this.goalGroup.add(ring);
    const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.8, 12), new THREE.MeshBasicMaterial({ color: 0x9ff0d0, transparent: true, opacity: 0.7 }));
    beam.rotation.x = Math.PI / 2; beam.position.z = 0.4; this.goalGroup.add(beam);
    this.scene.add(this.goalGroup);
    this.path = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineDashedMaterial({ color: 0x9ff0d0, dashSize: 0.08, gapSize: 0.06 }));
    this.path.frustumCulled = false; this.path.visible = false; this.scene.add(this.path);

    // hover marker for click-to-move
    this.cursor = new THREE.Mesh(new THREE.RingGeometry(0.06, 0.1, 32), new THREE.MeshBasicMaterial({ color: 0xc9b6ff, side: THREE.DoubleSide, transparent: true, opacity: 0.9 }));
    this.cursor.visible = false; this.scene.add(this.cursor);

    this._bindClicks();
    new ResizeObserver(() => this._resize()).observe(container);
    this._resize();
    this.clock = new THREE.Clock();
    setInterval(() => this._recolour(), 1000);
    r.setAnimationLoop(() => this._tick());
  }

  // ---- data in ----
  updateMap(slam) {
    if (!slam.info || slam.mapVersion === this.mapVersion) return;
    this.mapVersion = slam.mapVersion;
    const i = slam.info, w = i.width * i.resolution, h = i.height * i.resolution;
    if (!this.floor || this.floor.userData.w !== w || this.floor.userData.h !== h) {
      if (this.floor) { this.scene.remove(this.floor); this.floor.geometry.dispose(); this.floor.material.map.dispose(); }
      const tex = new THREE.CanvasTexture(slam.grid); tex.magFilter = THREE.NearestFilter; tex.colorSpace = THREE.SRGBColorSpace;
      this.floor = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: 0.85 }));
      this.floor.userData = { w, h }; this.scene.add(this.floor); this.grid.visible = false;
    }
    this.floor.material.map.needsUpdate = true;
    const c = Math.cos(i.oyaw), s = Math.sin(i.oyaw);
    this.floor.position.set(i.ox + c * w / 2 - s * h / 2, i.oy + s * w / 2 + c * h / 2, -0.002);
    this.floor.rotation.set(0, 0, i.oyaw);
    // extrude occupied cells
    const m = new THREE.Matrix4(), q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), i.oyaw);
    let n = 0;
    for (let row = 0; row < i.height && n < this.mapWalls.instanceMatrix.count; row++) {
      for (let col = 0; col < i.width; col++) {
        if (slam.raw[row * i.width + col] < 65) continue;
        const wx = i.ox + (c * (col + 0.5) - s * (row + 0.5)) * i.resolution, wy = i.oy + (s * (col + 0.5) + c * (row + 0.5)) * i.resolution;
        m.compose(new THREE.Vector3(wx, wy, 0), q, new THREE.Vector3(i.resolution, i.resolution, this.wallH));
        this.mapWalls.setMatrixAt(n++, m);
        if (n >= 60000) break;
      }
    }
    this.mapWalls.count = n; this.mapWalls.instanceMatrix.needsUpdate = true;
    this._lastSlam = slam;
  }

  setPose(x, y, yaw) {
    this.pose = { x, y, yaw };
    if (!this.shownPose) { this.shownPose = { ...this.pose }; this._place(); this._recentre(true); }
    const last = this.trailPts[this.trailPts.length - 1];
    if (!last || Math.hypot(last.x - x, last.y - y) > 0.03) {
      this.trailPts.push(new THREE.Vector3(x, y, 0.01));
      if (this.trailPts.length > 2000) this.trailPts.shift();
      this.trail.geometry.setFromPoints(this.trailPts);
    }
    if (this.goal && Math.hypot(this.goal.x - x, this.goal.y - y) < 0.12) {
      this.dispatchEvent(new CustomEvent('reached', { detail: this.goal }));
      this.setGoal(null);
    }
  }

  // points: Float32Array of xyz in the map frame; also adds them to the reconstruction
  addScan(pts, n) {
    const pos = this.scanGeo.attributes.position;
    pos.array.set(pts.subarray(0, Math.min(n, 4096) * 3)); pos.needsUpdate = true;
    this.scanGeo.setDrawRange(0, Math.min(n, 4096));
    const now = performance.now() / 1000, m = new THREE.Matrix4(), one = new THREE.Quaternion();
    let changed = false;
    for (let k = 0; k < n; k++) {
      const x = pts[k * 3], y = pts[k * 3 + 1];
      const ix = Math.floor(x / VOXEL), iy = Math.floor(y / VOXEL), key = ix * 100003 + iy;
      const slot = this.voxels.get(key);
      if (slot !== undefined) { this.slotSeen[slot] = now; continue; }
      const s = this.nextSlot; this.nextSlot = (this.nextSlot + 1) % MAX_HITS;
      if (this.slotKey[s] !== undefined) this.voxels.delete(this.slotKey[s]);
      this.slotKey[s] = key; this.voxels.set(key, s); this.slotSeen[s] = now;
      const cx = (ix + 0.5) * VOXEL, cy = (iy + 0.5) * VOXEL;
      this.slotPos[s * 2] = cx; this.slotPos[s * 2 + 1] = cy;
      m.compose(new THREE.Vector3(cx, cy, 0), one, new THREE.Vector3(VOXEL * 0.9, VOXEL * 0.9, this.wallH));
      this.hits.setMatrixAt(s, m); this.hits.setColorAt(s, FRESH);
      this.used = Math.min(this.used + 1, MAX_HITS); changed = true;
    }
    if (changed) {
      this.hits.count = this.used; this.hits.instanceMatrix.needsUpdate = true;
      if (this.hits.instanceColor) this.hits.instanceColor.needsUpdate = true;
    }
  }

  clearHits() {
    this.voxels.clear(); this.slotKey = new Array(MAX_HITS); this.used = 0; this.nextSlot = 0; this.hits.count = 0;
  }

  setWallHeight(h) {
    this.wallH = h;
    const m = new THREE.Matrix4(), one = new THREE.Quaternion();
    for (let s = 0; s < this.used; s++) {
      m.compose(new THREE.Vector3(this.slotPos[s * 2], this.slotPos[s * 2 + 1], 0), one, new THREE.Vector3(VOXEL * 0.9, VOXEL * 0.9, h));
      this.hits.setMatrixAt(s, m);
    }
    this.hits.instanceMatrix.needsUpdate = true;
    if (this._lastSlam) { this.mapVersion = -1; this.updateMap(this._lastSlam); }
  }

  setGoal(g) {
    this.goal = g;
    this.goalGroup.visible = !!g; this.path.visible = !!g;
    if (g) this.goalGroup.position.set(g.x, g.y, 0);
  }

  // ---- camera ----
  setFollow(on) { this.follow = on; if (on) this._recentre(true); }
  topView() {
    const p = this.shownPose || { x: 0, y: 0 };
    this.controls.target.set(p.x, p.y, 0);
    this.camera.position.set(p.x, p.y - 0.01, 9);
  }
  resetView() {
    const p = this.shownPose || { x: 0, y: 0 };
    this.controls.target.set(p.x, p.y, 0.1);
    this.camera.position.set(p.x - 2.2, p.y - 2.6, 2.4);
  }
  _recentre(jump) {
    if (!this.shownPose) return;
    const t = this.controls.target, dx = this.shownPose.x - t.x, dy = this.shownPose.y - t.y;
    t.set(this.shownPose.x, this.shownPose.y, 0.1);
    if (jump) { this.camera.position.x += dx; this.camera.position.y += dy; }
  }

  // ---- click-to-move ----
  _groundAt(ev) {
    const r = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
    const ray = new THREE.Raycaster(); ray.setFromCamera(ndc, this.camera);
    const hit = new THREE.Vector3();
    return ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 0, 1), 0), hit) ? hit : null;
  }
  _bindClicks() {
    const el = this.renderer.domElement;
    let down = null;
    el.addEventListener('pointerdown', (e) => { down = { x: e.clientX, y: e.clientY }; });
    el.addEventListener('pointermove', (e) => {
      if (!this.clickToMove) { this.cursor.visible = false; return; }
      const p = this._groundAt(e);
      this.cursor.visible = !!p;
      if (p) this.cursor.position.set(p.x, p.y, 0.006);
    });
    el.addEventListener('pointerleave', () => { this.cursor.visible = false; });
    el.addEventListener('pointerup', (e) => {
      if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5) { down = null; return; }
      down = null;
      if (!this.clickToMove) return;
      const p = this._groundAt(e);
      if (p) this.dispatchEvent(new CustomEvent('click-ground', { detail: { x: p.x, y: p.y } }));
    });
  }

  // ---- frame loop ----
  _place() {
    this.robot.position.set(this.shownPose.x, this.shownPose.y, 0);
    this.robot.rotation.set(0, 0, this.shownPose.yaw);
  }
  _recolour() {
    if (!this.used || !this.hits.instanceColor) return;
    const now = performance.now() / 1000, c = new THREE.Color();
    for (let s = 0; s < this.used; s++) {
      const a = Math.min(1, (now - this.slotSeen[s]) / FADE_S);
      c.copy(FRESH).lerp(OLD, a); this.hits.setColorAt(s, c);
    }
    this.hits.instanceColor.needsUpdate = true;
  }
  _tick() {
    const dt = Math.min(this.clock.getDelta(), 0.1);
    if (this.pose && this.shownPose) {
      const k = 1 - Math.exp(-dt * 12), sp = this.shownPose;
      const ox = sp.x, oy = sp.y;
      sp.x += (this.pose.x - sp.x) * k; sp.y += (this.pose.y - sp.y) * k;
      let d = this.pose.yaw - sp.yaw; d = Math.atan2(Math.sin(d), Math.cos(d)); sp.yaw += d * k;
      this._place();
      if (this.follow && !this._orbiting) {
        this.camera.position.x += sp.x - ox; this.camera.position.y += sp.y - oy;
        this.controls.target.set(sp.x, sp.y, this.controls.target.z);
      }
      if (this.goal) {
        this.path.geometry.setFromPoints([new THREE.Vector3(sp.x, sp.y, 0.02), new THREE.Vector3(this.goal.x, this.goal.y, 0.02)]);
        this.path.computeLineDistances();
      }
    }
    this.goalGroup.rotation.z += dt * 1.2;
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }
  _resize() {
    const w = this.container.clientWidth, h = this.container.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
  }
}

// ---------------------------------------------------------------------------
// Page wiring
// ---------------------------------------------------------------------------
const ros = new RosBridge(CONFIG.rosbridgeUrl);
const view = new Explore3D($('#view'));
const map2d = new SlamMap($('#slam-canvas'));   // the full 2D SLAM map pane
const tf = new TfBuffer();
const st = { lastScanAt: 0, scanTimes: [], tfMode: '', poseFromTopicAt: 0, stopLatched: false };

function setLink(id, cls, text) {
  const el = document.querySelector(`[data-link="${id}"]`);
  if (!el) return; el.dataset.state = cls; el.querySelector('.txt').textContent = text;
}
let toastTimer = null;
function toast(text, kind = 'warn') {
  const t = $('#toast'); t.textContent = text; t.dataset.kind = kind; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 3500);
}

ros.addEventListener('state', (e) => {
  const s = e.detail.state;
  setLink('ros', s === 'connected' ? 'ok' : s === 'connecting' ? 'wait' : 'bad',
    s === 'connected' ? 'ROS connected' : s === 'connecting' ? 'Connecting to ROS…' : 'ROS offline');
  $('#reconnect').hidden = s === 'connected' || s === 'connecting';
});
$('#reconnect').addEventListener('click', () => ros.reconnect());
view.addEventListener('status', (e) => { $('#model-note').textContent = e.detail; });

// map
ros.subscribe(...CONFIG.topics.map, (msg) => {
  map2d.setMap(msg); view.updateMap(map2d);
  $('#map-empty').hidden = true;
  $('#map-meta').textContent = `${msg.info.width} × ${msg.info.height} cells, ${(msg.info.resolution * 100).toFixed(0)} cm`;
}, { throttle_rate: 1000, queue_length: 1 });

// TF
ros.subscribe(...CONFIG.topics.tf, (msg) => tf.ingest(msg), { queue_length: 20 });
ros.subscribe(...CONFIG.topics.tfStatic, (msg) => tf.ingest(msg), { queue_length: 20 });

// pose: /robot_pose if published, otherwise TF map -> base_link
function applyPose(x, y, yaw) {
  view.setPose(x, y, yaw); map2d.setPose(x, y, yaw);
  $('#pose').textContent = `x ${x.toFixed(2)} m   y ${y.toFixed(2)} m   heading ${(yaw * 180 / Math.PI).toFixed(0)}°`;
}
ros.subscribe(...CONFIG.topics.pose, (msg) => {
  st.poseFromTopicAt = performance.now();
  applyPose(msg.pose.position.x, msg.pose.position.y, yawFromQuaternion(msg.pose.orientation));
}, { throttle_rate: 50, queue_length: 1 });
setInterval(() => {
  if (performance.now() - st.poseFromTopicAt < 1000) return;
  for (const base of ['base_link', 'base_footprint']) {
    const M = tf.lookup(CONFIG.fixedFrame, base);
    if (M) {
      const p = new THREE.Vector3(), q = new THREE.Quaternion(); M.decompose(p, q, new THREE.Vector3());
      applyPose(p.x, p.y, new THREE.Euler().setFromQuaternion(q, 'ZYX').z);
      return;
    }
  }
}, 100);

// lidar
const scanBuf = new Float32Array(8192 * 3);
ros.subscribe(...CONFIG.topics.scan, (msg) => {
  const frame = (msg.header.frame_id || 'laser').replace(/^\//, '');
  let M = tf.lookup(CONFIG.fixedFrame, frame), mode = `TF: ${frame} → ${CONFIG.fixedFrame}`;
  if (!M && view.pose) {
    const L = CONFIG.laserFallback, p = view.pose;
    const base = new THREE.Matrix4().compose(new THREE.Vector3(p.x, p.y, 0), new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), p.yaw), new THREE.Vector3(1, 1, 1));
    const lz = new THREE.Matrix4().compose(new THREE.Vector3(L.x, L.y, L.z), new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), L.yaw), new THREE.Vector3(1, 1, 1));
    M = base.multiply(lz); mode = 'Fallback: robot pose + lidar offset';
  }
  if (!M) { st.tfMode = 'Waiting for robot pose'; return; }
  st.tfMode = mode;
  const e = M.elements, ranges = msg.ranges, a0 = msg.angle_min, da = msg.angle_increment;
  let n = 0;
  for (let i = 0; i < ranges.length && n < 8192; i++) {
    const r = ranges[i];
    if (r === null || !Number.isFinite(r) || r < msg.range_min || r > msg.range_max) continue;
    const a = a0 + i * da, lx = r * Math.cos(a), ly = r * Math.sin(a);
    scanBuf[n * 3] = e[0] * lx + e[4] * ly + e[12];
    scanBuf[n * 3 + 1] = e[1] * lx + e[5] * ly + e[13];
    scanBuf[n * 3 + 2] = e[2] * lx + e[6] * ly + e[14];
    n++;
  }
  view.addScan(scanBuf, n);
  if (document.body.dataset.layout !== '3d' && $('#show-scan').checked) {   // live scan overlay on the 2D map
    const xy = new Float32Array(n * 2);
    for (let k = 0; k < n; k++) { xy[k * 2] = scanBuf[k * 3]; xy[k * 2 + 1] = scanBuf[k * 3 + 1]; }
    map2d.setScan(xy);
  }
  const now = performance.now(); st.scanTimes.push(now); while (st.scanTimes.length > 20) st.scanTimes.shift();
  st.lastScanAt = now; st.lastScanN = n;
}, { throttle_rate: 100, queue_length: 1 });

setInterval(() => {
  const age = performance.now() - st.lastScanAt;
  if (!st.lastScanAt || age > 2000) { setLink('lidar', 'bad', 'No lidar scans on ' + CONFIG.topics.scan[0]); }
  else {
    const t = st.scanTimes, hz = t.length > 1 ? (t.length - 1) * 1000 / (t[t.length - 1] - t[0]) : 0;
    setLink('lidar', 'ok', `Lidar ${hz.toFixed(1)} Hz, ${st.lastScanN} points`);
  }
  $('#tf-mode').textContent = st.tfMode || 'Waiting for scans';
  $('#hit-count').textContent = `${view.used.toLocaleString()} wall cells`;
}, 500);

// goals: from any page or tool, shown on both views
ros.subscribe(...CONFIG.topics.goal, (msg) => {
  const p = msg.pose.position; view.setGoal({ x: p.x, y: p.y }); map2d.setGoal({ x: p.x, y: p.y });
  $('#goal').textContent = `Goal: x ${p.x.toFixed(2)}, y ${p.y.toFixed(2)} m`;
}, { queue_length: 1 });
view.addEventListener('reached', () => { $('#goal').textContent = 'Goal reached'; map2d.setGoal(null); });

function sendGoal(x, y, cellValue) {
  if (cellValue !== undefined && cellValue >= 65) { toast('That point is an obstacle on the map.'); return; }
  if (!publishGoal(ros, x, y, view.pose)) { toast('Goal not sent: ROS is offline.', 'bad'); return; }
  view.setGoal({ x, y }); map2d.setGoal({ x, y });
  $('#goal').textContent = `Goal: x ${x.toFixed(2)}, y ${y.toFixed(2)} m${cellValue !== undefined && cellValue < 0 ? ' (unexplored)' : ''}`;
}
view.addEventListener('click-ground', (e) => {
  const { x, y } = e.detail;
  let cell;
  if (map2d.info) { const g = map2d.worldToImage(x, y); cell = map2d._cellValue(g.gx, g.gy); }
  sendGoal(x, y, cell);
});
map2d.addEventListener('goal', (e) => sendGoal(e.detail.x, e.detail.y, e.detail.unknown ? -1 : 0));
map2d.addEventListener('rejected', (e) => toast(e.detail));

// layout: 3D only, split (3D + SLAM map) or SLAM map only
function setLayout(which) {
  document.body.dataset.layout = which;
  for (const btn of document.querySelectorAll('.layout-switch [data-layout]')) btn.setAttribute('aria-pressed', String(btn.dataset.layout === which));
  if (which === '3d') map2d.setScan(null);
  requestAnimationFrame(() => { if (!map2d.followRobot) map2d.fit(); });
}
for (const btn of document.querySelectorAll('.layout-switch [data-layout]')) btn.addEventListener('click', () => setLayout(btn.dataset.layout));
$('#show-scan').addEventListener('change', (e) => { if (!e.target.checked) map2d.setScan(null); });

// save the SLAM map through slam_toolbox (writes <name>.pgm + <name>.yaml on the robot)
$('#save-map').addEventListener('click', async () => {
  const name = $('#map-name').value.trim().replace(/[^A-Za-z0-9_./~-]/g, '_') || 'robie_map';
  $('#save-result').textContent = 'Saving…';
  try {
    const r = await ros.callService('/slam_toolbox/save_map', 'slam_toolbox/srv/SaveMap', { name: { data: name } });
    const ok = !r || r.result === 0 || r.result === undefined;
    $('#save-result').textContent = ok ? `Saved "${name}" (.pgm + .yaml, in SLAM Toolbox's working folder unless you gave a full path).`
                                       : `SLAM Toolbox refused (code ${r.result}: ${r.result === 1 ? 'no map received yet' : 'save failed'}).`;
  } catch (err) {
    $('#save-result').textContent = `Not saved: ${err.message}. Is SLAM Toolbox running?`;
  }
});

// controls
function setClickToMove(on) {
  view.clickToMove = on; map2d.setManual(on);
  $('#click-move').checked = on;
  document.body.classList.toggle('is-click-move', on);
  $('#click-hint').textContent = on ? 'Click the 3D floor or the SLAM map to send R.O.B.I.E. there.' : 'Turn on to send R.O.B.I.E. to a point by clicking.';
  $('#slam-hint').textContent = on ? 'Click a free (light) cell to send a goal. Drag to pan, scroll to zoom.' : 'Drag to pan, scroll to zoom.';
}
$('#click-move').addEventListener('change', (e) => setClickToMove(e.target.checked));
$('#show-hits').addEventListener('change', (e) => { view.hits.visible = e.target.checked; });
$('#show-walls').addEventListener('change', (e) => { view.mapWalls.visible = e.target.checked; });
$('#show-scan').addEventListener('change', (e) => { view.scan.visible = e.target.checked; });
$('#show-trail').addEventListener('change', (e) => { view.trail.visible = e.target.checked; });
$('#wall-h').addEventListener('input', (e) => { const h = parseFloat(e.target.value); $('#wall-h-val').textContent = `${h.toFixed(1)} m`; view.setWallHeight(h); });
$('#clear-hits').addEventListener('click', () => view.clearHits());
$('#follow').addEventListener('change', (e) => view.setFollow(e.target.checked));
$('#slam-follow').addEventListener('change', (e) => { map2d.followRobot = e.target.checked; if (!e.target.checked) map2d.fit(); });
$('#slam-fit').addEventListener('click', () => { $('#slam-follow').checked = false; map2d.followRobot = false; map2d.fit(); });
$('#top-view').addEventListener('click', () => { $('#follow').checked = false; view.setFollow(false); view.topView(); });
$('#reset-view').addEventListener('click', () => view.resetView());

// STOP / RESET (same paths as the dashboard)
async function triggerStop(source) {
  $('#stop-btn').classList.add('is-firing');
  const { path, ms } = await sendStop(ros);
  $('#stop-btn').classList.remove('is-firing');
  setClickToMove(false);
  if (path) { st.stopLatched = true; $('#stop-result').textContent = `Stopped via ${path} (${ms} ms)`; }
  else { $('#stop-result').textContent = 'STOP could not reach the robot'; toast('Stop could not reach the robot. Cut power if it is still moving.', 'bad'); }
}
$('#stop-btn').addEventListener('click', () => triggerStop('button'));
window.addEventListener('keydown', (e) => {
  if (e.target.matches('input, textarea, select')) return;
  if (e.code === 'Space' || e.code === 'Escape') { e.preventDefault(); triggerStop(e.code); }
});
holdButton($('#reset-btn'), 1000, async () => {
  const ok = await sendReset();
  $('#stop-result').textContent = ok ? 'Reset sent' : 'Reset could not reach the safety node';
  if (ok) st.stopLatched = false;
});

window.__robie = { map2d, view };   // handy for debugging in the browser console
ros.connect();
setClickToMove(false);
setLayout(document.body.dataset.layout || 'split');
