#!/bin/bash
pkill -f gzserver; pkill -f gzclient; pkill -f spawn_entity.py
pkill -f teleop_twist_keyboard; pkill -f rviz2
pkill -f mecanum_driver; pkill -f motor_arbiter; pkill -f safety_node
pkill -f mock_bridge; pkill -f serial_bridge
pkill -f plume_sim; pkill -f gas_climber
pkill -f robot_state_publisher; pkill -f slam_toolbox
echo "All simulation processes stopped."
