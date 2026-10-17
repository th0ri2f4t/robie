#!/usr/bin/env python3
"""SITL fixture: models the ESP32 hardware interlock for laptop demos.
Gates /cmd_vel_raw -> /cmd_vel; zero-twist on remote E-stop or command
watchdog timeout; publishes SafetyState so web_bridge T-lines react.
On the real robot this role belongs to the ESP32 interlock firmware."""
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from robie_msgs.msg import SafetyState

WATCHDOG = 0.75  # s without any command frame => motors zero (fail-safe)

class SitlInterlock(Node):
    def __init__(self):
        super().__init__('sitl_interlock')
        self.estop = False
        self.last_raw = 0.0
        self.raw = Twist()
        self.cmd = self.create_publisher(Twist, '/cmd_vel', 20)
        self.safety = self.create_publisher(SafetyState, '/safety_state', 2)
        self.create_subscription(Twist, '/cmd_vel_raw', self._raw, 20)
        self.create_subscription(Bool, '/sw/estop', self._estop, 10)
        self.create_timer(0.05, self._tick)
        self.create_timer(0.5, self._safety_tick)
        self.get_logger().info('sitl_interlock up: gating /cmd_vel_raw -> /cmd_vel')

    def _raw(self, m):
        self.raw = m; self.last_raw = time.monotonic()

    def _estop(self, m):
        if m.data != self.estop:
            self.get_logger().warn('E-STOP %s' % ('ENGAGED' if m.data else 'CLEARED'))
        self.estop = m.data

    def _tick(self):
        tw = Twist()
        if not self.estop and (time.monotonic() - self.last_raw) < WATCHDOG:
            tw = self.raw
        self.cmd.publish(tw)

    def _safety_tick(self):
        s = SafetyState()
        s.header.stamp = self.get_clock().now().to_msg()
        s.estop_pressed = self.estop
        s.bumper_front = False
        s.bumper_rear = False
        s.nrf_link_alive = True
        s.motors_enabled = not self.estop
        self.safety.publish(s)

def main():
    rclpy.init(); rclpy.spin(SitlInterlock())

if __name__ == '__main__': main()
