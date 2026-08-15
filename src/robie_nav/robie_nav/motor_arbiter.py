import rclpy
from rclpy.node import Node
from robie_msgs.msg import WheelSpeeds
from std_msgs.msg import Bool


class MotorArbiter(Node):
    """
    The final hardware gate. Intercepts wheel commands and blocks them
    if the safety interlock is not enabled.
    """
    def __init__(self):
        super().__init__('motor_arbiter')
        self.enabled = False
        self.latest_commands = WheelSpeeds()

        self.create_subscription(Bool, '/motor_enable', self.enable_cb, 10)
        self.create_subscription(WheelSpeeds, '/wheel_commands', self.cmd_cb, 10)
        self.pub = self.create_publisher(WheelSpeeds, '/motor_targets', 10)

        # Publish to the ESP32 at 50Hz (20ms) for smooth motor control
        self.create_timer(0.02, self.publish_targets)
        self.get_logger().info('MotorArbiter ready. Waiting for safety enable.')

    def enable_cb(self, msg):
        self.enabled = msg.data
        state = "ENABLED" if self.enabled else "DISABLED (KILLED)"
        self.get_logger().warn(f'Safety interlock changed to: {state}')

    def cmd_cb(self, msg):
        self.latest_commands = msg

    def publish_targets(self):
        out = WheelSpeeds()
        out.header.stamp = self.get_clock().now().to_msg()

        if self.enabled:
            out.front_left = self.latest_commands.front_left
            out.front_right = self.latest_commands.front_right
            out.rear_left = self.latest_commands.rear_left
            out.rear_right = self.latest_commands.rear_right
        else:
            # HARD OVERRIDE: Force all wheels to 0.0 regardless of navigation commands
            out.front_left = 0.0
            out.front_right = 0.0
            out.rear_left = 0.0
            out.rear_right = 0.0

        self.pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = MotorArbiter()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
