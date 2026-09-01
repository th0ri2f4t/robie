#!/bin/bash
# T5 - Brain: Nav2, merged params, sim time
source /opt/ros/humble/setup.bash
ros2 launch nav2_bringup navigation_launch.py use_sim_time:=true \
  params_file:=$HOME/robie_ws/src/robie_nav/params/nav2_params.yaml
