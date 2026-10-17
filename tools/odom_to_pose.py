#!/usr/bin/env python3
"""SITL fixture: republishes /odom (Odometry) as /pose (PoseStamped) for web_bridge."""
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseStamped

class Republisher(Node):
    def __init__(self):
        super().__init__('odom_to_pose')
        self.pub = self.create_publisher(PoseStamped, '/pose', 10)
        self.create_subscription(Odometry, '/odom', self.cb, 10)
        self.get_logger().info('odom_to_pose republisher up')

    def cb(self, msg):
        p = PoseStamped()
        p.header = msg.header
        p.pose = msg.pose.pose
        self.pub.publish(p)

def main():
    rclpy.init(); rclpy.spin(Republisher())

if __name__ == '__main__': main()
