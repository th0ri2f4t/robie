import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    share = get_package_share_directory('robie_bringup')
    with open(os.path.join(share, 'urdf', 'robie.urdf')) as f:
        robot_description = f.read()

    rsp = Node(package='robot_state_publisher',
               executable='robot_state_publisher',
               parameters=[{'robot_description': robot_description, 'use_sim_time': True}])

    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('slam_toolbox'),
            'launch', 'online_async_launch.py')),
        launch_arguments={
            'use_sim_time': 'true',
            'slam_params_file': os.path.join(share, 'config', 'slam_params.yaml'),
        }.items())

    return LaunchDescription([rsp, slam])
