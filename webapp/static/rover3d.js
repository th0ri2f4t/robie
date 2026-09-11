// R.O.B.I.E. shared 3D rover builder (mecanum wheels) - imported by bg3d.js and slam.js
export function buildMecanumRover(THREE) {
  const g = new THREE.Group();
  const body = new THREE.MeshStandardMaterial({ color: 0xcdb4f6, metalness: 0.25, roughness: 0.45, emissive: 0x6d28d9, emissiveIntensity: 0.18 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x241b3a, roughness: 0.6 });
  const rollerMat = new THREE.MeshStandardMaterial({ color: 0x8f7bb8, roughness: 0.85 });
  const chassis = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.42, 1.5), body);
  chassis.position.y = 0.5; g.add(chassis);
  const head = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.42, 0.5), body);
  head.position.set(0, 0.95, 0.45); g.add(head);
  const eyeMat = new THREE.MeshStandardMaterial({ color: 0x1a1030, emissive: 0x9ff3ff, emissiveIntensity: 2.6 });
  for (const ex of [-0.17, 0.17]) {
    const eye = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.11, 0.06, 20), eyeMat);
    eye.rotation.x = Math.PI / 2; eye.position.set(ex, 0.95, 0.71); g.add(eye);
  }
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.5), body);
  mast.position.set(0, 1.35, -0.3); g.add(mast);
  const lidar = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.08, 24),
    new THREE.MeshStandardMaterial({ color: 0x241b3a, emissive: 0x34d399, emissiveIntensity: 0.8 }));
  lidar.position.set(0, 1.62, -0.3); g.add(lidar);
  const glow = new THREE.PointLight(0xc4b5fd, 0.9, 6); glow.position.set(0, 1.1, 0); g.add(glow);

  const wheels = [];
  function mecanum(rightHanded) {
    const w = new THREE.Group();
    const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.14, 18), dark);
    hub.rotation.z = Math.PI / 2; w.add(hub);
    const n = 10, R = 0.2;
    for (let i = 0; i < n; i++) {
      const th = (i / n) * Math.PI * 2;
      const tangent = new THREE.Vector3(0, -Math.sin(th), Math.cos(th));
      const axis = new THREE.Vector3(1, 0, 0).addScaledVector(tangent, rightHanded ? 1 : -1).normalize();
      const roller = new THREE.Mesh(new THREE.CylinderGeometry(0.065, 0.065, 0.12, 10), rollerMat);
      roller.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), axis);
      roller.position.set(0, Math.cos(th) * R, Math.sin(th) * R);
      w.add(roller);
    }
    return w;
  }
  for (const [sx, sz, rh] of [[-0.62, -0.5, false], [0.62, -0.5, true], [-0.62, 0.5, true], [0.62, 0.5, false]]) {
    const w = mecanum(rh);
    w.position.set(sx, 0.24, sz);
    g.add(w); wheels.push(w);
  }
  g.userData.wheels = wheels;
  g.userData.wheelRadius = 0.26;
  return g;
}