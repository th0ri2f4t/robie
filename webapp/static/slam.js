// R.O.B.I.E. SLAM page - live 3D occupancy map from LiDAR scans + click-to-navigate
import { buildMecanumRover } from './rover3d.js';
try {
  const THREE = await import('three');
  const $ = id => document.getElementById(id);

  const canvas = $('slam3d');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.setSize(innerWidth, innerHeight);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0716);
  scene.fog = new THREE.FogExp2(0x0b0716, 0.035);
  const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 120);
  let viewMode = 'chase';

  scene.add(new THREE.HemisphereLight(0x4c3a6e, 0x0b0716, 0.9));
  const key = new THREE.DirectionalLight(0xd8c7ff, 1.4); key.position.set(6, 10, 4); scene.add(key);

  // occupancy grid (16 m x 16 m at 0.1 m)
  const RES = 0.1, N = 160, OX = -8, OY = -8;
  const grid = new Uint8Array(N * N);
  const gcan = document.createElement('canvas'); gcan.width = N; gcan.height = N;
  const gctx = gcan.getContext('2d');
  const gimg = gctx.createImageData(N, N);
  const gtex = new THREE.CanvasTexture(gcan);
  gtex.magFilter = THREE.NearestFilter;
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(N * RES, N * RES),
    new THREE.MeshBasicMaterial({ map: gtex, transparent: true }));
  floor.rotation.x = -Math.PI / 2; floor.position.set(0, 0.02, 0); scene.add(floor);
  const base = new THREE.GridHelper(60, 60, 0x2c2340, 0x171126);
  base.material.transparent = true; base.material.opacity = 0.4; scene.add(base);

  // extruded wall cells
  const WALL_CAP = 8000;
  const walls = new THREE.InstancedMesh(new THREE.BoxGeometry(RES, 0.35, RES),
    new THREE.MeshStandardMaterial({ color: 0xcdb4f6, roughness: 0.6, emissive: 0x6d28d9, emissiveIntensity: 0.25 }), WALL_CAP);
  walls.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  walls.count = 0; scene.add(walls);
  const occupied = [];

  // live scan fan
  const fanPos = new Float32Array(360 * 6);
  const fanGeo = new THREE.BufferGeometry();
  fanGeo.setAttribute('position', new THREE.BufferAttribute(fanPos, 3));
  const fan = new THREE.LineSegments(fanGeo, new THREE.LineBasicMaterial({ color: 0x34d399, transparent: true, opacity: 0.3 }));
  scene.add(fan);

  const rover = buildMecanumRover(THREE);
  scene.add(rover);
  let pose = { x: 2, y: 0, th: 0 }, hasPose = false, prev = null;

  // target beacon + dashed link line
  const beacon = new THREE.Group();
  const bCone = new THREE.Mesh(new THREE.ConeGeometry(0.18, 0.6, 16),
    new THREE.MeshStandardMaterial({ color: 0xfbbf24, emissive: 0xfbbf24, emissiveIntensity: 1.4, transparent: true, opacity: 0.9 }));
  bCone.rotation.x = Math.PI; bCone.position.y = 0.7; beacon.add(bCone);
  const bRing = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.42, 32),
    new THREE.MeshBasicMaterial({ color: 0xfbbf24, transparent: true, opacity: 0.7, side: THREE.DoubleSide }));
  bRing.rotation.x = -Math.PI / 2; bRing.position.y = 0.05; beacon.add(bRing);
  beacon.visible = false; scene.add(beacon);
  const linkLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
    new THREE.LineDashedMaterial({ color: 0xfbbf24, dashSize: 0.25, gapSize: 0.15, transparent: true, opacity: 0.8 }));
  linkLine.visible = false; scene.add(linkLine);
  let target = null;

  // click-to-navigate (raycast onto floor plane)
  const ray = new THREE.Raycaster();
  const gplane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  canvas.addEventListener('pointerdown', e => {
    ray.setFromCamera({ x: (e.clientX / innerWidth) * 2 - 1, y: -(e.clientY / innerHeight) * 2 + 1 }, camera);
    const hit = new THREE.Vector3();
    if (ray.ray.intersectPlane(gplane, hit)) {
      target = { x: hit.x, y: -hit.z };
      beacon.position.set(hit.x, 0, hit.z); beacon.visible = true;
      linkLine.visible = true;
      send(`W,${target.x.toFixed(2)},${target.y.toFixed(2)}`);
      $('hudTarget').textContent = `x ${target.x.toFixed(2)} · y ${target.y.toFixed(2)}`;
    }
  });

  // websocket: P pose, T safety, Z scan (same format the real-robot bridge will use)
  let ws, estop = false, scans = 0;
  function send(d) { if (ws && ws.readyState === 1) ws.send(d); }
  function connect() {
    ws = new WebSocket(`ws://${location.host}/ws`);
    ws.onopen = () => { $('connDot').classList.add('on'); $('connText').textContent = 'live'; };
    ws.onclose = () => { $('connDot').classList.remove('on'); $('connText').textContent = 'offline'; setTimeout(connect, 2000); };
    ws.onmessage = ev => handle(ev.data);
  }
  function handle(msg) {
    const p = msg.split(',');
    if (p[0] === 'P') { pose = { x: +p[1], y: +p[2], th: +p[3] }; hasPose = true; }
    else if (p[0] === 'T') { estop = p[1] === '1'; $('estopState').textContent = estop ? 'ENGAGED' : 'CLEAR'; }
    else if (p[0] === 'Z') { scans++; integrate(p[1]); if (window.ROBIE_BG3D) window.ROBIE_BG3D.scanData(p[1]); }
  }
  function integrate(b64) {
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
        if (grid[idx] === 0) grid[idx] = 1;
      }
      if (range < 7.9) {
        const cx = Math.floor((pose.x + dx * range - OX) / RES);
        const cy = Math.floor((pose.y + dy * range - OY) / RES);
        if (cx >= 0 && cy >= 0 && cx < N && cy < N) {
          const idx = cy * N + cx;
          if (grid[idx] !== 2) { grid[idx] = 2; occupied.push(idx); }
        }
        fanPos[a * 6 + 0] = pose.x; fanPos[a * 6 + 1] = 0.06; fanPos[a * 6 + 2] = -pose.y;
        fanPos[a * 6 + 3] = pose.x + dx * range; fanPos[a * 6 + 4] = 0.06; fanPos[a * 6 + 5] = -(pose.y + dy * range);
      }
    }
    fanGeo.attributes.position.needsUpdate = true;
    paintGrid();
    rebuildWalls();
    $('hudScans').textContent = scans + ' scans · ' + occupied.length + ' wall cells';
  }
  function paintGrid() {
    const d = gimg.data;
    for (let i = 0; i < N * N; i++) {
      const v = grid[i], o = i * 4;
      if (v === 0) { d[o] = 0; d[o + 1] = 0; d[o + 2] = 0; d[o + 3] = 0; }
      else if (v === 1) { d[o] = 120; d[o + 1] = 100; d[o + 2] = 180; d[o + 3] = 26; }
      else { d[o] = 205; d[o + 1] = 180; d[o + 2] = 246; d[o + 3] = 235; }
    }
    gctx.putImageData(gimg, 0, 0);
    gtex.needsUpdate = true;
  }
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

  // HUD controls
  $('btnView').addEventListener('click', () => {
    viewMode = viewMode === 'chase' ? 'top' : 'chase';
    $('btnView').textContent = viewMode === 'chase' ? '◱ TOP VIEW' : '◲ CHASE VIEW';
  });
  $('btnAuto').addEventListener('click', () => send('A,1'));
  $('btnStop').addEventListener('click', () => {
    send('D,0,0,0'); target = null; beacon.visible = false; linkLine.visible = false;
    $('hudTarget').textContent = '—'; $('hudDist').textContent = '—';
  });
  $('btnEstop').addEventListener('click', () => {
    estop = !estop; send(`E,${estop ? 1 : 0}`);
    $('btnEstop').classList.toggle('active', estop);
    $('estopState').textContent = estop ? 'ENGAGED' : 'CLEAR';
  });

  let last = 0, acc = 0;
  const clock = new THREE.Clock();
  const camTarget = new THREE.Vector3();
  function tick(t) {
    requestAnimationFrame(tick);
    if (document.hidden) return;
    const dt = clock.getDelta();
    acc += t - last; last = t;
    if (acc < 33) return; acc = 0;
    if (hasPose) {
      if (prev && rover.userData.wheels) {
        const dist = Math.hypot(pose.x - prev.x, pose.y - prev.y);
        for (const w of rover.userData.wheels) w.rotation.x += dist / 0.26;
      }
      prev = { x: pose.x, y: pose.y };
      rover.position.x += (pose.x - rover.position.x) * Math.min(1, dt * 6);
      rover.position.z += (-pose.y - rover.position.z) * Math.min(1, dt * 6);
      rover.rotation.y += ((pose.th + Math.PI/2) - rover.rotation.y) * Math.min(1, dt * 6);
      $('hudPose').textContent = `x ${pose.x.toFixed(2)} · y ${pose.y.toFixed(2)} · θ ${(pose.th * 57.3).toFixed(0)}°`;
      if (target) {
        linkLine.geometry.setFromPoints([
          new THREE.Vector3(rover.position.x, 0.1, rover.position.z),
          new THREE.Vector3(target.x, 0.1, -target.y)]);
        linkLine.computeLineDistances();
        $('hudDist').textContent = Math.hypot(target.x - pose.x, target.y - pose.y).toFixed(2) + ' m';
      }
    }
    const now = performance.now();
    if (beacon.visible) { const s = 1 + Math.sin(now / 300) * 0.15; bRing.scale.set(s, s, 1); }
    if (viewMode === 'chase') {
      const fx = Math.cos(rover.rotation.y), fz = Math.sin(rover.rotation.y);
      camTarget.set(rover.position.x - fx * 4.2, 2.6, rover.position.z - fz * 4.2);
      camera.position.lerp(camTarget, 0.08);
      camera.lookAt(rover.position.x, 0.6, rover.position.z);
    } else {
      camTarget.set(rover.position.x, 13, rover.position.z + 0.001);
      camera.position.lerp(camTarget, 0.12);
      camera.lookAt(rover.position.x, 0, rover.position.z);
    }
    renderer.render(scene, camera);
  }
  requestAnimationFrame(tick);

  addEventListener('resize', () => {
    camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  });

  connect();
} catch (err) {
  console.warn('[slam] page disabled:', err);
}