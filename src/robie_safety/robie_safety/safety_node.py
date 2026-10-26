import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
        self.sw_estop = False  # latched software stop (dashboard)

        # Subscribers
        self.create_subscription(Bool, '/hw/estop', self.estop_cb, 10)
        self.create_subscription(Bool, '/sw/estop', self.sw_estop_cb, 10)
        self.create_subscription(Bool, '/hw/bumper_front', self.bumper_f_cb, 10)
        self.create_subscription(Bool, '/hw/bumper_rear', self.bumper_r_cb, 10)
        self.create_subscription(Bool, '/hw/rf_alive', self.rf_cb, 10)

        # Publishers
        self.state_pub = self.create_publisher(SafetyState, '/safety_state', 10)
        self.enable_pub = self.create_publisher(Bool, '/motor_enable', 10)

        self.create_timer(0.05, self.tick)
        self._start_http()
        self.get_logger().info('SafetyNode active. Watchdog timeout: 2.0s')

    def sw_estop_cb(self, msg): self.sw_estop = bool(msg.data)

    def _start_http(self, port=8082):
        node = self

        class Handler(BaseHTTPRequestHandler):
            def _reply(self, code, body):
                self.send_response(code)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                if self.path == '/estop':
                    node.sw_estop = True
                    node.get_logger().warn('SOFTWARE STOP latched (dashboard)')
                    self._reply(200, b'estop latched')
                elif self.path == '/reset':
                    node.sw_estop = False
                    node.get_logger().warn('software stop released (dashboard reset)')
                    self._reply(200, b'reset')
                else:
                    self._reply(404, b'not found')

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', '*')
                self.end_headers()

            def log_message(self, *args):
                pass

        try:
            self.http = ThreadingHTTPServer(('0.0.0.0', port), Handler)
            threading.Thread(target=self.http.serve_forever, daemon=True).start()
            self.get_logger().info('stop endpoint on port %d: POST /estop, POST /reset' % port)
        except OSError as e:
            self.get_logger().error('stop endpoint not started: %s' % e)

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
            (self.logic.estop_pressed or self.sw_estop), 
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
