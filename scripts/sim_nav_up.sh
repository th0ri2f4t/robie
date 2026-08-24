#!/bin/bash
WS=$HOME/robie_ws
trap 'echo; echo "== shutting down =="; kill %1 %2 2>/dev/null; exit 0' INT TERM

echo "== cleanup =="
$WS/scripts/stop_all.sh
sleep 2

echo "== starting Gazebo world =="
ros2 launch gazebo_ros gazebo.launch.py \
  world:=$WS/install/robie_bringup/share/robie_bringup/worlds/robie_warehouse.world &

until ros2 service list 2>/dev/null | grep -q spawn_entity; do sleep 1; done
echo "== factory ready: spawning robot =="
ros2 run gazebo_ros spawn_entity.py -entity robie \
  -file $WS/install/robie_bringup/share/robie_bringup/urdf/robie.urdf -x 0 -y 0 -z 0.1

until ros2 topic list 2>/dev/null | grep -q '^/odom$' && ros2 topic list 2>/dev/null | grep -q '^/scan$'; do sleep 1; done
echo "== robot alive (/odom + /scan) =="

echo "== starting SLAM =="
ros2 launch robie_bringup robie_slam.launch.py &

sleep 5
echo "=========================================================="
echo " STACK UP: world + robot + SLAM. Keep this terminal OPEN."
echo " Next: rviz (T2), teleop lap then Nav2 (T3)."
echo " Ctrl+C here brings everything down."
echo "=========================================================="
wait
