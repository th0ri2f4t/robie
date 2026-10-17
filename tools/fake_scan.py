#!/usr/bin/env python3
"""SITL fixture: synthetic /scan (6.0x5.0 m room + pipe obstacle), 5 Hz."""
import math, random
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

AX, AY = 3.0, 2.5
PIPE = (1.2, -0.8, 0.15)
N = 360

def ray_room(th):
    c, s = math.cos(th), math.sin(th)
    ts = []
    if c > 1e-9: ts.append(AX / c)
    if c < -1e-9: ts.append(-AX / c)
    if s > 1e-9: ts.append(AY / s)
    if s < -1e-9: ts.append(-AY / s)
    return min(ts) if ts else 8.0

def ray_circle(th, cx, cy, r):
    c, s = math.cos(th), math.sin(th)
    b = -2 * (c * cx + s * cy)
    c0 = cx * cx + cy * cy - r * r
    disc = b * b - 4 * c0
    if disc < 0: return None
    t = (-b - math.sqrt(disc)) / 2
    return t if t > 0.02 else None

class FakeScan(Node):
    def __init__(self):
        super().__init__('fake_scan')
        self.pub = self.create_publisher(LaserScan, '/scan', 10)
        self.create_timer(0.2, self.tick)
        self.sent = False
        self.get_logger().info('fake_scan fixture up')

    def tick(self):
        try:
            msg = LaserScan()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'laser'
            msg.angle_min, msg.angle_max = 0.0, 2 * math.pi
            msg.angle_increment = 2 * math.pi / N
            msg.scan_time, msg.time_increment = 0.2, 0.0
            msg.range_min, msg.range_max = 0.12, 8.0
            ranges = []
            for i in range(N):
                th = i * msg.angle_increment
                d = ray_room(th)
                pc = ray_circle(th, *PIPE)
                if pc is not None: d = min(d, pc)
                ranges.append(d + random.uniform(-0.02, 0.02))
            msg.ranges = ranges
            msg.intensities = [50.0] * N
            self.pub.publish(msg)
            if not self.sent:
                self.sent = True
                self.get_logger().info('first scan published on /scan')
        except Exception as e:
            self.get_logger().error('scan tick failed: %r' % e)

def main():
    rclpy.init(); rclpy.spin(FakeScan())

if __name__ == '__main__': main()
