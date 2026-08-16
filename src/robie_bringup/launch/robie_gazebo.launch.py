import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    share = get_package_share_directory('robie_bringup')
    gz_share = get_package_share_directory('gazebo_ros')
    world = os.path.join(share, 'worlds', 'robie_warehouse.world')
    urdf = os.path.join(share, 'urdf', 'robie.urdf')

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gz_share, 'launch', 'gazebo.launch.py')),
        launch_arguments={'world': world}.items())

    spawn = Node(package='gazebo_ros', executable='spawn_entity.py',
                 arguments=['-entity', 'robie', '-file', urdf,
                            '-x', '0', '-y', '0', '-z', '0.1'])
    return LaunchDescription([gazebo, spawn])
