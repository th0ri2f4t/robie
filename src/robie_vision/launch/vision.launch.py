from launch import LaunchDescription
from launch_ros.actions import Node
C='/home/th0r12f4t/robie_ws/src/robie_vision/config/camera.yaml'
def generate_launch_description():
 return LaunchDescription([
  Node(package='robie_vision',executable='camera_node',
   name='camera_node',output='screen',
   parameters=[{'config_path':C}]),
  Node(package='robie_vision',
   executable='crack_detector_node',
   name='crack_detector_node',output='screen',
   parameters=[{'config_path':C}]),
 ])
