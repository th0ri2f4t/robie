// R.O.B.I.E. bg3d v7 — shared rover, trail, beacon, pulses, scan walls
// Rotation fix: +PI/2 offset aligns model's +Z nose with ROS +X forward
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
import { buildMecanumRover } from './rover3d.js';

export function initBG3D(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return null;

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x0b0716, 8, 24);

  const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.1, 80);
  camera.position.set(-8, 4.5, 0);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  container.appendChild(renderer.domElement);

  scene.add(new THREE.GridHelper(24, 24, 0x3a2d5a, 0x1f1638));
  scene.add(new THREE.HemisphereLight(0x4c3a6e, 0x0b0716, 0.95));
  const key = new THREE.DirectionalLight(0xd8c7ff, 1.7); key.position.set(4, 6, 3); scene.add(key);
  const rim = new THREE.PointLight(0xf472b6, 1.1, 20); rim.position.set(-4, 2.5, -4); scene.add(rim);

  const rover = buildMecanumRover(THREE);
  rover.position.set(2, 0, 0);
  scene.add(rover);

  // trail
  const trailMax = 400;
  const trailGeo = new THREE.BufferGeometry();
  const trailPos = new Float32Array(trailMax * 3);
  trailGeo.setAttribute('position', new THREE.BufferAttribute(trailPos, 3));
  const trail = new THREE.Line(trailGeo, new THREE.LineBasicMaterial({ color: 0xc4b5fd, transparent: true, opacity: 0.5 }));
  let trailCount = 0;
  function pushTrail(x, z) {
    if (trailCount >= trailMax) return;
    trailPos[trailCount * 3] = x;
    trailPos[trailCount * 3 + 1] = 0.05;
    trailPos[trailCount * 3 + 2] = z;
    trailCount++;
    trailGeo.setDrawRange(0, trailCount);
  }
  scene.add(trail);

  // beacon
  const beacon = new THREE.Group();
  const bCone = new THREE.Mesh(new THREE.ConeGeometry(0.18, 0.6, 16),
    new THREE.MeshStandardMaterial({ color: 0xfbbf24, emissive: 0xfbbf24, emissiveIntensity: 1.4, transparent: true, opacity: 0.9 }));
  bCone.position.y = 0.3;
  const bRing = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.42, 32),
    new THREE.MeshBasicMaterial({ color: 0xfbbf24, transparent: true, opacity: 0.7, side: THREE.DoubleSide }));
  bRing.rotation.x = -Math.PI / 2; bRing.position.y = 0.02;
  beacon.add(bCone, bRing); beacon.visible = false; scene.add(beacon);

  // pulses
  const pulses = [];
  function pulse(type, x, y) {
    const col = type === 'leak' ? 0x34d399 : 0xf472b6;
    const m = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.4, 32),
      new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.9, side: THREE.DoubleSide }));
    m.rotation.x = -Math.PI / 2; m.position.set(x, 0.02, -y);
    scene.add(m); pulses.push({ m, t0: performance.now() });
  }

  // scan walls (shared with SLAM page)
  const N = 200, RES = 0.1;
  const OX = -N * RES / 2, OY = -N * RES / 2;
  const gridArr = new Uint8Array(N * N);
  const canvas = document.createElement('canvas');
  canvas.width = N; canvas.height = N;
  const gctx = canvas.getContext('2d');
  const gimg = gctx.createImageData(N, N);
  const gtex = new THREE.CanvasTexture(canvas);
  gtex.magFilter = THREE.NearestFilter;
  const gplane = new THREE.Mesh(
    new THREE.PlaneGeometry(N * RES, N * RES),
    new THREE.MeshBasicMaterial({ map: gtex, transparent: true })
  );
  gplane.rotation.x = -Math.PI / 2; gplane.position.y = 0.01;
  scene.add(gplane);

  const WALL_CAP = 8000;
  const walls = new THREE.InstancedMesh(new THREE.BoxGeometry(RES, 0.35, RES),
    new THREE.MeshStandardMaterial({ color: 0xcdb4f6, roughness: 0.6, emissive: 0x6d28d9, emissiveIntensity: 0.25 }), WALL_CAP);
  walls.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  walls.count = 0; scene.add(walls);
  const occupied = [];

  const mtx = new THREE.Matrix4();
  function rebuildWalls() {
    const n = Math.min(occupied.length, WALL_CAP);
    for (let i = 0; i < n; i++) {
      const idx = occupied[i];
      const cx = idx % N, cy = Math.floor(idx / N);
      mtx.makeTranslation(OX + cx * RES + RES / 2, 0.175, -(OY + cy * RES + RES / 2));
      walls.setMatrixAt(i, mtx);
    }
    walls.count = n;
    walls.instanceMatrix.needsUpdate = true;
  }

  function paintGrid() {
    const d = gimg.data;
    for (let i = 0; i < N * N; i++) {
      const v = gridArr[i], o = i * 4;
      if (v === 0) { d[o] = 0; d[o + 1] = 0; d[o + 2] = 0; d[o + 3] = 0; }
      else if (v === 1) { d[o] = 120; d[o + 1] = 100; d[o + 2] = 180; d[o + 3] = 26; }
      else { d[o] = 205; d[o + 1] = 180; d[o + 2] = 246; d[o + 3] = 235; }
    }
    gctx.putImageData(gimg, 0, 0);
    gtex.needsUpdate = true;
  }

  let pose = null;
  function integrate(b64) {
    if (!pose) return;
    const bin = atob(b64);
    const r = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) r[i] = bin.charCodeAt(i);
    for (let a = 0; a < 360; a++) {
      const range = r[a] / 10;
      const wa = pose.th + a * Math.PI / 180;
      const dx = Math.cos(wa), dy = Math.sin(wa);
      const steps = Math.floor(range / RES);
      for (let s = 1; s < steps; s++) {
        const cx = Math.floor((pose.x + dx * s * RES - OX) / RES);
        const cy = Math.floor((pose.y + dy * s * RES - OY) / RES);
        if (cx < 0 || cy < 0 || cx >= N || cy >= N) continue;
        const idx = cy * N + cx;
        if (gridArr[idx] === 0) gridArr[idx] = 1;
      }
      if (range < 7.9) {
        const cx = Math.floor((pose.x + dx * range - OX) / RES);
        const cy = Math.floor((pose.y + dy * range - OY) / RES);
        if (cx >= 0 && cy >= 0 && cx < N && cy < N) {
          const idx = cy * N + cx;
          if (gridArr[idx] !== 2) { gridArr[idx] = 2; occupied.push(idx); }
        }
      }
    }
    paintGrid();
    rebuildWalls();
  }

  const target = { x: 0, y: 0, th: 0 };
  let live = false, idleT = 0, prevBg = null;
  const camTarget = new THREE.Vector3();

  const api = {
    setPose(x, y, th) {
      target.x = x; target.y = y; target.th = th;
      live = true; pose = { x, y, th };
      pushTrail(x, -y);
    },
    setWaypoint(x, y) { beacon.position.set(x, 0, -y); beacon.visible = true; },
    scanData(b64) { integrate(b64); },
    pulse
  };

  const clock = new THREE.Clock();
  let last = 0, acc = 0;
  function tick(t) {
    requestAnimationFrame(tick);
    if (document.hidden) return;
    const dt = clock.getDelta();
    acc += t - last; last = t;
    if (acc < 33) return; acc = 0;

    if (live) {
      rover.position.x += (target.x - rover.position.x) * Math.min(1, dt * 4);
      rover.position.z += (-target.y - rover.position.z) * Math.min(1, dt * 4);
      // +PI/2 offset: model's +Z nose aligns with ROS +X forward
      rover.rotation.y += ((target.th + Math.PI/2) - rover.rotation.y) * Math.min(1, dt * 4);
    } else {
      idleT += dt * 0.35;
      rover.position.x = Math.sin(idleT) * 3.2;
      rover.position.z = Math.sin(idleT * 2) * 1.8;
      rover.rotation.y = Math.atan2(Math.cos(idleT) * 3.2, -Math.cos(idleT * 2) * 3.6);
      pushTrail(rover.position.x, rover.position.z);
    }
    if (prevBg && rover.userData.wheels) {
      const d = Math.hypot(rover.position.x - prevBg.x, rover.position.z - prevBg.z);
      for (const w of rover.userData.wheels) w.rotation.x += d / 0.26;
    }
    prevBg = { x: rover.position.x, z: rover.position.z };
    const now = performance.now();
    if (beacon.visible) { const s = 1 + Math.sin(now / 300) * 0.15; bRing.scale.set(s, s, 1); }
    for (let i = pulses.length - 1; i >= 0; i--) {
      const age = (now - pulses[i].t0) / 2000;
      if (age >= 1) { scene.remove(pulses[i].m); pulses.splice(i, 1); continue; }
      const s = 1 + age * 6; pulses[i].m.scale.set(s, s, 1);
      pulses[i].m.material.opacity = 0.9 * (1 - age);
    }
    // Camera follows rover from behind, smoothly lerping
    camTarget.set(rover.position.x - 8, 4.5, rover.position.z);
    camera.position.lerp(camTarget, 0.05);
    camera.lookAt(rover.position.x, 0.5, rover.position.z);
    renderer.render(scene, camera);
  }
  requestAnimationFrame(tick);

  addEventListener('resize', () => {
    camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  });

  return api;
}
