#!/usr/bin/env python3
"""
camera_node.py - ROS 2 node wrapping libcamera/rpicam for Pi Camera Module 3 NoIR
Publishes sensor_msgs/Image on /camera/image_raw
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import subprocess
import time
import yaml

class CameraNode(Node):
def __init__(self):
super().__init__('camera_node')

# Load config
self.declare_parameter('config_path', '~/robie_ws/src/robie_vision/config/camera.yaml')
config_path = self.get_parameter('config_path').value

with open(config_path, 'r') as f:
self.config = yaml.safe_load(f)

self.bridge = CvBridge()
self.publisher = self.create_publisher(Image, '/camera/image_raw', 10)

# Start rpicam-vid stream
width = self.config['camera']['width']
height = self.config['camera']['height']
fps = self.config['camera']['framerate']
quality = self.config['camera']['quality']
denoise = self.config['camera']['denoise']
port = self.config['stream']['port']

cmd = [
'rpicam-vid', '-t', '0', '-n', '--codec', 'mjpeg',
'--width', str(width), '--height', str(height),
'--framerate', str(fps), '--quality', str(quality),
'--denoise', denoise, '--flush', '--listen',
'-o', f'tcp://0.0.0.0:{port}'
]

self.process = subprocess.Popen(cmd)
self.get_logger().info(f'Started rpicam-vid on port {port}')

# Wait for stream to be ready
time.sleep(2)

# Connect to stream
self.cap = cv2.VideoCapture(f'tcp://127.0.0.1:{port}')

if not self.cap.isOpened():
self.get_logger().error('Failed to connect to camera stream')
return

self.get_logger().info('Camera node ready, publishing on /camera/image_raw')

# Timer for frame capture
self.timer = self.create_timer(1.0/fps, self.timer_callback)

def timer_callback(self):
ret, frame = self.cap.read()
if not ret:
self.get_logger().warn('Failed to read frame')
return

# Convert BGR to RGB
frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

# Convert to ROS Image message
msg = self.bridge.cv2_to_imgmsg(frame_rgb, encoding='rgb8')
msg.header.stamp = self.get_clock().now().to_msg()
msg.header.frame_id = 'camera_frame'

self.publisher.publish(msg)

def destroy_node(self):
self.get_logger().info('Shutting down camera node')
if hasattr(self, 'cap'):
self.cap.release()
if hasattr(self, 'process'):
self.process.terminate()
self.process.wait()
super().destroy_node()

def main(args=None):
rclpy.init(args=args)
node = CameraNode()
try:
rclpy.spin(node)
except KeyboardInterrupt:
pass
finally:
node.destroy_node()
rclpy.shutdown()

if __name__ == '__main__':
main()
