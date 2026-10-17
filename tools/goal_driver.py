#!/usr/bin/env python3
"""SITL fixture: proportional goal-driver (/goal_pose or /move_base_simple/goal
+ /odom -> /cmd_vel). Laptop stand-in for Nav2."""
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PoseStamped
from nav_msgs.msg import Odometry

LINEAR_K, ANGULAR_K, GOAL_TOL = 0.4, 0.8, 0.08
MAX_LIN, MAX_ANG = 0.3, 1.2

class GoalDriver(Node):
    def __init__(self):
        super().__init__('goal_driver')
        self.x = self.y = self.th = 0.0; self.goal = None
        self.cmd = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(Odometry, '/odom', self._odom, 10)
        self.create_subscription(PoseStamped, '/goal_pose', self._goal, 10)
        self.create_subscription(PoseStamped, '/move_base_simple/goal', self._goal, 10)
        self.create_timer(0.1, self.tick)
        self.get_logger().info('goal_driver up')

    def _odom(self, m):
        p = m.pose.pose
        self.x, self.y = p.position.x, p.position.y
        self.th = 2.0 * math.atan2(p.orientation.z, p.orientation.w)

    def _goal(self, m):
        self.goal = (m.pose.position.x, m.pose.position.y)
        self.get_logger().info(f'new goal: {self.goal}')

    def tick(self):
        tw = Twist()
        if self.goal is None: self.cmd.publish(tw); return
        dx, dy = self.goal[0] - self.x, self.goal[1] - self.y
        dist = math.hypot(dx, dy)
        if dist < GOAL_TOL:
            self.goal = None; self.get_logger().info('goal reached')
            self.cmd.publish(tw); return
        err = math.atan2(dy, dx) - self.th
        while err > math.pi: err -= 2*math.pi
        while err < -math.pi: err += 2*math.pi
        tw.angular.z = max(-MAX_ANG, min(MAX_ANG, ANGULAR_K * err))
        tw.linear.x = 0.0 if abs(err) > 0.8 else max(-MAX_LIN, min(MAX_LIN, LINEAR_K * dist))
        self.cmd.publish(tw)

def main():
    rclpy.init(); rclpy.spin(GoalDriver())

if __name__ == '__main__': main()
