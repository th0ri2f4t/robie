// 3D view of R.O.B.I.E. on the SLAM map. World frame = ROS map frame (Z up, metres).
// Model load order: robie_cad.glb (coloured) -> robie_cad.stl -> primitive stand-in.
// Both model files are in the ROS base_link frame: x forward, y left, z up, origin on the ground.

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

THREE.Object3D.DEFAULT_UP.set(0, 0, 1);

export class CadViewer {
  constructor(container, { modelBase = '/static/models/robie_cad', onStatus = () => {} } = {}) {
    this.container = container;
    this.onStatus = onStatus;
    this.target = { x: 0, y: 0, yaw: 0, valid: false };
    this.follow = true;
    this.mapVersion = -1;

    const r = this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    r.outputColorSpace = THREE.SRGBColorSpace;
    r.setClearColor(0x140f24);
    container.appendChild(r.domElement);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(40, 1, 0.01, 200);
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(-0.9, -0.9, 0.7);

    this.controls = new OrbitControls(this.camera, r.domElement);
    this.controls.enableDamping = true;
    this.controls.target.set(0, 0, 0.08);
    this.controls.maxPolarAngle = Math.PI * 0.49;
    this.controls.addEventListener('start', () => { this._userOrbiting = true; });
    this.controls.addEventListener('end', () => { this._userOrbiting = false; });

    this.scene.add(new THREE.HemisphereLight(0xf1e9ff, 0x1d1436, 1.1));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(2, -3, 5);
    this.scene.add(sun);

    this.grid = new THREE.GridHelper(20, 40, 0x4a3b78, 0x2a2048);
    this.grid.rotation.x = Math.PI / 2;
    this.scene.add(this.grid);

    this.mapMesh = null;
    this.robot = new THREE.Group();
    this.scene.add(this.robot);

    this._loadModel(modelBase);
    new ResizeObserver(() => this._resize()).observe(container);
    this._resize();
    this.clock = new THREE.Clock();
    r.setAnimationLoop(() => this._tick());
  }

  async _loadModel(base) { this.onStatus(await loadRobotModel(this.robot, base)); }

  // map: SlamMap instance (uses its 1 px-per-cell canvas as a texture)
  updateMap(slam) {
    if (!slam.info || slam.mapVersion === this.mapVersion) return;
    this.mapVersion = slam.mapVersion;
    const i = slam.info;
    const w = i.width * i.resolution, h = i.height * i.resolution;
    if (!this.mapMesh || this.mapMesh.userData.w !== w || this.mapMesh.userData.h !== h) {
      if (this.mapMesh) { this.scene.remove(this.mapMesh); this.mapMesh.geometry.dispose(); this.mapMesh.material.map.dispose(); }
      const tex = new THREE.CanvasTexture(slam.grid);
      tex.magFilter = THREE.NearestFilter; tex.minFilter = THREE.LinearFilter; tex.colorSpace = THREE.SRGBColorSpace;
      const mat = new THREE.MeshBasicMaterial({ map: tex });
      this.mapMesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
      this.mapMesh.userData = { w, h };
      this.scene.add(this.mapMesh);
      this.grid.visible = false;
    }
    this.mapMesh.material.map.needsUpdate = true;
    // plane centre in map frame (origin is the bottom-left cell corner, rotated by origin yaw)
    const c = Math.cos(i.oyaw), s = Math.sin(i.oyaw);
    this.mapMesh.position.set(i.ox + c * w / 2 - s * h / 2, i.oy + s * w / 2 + c * h / 2, -0.001);
    this.mapMesh.rotation.set(0, 0, i.oyaw);
  }

  setPose(x, y, yaw) {
    const first = !this.target.valid;
    this.target = { x, y, yaw, valid: true };
    if (first) { this.robot.position.set(x, y, 0); this.robot.rotation.set(0, 0, yaw); this._recentre(true); }
  }

  setFollow(on) { this.follow = on; if (on) this._recentre(true); }

  _recentre(jump) {
    const p = this.robot.position, t = this.controls.target;
    const dx = p.x - t.x, dy = p.y - t.y;
    t.set(p.x, p.y, 0.08);
    if (jump) this.camera.position.add(new THREE.Vector3(dx, dy, 0));
  }

  _tick() {
    const dt = Math.min(this.clock.getDelta(), 0.1);
    if (this.target.valid) {
      const k = 1 - Math.exp(-dt * 12);           // smooths 10 Hz pose updates
      const p = this.robot.position;
      const ox = p.x, oy = p.y;
      p.x += (this.target.x - p.x) * k;
      p.y += (this.target.y - p.y) * k;
      let dyaw = this.target.yaw - this.robot.rotation.z;
      dyaw = Math.atan2(Math.sin(dyaw), Math.cos(dyaw));
      this.robot.rotation.z += dyaw * k;
      if (this.follow && !this._userOrbiting) {
        this.camera.position.x += p.x - ox; this.camera.position.y += p.y - oy;
        this.controls.target.set(p.x, p.y, 0.08);
      }
    }
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  _resize() {
    const w = this.container.clientWidth, h = this.container.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }
}

// Load the R.O.B.I.E. model into a group: robie_cad.glb (coloured) -> robie_cad.stl -> stand-in.
// Returns a short status sentence for the UI.
export async function loadRobotModel(group, base = '/static/models/robie_cad') {
  try {
    const gltf = await new GLTFLoader().loadAsync(`${base}.glb`);
    group.add(gltf.scene);
    return 'Showing the R.O.B.I.E. CAD model.';
  } catch (e) { console.warn('GLB not loaded, trying STL', e); }
  try {
    const geo = await new STLLoader().loadAsync(`${base}.stl`);
    geo.computeVertexNormals();
    group.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: 0xf2b705, roughness: 0.5 })));
    return 'Showing the CAD model from STL (single colour).';
  } catch (e) { console.warn('STL not loaded, using stand-in', e); }
  group.add(buildStandIn());
  return 'Model file not found: showing a simplified stand-in. Put robie_cad.glb in static/models.';
}

// Simplified stand-in used only if both model files are missing.
function buildStandIn() {
  const g = new THREE.Group();
  const mat = (c) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.6 });
  const box = (sx, sy, sz, x, y, z, c) => { const m = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), mat(c)); m.position.set(x, y, z); g.add(m); };
  const cyl = (r, h, x, y, z, c, axis = 'z') => {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 24), mat(c));
    if (axis === 'z') m.rotation.x = Math.PI / 2; if (axis === 'x') m.rotation.z = Math.PI / 2;
    m.position.set(x, y, z); g.add(m);
  };
  box(0.25, 0.18, 0.003, 0, 0, 0.018, 0xececee);
  box(0.262, 0.19, 0.075, 0, 0, 0.087, 0xfac20d);
  box(0.24, 0.16, 0.028, 0, 0, 0.138, 0x1c1c1f);
  for (const x of [0.082, -0.082]) for (const y of [0.0845, -0.0845]) cyl(0.026, 0.025, x, y, 0.026, 0x389e40, 'y');
  cyl(0.035, 0.035, -0.052, 0, 0.19, 0x2e2e33);
  box(0.004, 0.025, 0.024, 0.115, 0, 0.175, 0x147333);
  for (const z of [0.089, 0.113]) cyl(0.0098, 0.014, 0.125, 0, z, 0xbebebe, 'x');
  return g;
}
