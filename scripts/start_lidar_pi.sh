#!/bin/bash
source /opt/ros/jazzy/setup.bash
source ~/robie_ws/install/setup.bash
ros2 run tf2_ros static_transform_publisher \
  --x 0 --y 0 --z 0.15 --yaw 0 --pitch 0 --roll 0 \
  --frame-id base_link --child-frame-id laser &
TF_PID=$!
trap "kill $TF_PID 2>/dev/null" EXIT
ros2 launch sllidar_ros2 sllidar_a1_launch.py
