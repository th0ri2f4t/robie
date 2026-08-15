import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from robie_msgs.msg import WheelSpeeds

from .serial_protocol import encode_motor_cmd, encode_enable, parse_line

try:
    import serial
except ImportError:
    serial = None


class SerialBridgeNode(Node):
    def __init__(self):
        super().__init__('serial_bridge')
        self.declare_parameter('port', '/dev/ttyUSB0')
        self.declare_parameter('baud', 115200)
        self.ser = None
        self.last_heartbeat = 0.0

        self.estop_pub = self.create_publisher(Bool, '/hw/estop', 10)
        self.bf_pub = self.create_publisher(Bool, '/hw/bumper_front', 10)
        self.br_pub = self.create_publisher(Bool, '/hw/bumper_rear', 10)
        self.link_pub = self.create_publisher(Bool, '/hw/rf_alive', 10)

        self.create_subscription(WheelSpeeds, '/motor_targets', self.targets_cb, 10)
        self.create_subscription(Bool, '/motor_enable', self.enable_cb, 10)

        self.create_timer(1.0, self.reconnect_timer)
        self.create_timer(0.5, self.link_timer)
        self.get_logger().info('SerialBridge ready (waiting for ESP32)')

    def reconnect_timer(self):
        if serial is None:
            self.get_logger().error('pyserial missing: sudo apt install python3-serial')
            return
        if self.ser is not None:
            return
        port = self.get_parameter('port').value
        baud = self.get_parameter('baud').value
        try:
            self.ser = serial.Serial(port, baud, timeout=0.1)
            self.get_logger().warn('Connected to ESP32 on %s' % port)
            threading.Thread(target=self.reader_loop, daemon=True).start()
        except serial.SerialException:
            self.ser = None

    def reader_loop(self):
        while rclpy.ok():
            if self.ser is None:
                return
            try:
                raw = self.ser.readline()
            except serial.SerialException:
                self.ser = None
                return
            if not raw:
                continue
            parsed = parse_line(raw.decode(errors='ignore'))
            if parsed is None:
                continue
            if parsed['type'] == 'T':
                for pub, key in ((self.estop_pub, 'estop'),
                                 (self.bf_pub, 'bumper_front'),
                                 (self.br_pub, 'bumper_rear')):
                    m = Bool()
                    m.data = parsed[key]
                    pub.publish(m)
            elif parsed['type'] == 'H':
                self.last_heartbeat = time.monotonic()

    def link_timer(self):
        # v1: "link alive" = USB heartbeat seen in last 2 s.
        # Fail-safe: ESP32 dies -> link False -> safety node kills motors.
        alive = self.ser is not None and \
            (time.monotonic() - self.last_heartbeat) < 2.0
        m = Bool()
        m.data = alive
        self.link_pub.publish(m)

    def targets_cb(self, msg):
        if self.ser is None:
            return
        line = encode_motor_cmd((msg.front_left, msg.front_right,
                                 msg.rear_left, msg.rear_right))
        self.ser.write((line + '\n').encode())

    def enable_cb(self, msg):
        if self.ser is None:
            return
        self.ser.write((encode_enable(msg.data) + '\n').encode())


def main(args=None):
    rclpy.init(args=args)
    node = SerialBridgeNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
