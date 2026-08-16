import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from robie_msgs.msg import WheelSpeeds

class MockBridge(Node):
    def __init__(self):
        super().__init__('mock_bridge')
        self.last_log = 0.0
        self.create_timer(0.5, self.heartbeat)
        self.create_subscription(WheelSpeeds, '/motor_targets', self.cmd_cb, 10)
        self.estop_pub = self.create_publisher(Bool, '/hw/estop', 10)
        self.bf_pub = self.create_publisher(Bool, '/hw/bumper_front', 10)
        self.br_pub = self.create_publisher(Bool, '/hw/bumper_rear', 10)
        self.link_pub = self.create_publisher(Bool, '/hw/rf_alive', 10)
        self.get_logger().info("MOCK HARDWARE: Simulating healthy ESP32")

    def heartbeat(self):
        e = Bool(); e.data = False; self.estop_pub.publish(e)
        bf = Bool(); bf.data = False; self.bf_pub.publish(bf)
        br = Bool(); br.data = False; self.br_pub.publish(br)
        l = Bool(); l.data = True; self.link_pub.publish(l)

    def cmd_cb(self, msg):
        now = time.time()
        if now - self.last_log > 1.0 and \
           (abs(msg.front_left) > 0.01 or abs(msg.front_right) > 0.01):
            self.last_log = now
            self.get_logger().info(
                "MOCK MOTORS: FL=%.2f FR=%.2f RL=%.2f RR=%.2f rad/s"
                % (msg.front_left, msg.front_right, msg.rear_left, msg.rear_right))

def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(MockBridge())
    rclpy.shutdown()
