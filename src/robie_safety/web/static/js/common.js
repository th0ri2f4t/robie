// Shared by the dashboard (app.js) and the 3D view (explore.js): one config, one STOP path.
import { quaternionFromYaw, nowStamp } from './ros_bridge.js';

// The host is whatever address the page was opened from, so the same build works on
// ROBIE-NET (192.168.4.1), home Wi-Fi, a phone hotspot or localhost (mock robot).
const HOST = location.hostname || '192.168.4.1';

export const CONFIG = {
  rosbridgeUrl: `ws://${HOST}:9090`,
  safetyUrl: `http://${HOST}:8082`,          // safety_node: POST /estop, POST /reset
  cameraUrl: `http://${HOST}:8081/stream`,
  topics: {
    event:    ['/robie/event', 'std_msgs/msg/String'],
    safety:   ['/safety_state', 'std_msgs/msg/String'],
    map:      ['/map', 'nav_msgs/msg/OccupancyGrid'],
    pose:     ['/robot_pose', 'geometry_msgs/msg/PoseStamped'],
    motor:    ['/motor_enable', 'std_msgs/msg/Bool'],
    battery:  ['/robie/battery', 'std_msgs/msg/Float32'],      // optional
    cmdVel:   ['/cmd_vel', 'geometry_msgs/msg/Twist'],
    goal:     ['/move_goal', 'geometry_msgs/msg/PoseStamped'], // Nav2's default is /goal_pose
    scan:     ['/scan', 'sensor_msgs/msg/LaserScan'],          // RPLIDAR (sllidar_ros2 default)
    tf:       ['/tf', 'tf2_msgs/msg/TFMessage'],
    tfStatic: ['/tf_static', 'tf2_msgs/msg/TFMessage'],
  },
  fixedFrame: 'map',
  // Used only when TF from the lidar frame to the map is not available:
  // lidar pose relative to the robot (from the CAD: 52 mm behind centre, scan plane ~205 mm above the floor).
  // If the 3D walls appear mirrored front-to-back, set laserFallback.yaw to Math.PI (some RPLIDAR mounts).
  laserFallback: { x: -0.052, y: 0.0, z: 0.205, yaw: 0.0 },
  teleopHz: 10,
  maxEvents: 50,
};

export async function postWithTimeout(url, ms, opts = {}) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { method: 'POST', signal: ctl.signal, cache: 'no-store', ...opts }); }
  finally { clearTimeout(t); }
}

// STOP. Path 1: POST straight to safety_node (no-cors simple request, no preflight).
// Path 2: same-origin relay /api/estop. Path 3 (always): motor_enable=false over rosbridge.
// Returns { path, ms } with path = null if nothing reached the robot.
export async function sendStop(ros) {
  const t0 = performance.now();
  let path = null;
  try { await postWithTimeout(`${CONFIG.safetyUrl}/estop`, 400, { mode: 'no-cors' }); path = 'safety node'; }
  catch {
    try { const r = await postWithTimeout('/api/estop', 600); if (r.ok) path = 'web server relay'; } catch {}
  }
  const viaTopic = ros.publish(...CONFIG.topics.motor, { data: false });
  if (!path && viaTopic) path = 'ROS topic only';
  return { path, ms: Math.round(performance.now() - t0) };
}

// RESET only ever goes through safety_node (never motor_enable=true on a topic).
export async function sendReset() {
  try { await postWithTimeout(`${CONFIG.safetyUrl}/reset`, 600, { mode: 'no-cors' }); return true; }
  catch { try { return (await postWithTimeout('/api/reset', 800)).ok; } catch { return false; } }
}

// Goal in the map frame, facing from the robot towards the goal.
export function publishGoal(ros, x, y, fromPose) {
  const yaw = fromPose ? Math.atan2(y - fromPose.y, x - fromPose.x) : 0;
  return ros.publish(...CONFIG.topics.goal, {
    header: { stamp: nowStamp(), frame_id: CONFIG.fixedFrame },
    pose: { position: { x, y, z: 0 }, orientation: quaternionFromYaw(yaw) },
  });
}

// Press-and-hold helper for RESET buttons.
export function holdButton(btn, ms, onFire) {
  let timer = null;
  const cancel = () => { clearTimeout(timer); timer = null; btn.classList.remove('is-holding'); };
  const start = (e) => {
    e.preventDefault(); if (timer) return;
    btn.classList.add('is-holding');
    timer = setTimeout(() => { cancel(); onFire(); }, ms);
  };
  btn.addEventListener('pointerdown', start);
  btn.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); start(e); } });
  for (const ev of ['pointerup', 'pointerleave', 'pointercancel', 'blur', 'keyup']) btn.addEventListener(ev, cancel);
}
