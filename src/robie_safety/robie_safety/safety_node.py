import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from robie_msgs.msg import SafetyState
from .safety_logic import SafetyInterlock

class SafetyNode(Node):
    def __init__(self):
        super().__init__('safety_node')
        self.logic = SafetyInterlock()
        self.last_heartbeat = time.time()  # Watchdog timer

        # Subscribers
        self.create_subscription(Bool, '/hw/estop', self.estop_cb, 10)
        self.create_subscription(Bool, '/sw/estop', self.estop_cb, 10)
        self.create_subscription(Bool, '/hw/bumper_front', self.bumper_f_cb, 10)
        self.create_subscription(Bool, '/hw/bumper_rear', self.bumper_r_cb, 10)
        self.create_subscription(Bool, '/hw/rf_alive', self.rf_cb, 10)

        # Publishers
        self.state_pub = self.create_publisher(SafetyState, '/safety_state', 10)
        self.enable_pub = self.create_publisher(Bool, '/motor_enable', 10)

        self.create_timer(0.05, self.tick)
        self.get_logger().info('SafetyNode active. Watchdog timeout: 2.0s')

    def estop_cb(self, msg): self.logic.estop_pressed = msg.data
    def bumper_f_cb(self, msg): self.logic.bumper_front = msg.data
    def bumper_r_cb(self, msg): self.logic.bumper_rear = msg.data
    def rf_cb(self, msg):
        self.logic.rf_link_alive = msg.data
        self.last_heartbeat = time.time()  # Reset watchdog

    def tick(self):
        # Watchdog logic: If no heartbeat in 2s, force RF alive to False
        rf_state = self.logic.rf_link_alive
        if time.time() - self.last_heartbeat > 2.0:
            if rf_state is True:
                self.get_logger().error('HEARTBEAT TIMEOUT -> Cutting power')
            rf_state = False

        enabled = self.logic.update(
            self.logic.estop_pressed, 
            self.logic.bumper_front, 
            self.logic.bumper_rear, 
            rf_state
        )
        
        enable_msg = Bool()
        enable_msg.data = enabled
        self.enable_pub.publish(enable_msg)

        state_msg = SafetyState()
        state_msg.header.stamp = self.get_clock().now().to_msg()
        state_msg.estop_pressed = self.logic.estop_pressed
        state_msg.bumper_front = self.logic.bumper_front
        state_msg.bumper_rear = self.logic.bumper_rear
        state_msg.nrf_link_alive = rf_state
        state_msg.motors_enabled = enabled
        self.state_pub.publish(state_msg)

def main(args=None):
    rclpy.init(args=args)
    node = SafetyNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
