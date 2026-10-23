# R.O.B.I.E. mission-control dashboard

A browser dashboard for R.O.B.I.E. with these panels:
- STOP / reset
- safety status
- live SLAM map with click-to-move
- camera feed with crack overlay
- 3D model of the robot moving on the map
- gas readings
- event log
- manual driving

It needs no internet and works on ROBIE-NET or on home Wi-Fi. The page uses whichever address you opened it from.

## Ports

| Port | Service |
|---|---|
| 8080 | This dashboard (`server.py`). Not 8082, because 8082 belongs to `safety_node`. |
| 8082 | `safety_node`: `POST /estop`, `POST /reset` (unchanged) |
| 9090 | rosbridge WebSocket |
| 8081 | MJPEG camera stream (unchanged) |

## Install

**On your laptop**, copy the folder to the Pi:
```
scp -r robie_web th0r12f4t@192.168.4.1:~/
```

**On the Pi**:
```
cd ~/robie_web && bash install.sh
```

This installs rosbridge and Flask, copies the dashboard to `~/robie_ws/src/robie_safety/web`, and starts two systemd services, `robie-rosbridge` and `robie-web`. Both restart on boot.

**On your laptop (browser)**, open one of these:
- `http://192.168.4.1:8080` on ROBIE-NET
- `http://th0r12f4t.local:8080` on home Wi-Fi

## Verify

**On the Pi:**
```
curl http://127.0.0.1:8080/api/status        # should report safety_node, rosbridge, camera = true
curl -X POST http://127.0.0.1:8080/api/estop # stop via the relay, reports latency
curl -X POST http://127.0.0.1:8080/api/reset
journalctl -u robie-web -u robie-rosbridge -f
```

**On your laptop:**
```
curl http://192.168.4.1:8080/api/status
```

## How STOP works

There is no physical e-stop, so the dashboard tries three independent paths, in order:
1. A direct `POST` to `safety_node` on port 8082. It is a "simple" no-cors request, so there's no CORS preflight and `safety_node` needs no changes.
2. If that fails, a relay through this server: `POST /api/estop` → `safety_node`.
3. It always also publishes `motor_enable = false` over rosbridge.

The dashboard shows which path worked and how long it took. Pressing Space or Esc anywhere on the page also triggers STOP.

Reset needs a 1-second press-and-hold and only ever goes through `safety_node`. The dashboard never publishes `motor_enable = true`.

## Manual mode

Switch to Manual, then click a free spot on the map to publish a goal. Obstacle cells are refused.

You can also hold the drive pad buttons or the W, A, S, D, Q, E keys:
- `/cmd_vel` is sent at 10 Hz only while something is held.
- Releasing, switching tab, losing the ROS link or pressing STOP sends a zero `Twist`.

## Look and feel

The theme is pastel purple, with MS-DOS type on frosted-glass panels. The fonts (VT323 and IBM Plex Mono, both under open licences) are bundled in `static/fonts`, so nothing loads from the internet. STOP stays red on purpose: an emergency stop must be recognisable instantly.

## 3D + SLAM view (`/explore`)

Click **Open 3D view ↗** on the "Robot on map" panel, or go to `http://<robot>:8080/explore`.

What it shows:
- **Lidar walls (cyan):** every scan hit is binned into a 5 cm cell and drawn as a wall. They're bright when just seen and fade over 90 s.
- **SLAM map walls (grey) and floor:** taken from `/map`.
- **Live scan (yellow), robot model and trail.**

Use the **3D / Split / Map** switch at the top to show the lidar 3D view, the full SLAM map, or both side by side. Turn on **Send goals by clicking**, then click the 3D floor or the SLAM map.

**Save map** calls SLAM Toolbox's `/slam_toolbox/save_map` service. It writes `<name>.pgm` and `<name>.yaml` on the robot, in SLAM Toolbox's working folder unless you give a full path such as `/home/th0r12f4t/maps/flow_station`. The goal goes to the same goal topic as the dashboard, and both pages show it. Clicks on obstacles are refused. STOP (button, Space or Esc) works on this page too, and it switches click-to-move off.

Placing the scan points:
- **Normal case:** scan points are placed with the robot's TF tree (`laser` → `base_link` → `odom` → `map`).
- **If TF is missing:** the page falls back to `/robot_pose` plus the lidar offset from the CAD (`CONFIG.laserFallback` in `static/js/common.js`).
- **If the walls appear mirrored front-to-back:** set `laserFallback.yaw` to `Math.PI` there.

The RPLIDAR A1 scans one horizontal plane, so the walls are that plane extruded upwards (wall height slider). It is not a true 3D scan.

## Topics and settings

All topic names are at the top of `static/js/app.js`, in `CONFIG.topics`. Check two of them:
- **Goal topic:** the goal publishes to `/move_goal` as in your spec. Nav2's default goal topic is `/goal_pose`, so if Nav2 doesn't react, change it there.
- **Robot pose:** the robot is drawn from `/robot_pose` (`PoseStamped`, map frame). SLAM Toolbox does not publish that topic by itself, so a node of yours must. If nothing arrives, the map shows "No pose yet".

Other inputs:
- **Gas events:** both `G,ppm` and `G,mq4ppm,mq6ppm` are understood.
- **Battery:** read from `/robie/battery` (`std_msgs/Float32`) if you publish it. Otherwise it shows "No data".

## 3D model

`static/models/robie_cad.glb` (coloured) and `robie_cad.stl` are exported from the R.O.B.I.E. CAD:
- the chassis from `R_O_B_I_E.SLDASM`,
- the v5 Jackal-style shell,
- the fixed camera mount, lidar and sensors.

They are in the ROS `base_link` frame: x forward, y left, z up, metres, origin on the ground under the chassis centre. To use your own export, replace either file. The viewer tries `.glb`, then `.stl`, then a simple stand-in.

## Try it without the robot

**On your laptop:**
```
pip install websockets pillow flask
python3 tools/mock_robot.py     # fake rosbridge, safety node and camera
python3 server.py               # second terminal
```
Then open `http://localhost:8080`. The mock robot publishes `/scan` and `/tf` too, so the 3D view works. It patrols a room, sends gas and crack events, and obeys STOP, reset, goals and manual driving. It's useful for demos and the viva.

Three.js r160 (MIT licence) is bundled in `static/vendor/three/`, so nothing loads from the internet.
