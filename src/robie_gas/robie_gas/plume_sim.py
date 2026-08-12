import math, random
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry


class PlumeSim(Node):
    def __init__(self):
        super().__init__('plume_sim')
        self.create_subscription(Twist, '/cmd_vel', self.cmd_cb, 10)
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.gas_pub = self.create_publisher(Float64, '/gas/raw', 10)
        self.create_timer(0.1, self.step)

        self.declare_parameter('leak_x', 1.5)
        self.declare_parameter('leak_y', 0.5)
        self.declare_parameter('peak', 400.0)
        self.declare_parameter('sigma', 0.5)
        self.leak_x = self.get_parameter('leak_x').value
        self.leak_y = self.get_parameter('leak_y').value
        self.peak = self.get_parameter('peak').value
        self.sigma = self.get_parameter('sigma').value

        self.x = self.y = self.yaw = 0.0
        self.vx = self.wz = 0.0
        self.last = self.get_clock().now()
        self.get_logger().info('PlumeSim ready (leak at %.1f, %.1f)' % (self.leak_x, self.leak_y))

    def cmd_cb(self, msg):
        self.vx, self.wz = msg.linear.x, msg.angular.z

    def step(self):
        now = self.get_clock().now()
        dt = (now - self.last).nanoseconds * 1e-9
        self.last = now

        self.yaw += self.wz * dt
        self.x += self.vx * math.cos(self.yaw) * dt
        self.y += self.vx * math.sin(self.yaw) * dt

        o = Odometry()
        o.header.stamp = now.to_msg()
        o.header.frame_id = 'odom'
        o.pose.pose.position.x = self.x
        o.pose.pose.position.y = self.y
        o.pose.pose.orientation.w = math.cos(self.yaw / 2)
        o.pose.pose.orientation.z = math.sin(self.yaw / 2)
        self.odom_pub.publish(o)

        d2 = (self.x - self.leak_x) ** 2 + (self.y - self.leak_y) ** 2
        reading = self.peak * math.exp(-d2 / (2 * self.sigma * self.sigma))
        reading = max(0.0, reading + random.gauss(0, 4))
        self.gas_pub.publish(Float64(data=reading))


def main(args=None):
    rclpy.init(args=args)
    node = PlumeSim()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
