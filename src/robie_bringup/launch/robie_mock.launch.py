from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(package='robie_hardware', executable='mock_bridge', name='mock_bridge', output='screen'),
        Node(package='robie_safety', executable='safety_node', name='safety_node', output='screen'),
        Node(package='robie_nav', executable='mecanum_driver', name='mecanum_driver', output='screen'),
        Node(package='robie_nav', executable='motor_arbiter', name='motor_arbiter', output='screen'),
    ])
