#!/bin/bash
# R.O.B.I.E - kill every stack process
pkill -f rviz2
pkill -f teleop_twist_keyboard
pkill -f gzclient
pkill -f gzserver
pkill -f nav2_
pkill -f controller_server
pkill -f planner_server
pkill -f bt_navigator
pkill -f behavior_server
pkill -f waypoint_follower
pkill -f velocity_smoother
pkill -f lifecycle_manager
pkill -f slam_toolbox
pkill -f robot_state_publisher
pkill -f plume_sim
pkill -f gas_climber
pkill -f ros2
sleep 2
ros2 daemon stop 2>/dev/null
echo "all stack processes killed"
