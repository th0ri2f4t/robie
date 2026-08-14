import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from robie_msgs.msg import WheelSpeeds


def inverse_kinematics(vx, vy, wz, radius, arm):
    """Mecanum inverse kinematics. Returns (fl, fr, rl, rr) wheel speeds in rad/s.
    Sign convention to be verified on the bench; if the robot crab-walks the
    wrong way, flip the vy terms."""
    w_fl = (vx - vy - arm * wz) / radius
    w_fr = (vx + vy + arm * wz) / radius
    w_rl = (vx + vy - arm * wz) / radius
    w_rr = (vx - vy + arm * wz) / radius
    return (w_fl, w_fr, w_rl, w_rr)


class MecanumDriver(Node):
    def __init__(self):
        super().__init__('mecanum_driver')
        self.create_subscription(Twist, '/cmd_vel', self.cmd_cb, 10)
        self.pub = self.create_publisher(WheelSpeeds, '/wheel_commands', 10)
        self.declare_parameter('wheel_radius', 0.032)
        self.declare_parameter('arm', 0.18)          # lx + ly
        self.declare_parameter('max_wheel_rad_s', 30.0)
        self.get_logger().info('MecanumDriver ready')

    def cmd_cb(self, msg):
        r = self.get_parameter('wheel_radius').value
        a = self.get_parameter('arm').value
        vmax = self.get_parameter('max_wheel_rad_s').value
        w = inverse_kinematics(msg.linear.x, msg.linear.y, msg.angular.z, r, a)
        peak = max(abs(x) for x in w) or 1e-9
        if peak > vmax:
            s = vmax / peak
            w = tuple(x * s for x in w)
        out = WheelSpeeds()
        out.header.stamp = self.get_clock().now().to_msg()
        out.front_left, out.front_right, out.rear_left, out.rear_right = w
        self.pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = MecanumDriver()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
