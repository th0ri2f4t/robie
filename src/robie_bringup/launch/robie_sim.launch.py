from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(package='robie_gas', executable='plume_sim', name='plume_sim',
             output='screen',
             parameters=[{'peak': 400.0, 'noise_sigma': 2.0}]),
        Node(package='robie_gas', executable='gas_climber', name='gas_climber',
             output='screen',
             parameters=[{'threshold': 50.0, 'timeout_s': 90.0,
                          'log_file': '/home/th0r12f4t/robie_ws/logs/mission_demo.csv'}]),
        Node(package='robie_hardware', executable='mock_bridge',
             name='mock_bridge', output='screen'),
        Node(package='robie_safety', executable='safety_node',
             name='safety_node', output='screen'),
        Node(package='robie_nav', executable='mecanum_driver',
             name='mecanum_driver', output='screen'),
        Node(package='robie_nav', executable='motor_arbiter',
             name='motor_arbiter', output='screen'),
    ])
