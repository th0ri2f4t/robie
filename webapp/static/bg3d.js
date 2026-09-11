// R.O.B.I.E. bg3d v4 - mecanum rover (shared builder), lavender trail, beacon + pulses
import { buildMecanumRover } from './rover3d.js';
try {
  const THREE = await import('three');
  const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');

  const canvas = document.getElementById('bg3d');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.setSize(innerWidth, innerHeight);

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x0b0716, 0.05);
  const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.1, 100);
  camera.position.set(0, 3.6, 7.5);

  const grid = new THREE.GridHelper(60, 60, 0x2c2340, 0x171126);
  grid.material.transparent = true; grid.material.opacity = 0.55;
  scene.add(grid);

  scene.add(new THREE.HemisphereLight(0x4c3a6e, 0x0b0716, 0.95));
  const key = new THREE.DirectionalLight(0xd8c7ff, 1.7); key.position.set(4, 6, 3); scene.add(key);
  const rim = new THREE.PointLight(0xf472b6, 1.1, 20); rim.position.set(-4, 2.5, -4); scene.add(rim);

  const rover = new THREE.Group();
  scene.add(rover);
  rover.add(buildMecanumRover(THREE));
  new GLTFLoader().load('models/rover.glb',
    gltf => {
      rover.clear();
      const m = gltf.scene;
      const box = new THREE.Box3().setFromObject(m);
      const s = 1.6 / Math.max(box.getSize(new THREE.Vector3()).y, 0.001);
      m.scale.setScalar(s); m.position.y = -box.min.y * s;
      rover.add(m);
    },
    undefined, () => console.info('[bg3d] no models/rover.glb - mecanum fallback rover active'));

  // lavender trail ribbon
  const TRAIL_MAX = 400;
  const tPos = new Float32Array(TRAIL_MAX * 3);
  const tCol = new Float32Array(TRAIL_MAX * 3);
  let tN = 0;
  const trailGeo = new THREE.BufferGeometry();
  trailGeo.setAttribute('position', new THREE.BufferAttribute(tPos, 3));
  trailGeo.setAttribute('color', new THREE.BufferAttribute(tCol, 3));
  trailGeo.setDrawRange(0, 0);
  const trail = new THREE.Line(trailGeo, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.85 }));
  scene.add(trail);

  function pushTrail(x, z) {
    if (tN > 0) {
      const lx = tPos[(tN - 1) * 3], lz = tPos[(tN - 1) * 3 + 2];
      if (Math.hypot(x - lx, z - lz) < 0.05) return;
    }
    if (tN >= TRAIL_MAX) { tPos.copyWithin(0, 3); tN = TRAIL_MAX - 1; }
    tPos[tN * 3] = x; tPos[tN * 3 + 1] = 0.06; tPos[tN * 3 + 2] = z;
    tN++;
    for (let i = 0; i < tN; i++) {
      const f = i / Math.max(1, tN - 1);
      tCol[i * 3] = 0.72 * f; tCol[i * 3 + 1] = 0.55 * f; tCol[i * 3 + 2] = 0.98 * f;
    }
    trailGeo.attributes.position.needsUpdate = true;
    trailGeo.attributes.color.needsUpdate = true;
    trailGeo.setDrawRange(0, tN);
  }

  // waypoint beacon
  const beacon = new THREE.Group();
  const bCone = new THREE.Mesh(new THREE.ConeGeometry(0.18, 0.6, 16),
    new THREE.MeshStandardMaterial({ color: 0xfbbf24, emissive: 0xfbbf24, emissiveIntensity: 1.4, transparent: true, opacity: 0.9 }));
  bCone.rotation.x = Math.PI; bCone.position.y = 0.7;
  const bRing = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.42, 32),
    new THREE.MeshBasicMaterial({ color: 0xfbbf24, transparent: true, opacity: 0.7, side: THREE.DoubleSide }));
  bRing.rotation.x = -Math.PI / 2; bRing.position.y = 0.05;
  beacon.add(bCone, bRing); beacon.visible = false; scene.add(beacon);

  // detection event pulses
  const pulses = [];
  function pulse(type, x, y) {
    const col = type === 'leak' ? 0xfbbf24 : 0xf87171;
    const m = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.4, 32),
      new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.9, side: THREE.DoubleSide }));
    m.rotation.x = -Math.PI / 2; m.position.set(x, 0.07, -y);
    scene.add(m); pulses.push({ m, t0: performance.now() });
  }

  const target = { x: 0, y: 0, th: 0 };
  let live = false, idleT = 0, prevBg = null;
  window.ROBIE_BG3D = {
    setPose(x, y, th) { target.x = x; target.y = y; target.th = th; live = true; pushTrail(x, -y); },
    setWaypoint(x, y) { beacon.position.set(x, 0, -y); beacon.visible = true; },
    pulse
  };

  let last = 0, acc = 0;
  const clock = new THREE.Clock();
  function tick(t) {
    requestAnimationFrame(tick);
    if (document.hidden) return;
    const dt = clock.getDelta();
    acc += t - last; last = t;
    if (acc < 33) return; acc = 0;

    if (live) {
      rover.position.x += (target.x - rover.position.x) * Math.min(1, dt * 4);
      rover.position.z += (-target.y - rover.position.z) * Math.min(1, dt * 4);
      rover.rotation.y += (target.th - rover.rotation.y) * Math.min(1, dt * 4);
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
    camera.lookAt(rover.position.x * 0.35, 0.5, rover.position.z * 0.35);
    renderer.render(scene, camera);
  }
  requestAnimationFrame(tick);

  addEventListener('resize', () => {
    camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  });
} catch (err) {
  console.warn('[bg3d] background scene disabled:', err);
}