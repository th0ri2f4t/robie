#!/usr/bin/env python3
"""
crack_detector_node.py - Classical CV pipeline for pipe crack detection
Subscribes to /camera/image_raw, publishes events to /robie/event
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2
import numpy as np
import yaml

class CrackDetectorNode(Node):
def __init__(self):
super().__init__('crack_detector_node')

# Load config
self.declare_parameter('config_path', '~/robie_ws/src/robie_vision/config/camera.yaml')
config_path = self.get_parameter('config_path').value

with open(config_path, 'r') as f:
self.config = yaml.safe_load(f)

self.threshold = self.config['detection']['threshold']
self.min_area = self.config['detection']['min_area']
self.confidence_threshold = self.config['detection']['confidence_threshold']

self.bridge = CvBridge()

# Subscribers and publishers
self.subscriber = self.create_subscription(
Image, '/camera/image_raw', self.image_callback, 10)
self.event_publisher = self.create_publisher(String, '/robie/event', 10)
self.annotated_publisher = self.create_publisher(Image, '/camera/image_annotated', 10)

self.get_logger().info('Crack detector node ready')

def image_callback(self, msg):
# Convert ROS Image to OpenCV
try:
cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='rgb8')
except Exception as e:
self.get_logger().error(f'CV bridge error: {e}')
return

# Convert to grayscale
gray = cv2.cvtColor(cv_image, cv2.COLOR_RGB2GRAY)

# Adaptive threshold
thresh = cv2.adaptiveThreshold(
gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
cv2.THRESH_BINARY_INV, 11, 2
)

# Morphological cleanup
kernel = np.ones((3, 3), np.uint8)
cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel, iterations=1)

# Canny edge detection
edges = cv2.Canny(cleaned, 50, 150)

# Find contours
contours, _ = cv2.findContours(
edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
)

# Analyze contours
annotated = cv_image.copy()
detections = []

for contour in contours:
area = cv2.contourArea(contour)
if area < self.min_area:
continue

# Get bounding box
x, y, w, h = cv2.boundingRect(contour)

# Simple confidence metric based on aspect ratio and area
aspect_ratio = w / h if h > 0 else 0
confidence = min(1.0, area / 10000.0) * (1.0 if 0.1 < aspect_ratio < 10 else 0.5)

if confidence >= self.confidence_threshold:
# Normalize position to 0-1 range
norm_x = (x + w/2) / cv_image.shape[1]
norm_y = (y + h/2) / cv_image.shape[0]

detections.append((confidence, norm_x, norm_y))

# Draw on annotated image
cv2.rectangle(annotated, (x, y), (x+w, y+h), (255, 0, 0), 2)
cv2.putText(annotated, f'{confidence:.2f}', (x, y-10),
cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

# Publish annotated image
annotated_msg = self.bridge.cv2_to_imgmsg(annotated, encoding='rgb8')
annotated_msg.header = msg.header
self.annotated_publisher.publish(annotated_msg)

# Publish detection events (pick highest confidence)
if detections:
detections.sort(reverse=True)
confidence, x, y = detections[0]
event_msg = String()
event_msg.data = f'C,{confidence:.2f},{x:.2f},{y:.2f}'
self.event_publisher.publish(event_msg)
self.get_logger().info(f'Crack detected: {event_msg.data}')

def main(args=None):
rclpy.init(args=args)
node = CrackDetectorNode()
try:
rclpy.spin(node)
except KeyboardInterrupt:
pass
finally:
node.destroy_node()
rclpy.shutdown()

if __name__ == '__main__':
main()
