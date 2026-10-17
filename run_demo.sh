#!/usr/bin/env bash
# R.O.B.I.E. laptop SITL demo v3 — one command; Ctrl+C stops everything.
# Command chain mirrors the robot: controllers -> /cmd_vel_raw -> interlock -> /cmd_vel -> motors.
cd ~/robie_ws || exit 1
source install/setup.bash
echo "[demo] killing stale processes..."
pkill -9 -f "webapp/server.py"; pkill -9 -f "robie_bringup/web_bridge"
pkill -9 -f plume_sim; pkill -9 -f gas_climber; pkill -9 -f fake_scan
pkill -9 -f odom_to_pose; pkill -9 -f sitl_glue; pkill -9 -f sitl_interlock
sleep 1
pids=()
cleanup(){ echo; echo "[demo] stopping all..."; for p in "${pids[@]}"; do kill "$p" 2>/dev/null; done; }
trap cleanup EXIT INT TERM
echo "[demo] launching SITL stack v3..."
ros2 run robie_gas plume_sim --ros-args -p leak_x:=2.0 -p leak_y:=0.0 -p peak:=400.0 -p sigma:=0.5 -p noise_sigma:=8.0 -r /robie/gas:=/robie/gas_sim & pids+=($!)
ros2 run robie_gas gas_climber --ros-args -p threshold:=150.0 -p exit_threshold:=100.0 -r /robie/gas:=/robie/gas_sim -r /cmd_vel:=/cmd_vel_raw & pids+=($!)
python3 tools/fake_scan.py & pids+=($!)
python3 tools/odom_to_pose.py & pids+=($!)
python3 tools/sitl_glue.py & pids+=($!)
python3 tools/sitl_interlock.py & pids+=($!)
ros2 run robie_bringup web_bridge --ros-args -r /cmd_vel:=/cmd_vel_raw & pids+=($!)
sleep 2
(cd webapp && python3 server.py) & pids+=($!)
sleep 2
echo "[demo] READY -> http://localhost:8080  (Ctrl+C stops everything)"
wait
