#!/usr/bin/env python3
"""R.O.B.I.E. safety & motor bridge - the software spine.
ESP32->Pi: T,<e>,<bf>,<br> @20Hz, H,<ms> @1Hz
Pi->ESP32: S,<0|1>, M,<fl>,<fr>,<rl>,<rr> rad/s +/-30
Rules: start DISARMED; arm via /robie/arm; estop or remote_estop or link-lost
or stale cmd_vel (>0.5s) zeroes wheels; bump_front forbids +x, bump_rear -x;
shutdown sends M,0 + S,0.
"""
import threading
import time
import rclpy
from rclpy.node import Node
import serial
from geometry_msgs.msg import Twist
from std_srvs.srv import SetBool
from std_msgs.msg import Bool
from robie_msgs.msg import SafetyState

WHEEL_MAX = 30.0
CMD_TIMEOUT = 0.5

class SafetyBridge(Node):
    def __init__(self):
        super().__init__('safety_bridge')
        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baud', 115200)
        self.declare_parameter('wheel_radius_m', 0.033)
        self.declare_parameter('yaw_scale_m', 0.15)
        self.declare_parameter('link_timeout_s', 0.5)
        self.declare_parameter('sign_fl', 1)
        self.declare_parameter('sign_fr', 1)
        self.declare_parameter('sign_rl', 1)
        self.declare_parameter('sign_rr', 1)
        self.port = self.get_parameter('serial_port').value
        self.r = self.get_parameter('wheel_radius_m').value
        self.k = self.get_parameter('yaw_scale_m').value
        self.timeout = self.get_parameter('link_timeout_s').value
        self.signs = [self.get_parameter(n).value for n in ('sign_fl', 'sign_fr', 'sign_rl', 'sign_rr')]
        self.ser = serial.Serial(self.port, self.get_parameter('baud').value, timeout=0.05)
        self.armed = False
        self.estop = False
        self.remote_estop = False
        self.bump_f = False
        self.bump_r = False
        self.last_t = 0.0
        self.last_cmd = 0.0
        self.t_count = 0
        self.hz = 0.0
        self.twist = None
        self.lock = threading.Lock()
        threading.Thread(target=self._read_loop, daemon=True).start()
        self.pub = self.create_publisher(SafetyState, '/robie/safety', 10)
        self.create_subscription(Twist, '/cmd_vel', self._on_cmd, 10)
        self.create_subscription(Bool, '/robie/remote_estop', self._on_remote_estop, 10)
        self.create_service(SetBool, '/robie/arm', self._on_arm)
        self.create_timer(0.05, self._tick)
        self.create_timer(1.0, self._housekeep)
        self._send('S,0')
        self.get_logger().info('safety_bridge up on %s - DISARMED' % self.port)
    def _send(self, line):
        try:
            self.ser.write((line + '\n').encode())
        except Exception as exc:
            self.get_logger().error('serial write failed: %s' % exc)
    def _read_loop(self):
        while True:
            try:
                raw = self.ser.readline()
            except Exception:
                time.sleep(0.05)
                continue
            line = raw.decode(errors='ignore').strip()
            if line.startswith('T,'):
                p = line.split(',')
                if len(p) == 4:
                    with self.lock:
                        self.estop = p[1] == '1'
                        self.bump_f = p[2] == '1'
                        self.bump_r = p[3] == '1'
                        self.last_t = time.monotonic()
                        self.t_count += 1
            elif line.startswith('H,'):
                with self.lock:
                    self.last_t = time.monotonic()
    def _on_cmd(self, msg):
        with self.lock:
            self.twist = msg
            self.last_cmd = time.monotonic()
    def _on_remote_estop(self, msg):
        self.remote_estop = bool(msg.data)
        if self.remote_estop:
            self.get_logger().warn('REMOTE E-STOP inhibit active')
    def _on_arm(self, req, res):
        self.armed = bool(req.data)
        self._send('S,1' if self.armed else 'S,0')
        res.success = True
        res.message = 'armed' if self.armed else 'disarmed'
        self.get_logger().warn('ARM STATE: %s' % res.message)
        return res
    def _mix(self, tw):
        vx = tw.linear.x
        vy = tw.linear.y
        wz = tw.angular.z
        if self.bump_f and vx > 0.0:
            vx = 0.0
        if self.bump_r and vx < 0.0:
            vx = 0.0
        fl = (vx - vy - wz * self.k) / self.r
        fr = (vx + vy + wz * self.k) / self.r
        rl = (vx + vy - wz * self.k) / self.r
        rr = (vx - vy + wz * self.k) / self.r
        out = [fl, fr, rl, rr]
        for i in range(4):
            out[i] = max(-WHEEL_MAX, min(WHEEL_MAX, out[i])) * self.signs[i]
        return out
    def _tick(self):
        now = time.monotonic()
        with self.lock:
            link_ok = (now - self.last_t) < self.timeout and self.last_t > 0
            fresh = (now - self.last_cmd) < CMD_TIMEOUT
            tw = self.twist
            estop = self.estop
        if (not self.armed) or estop or self.remote_estop or (not link_ok) or (tw is None) or (not fresh):
            wheels = [0.0, 0.0, 0.0, 0.0]
        else:
            wheels = self._mix(tw)
        self._send('M,%.2f,%.2f,%.2f,%.2f' % tuple(wheels))
        msg = SafetyState()
        msg.estop = estop
        msg.bump_front = self.bump_f
        msg.bump_rear = self.bump_r
        msg.link_ok = link_ok
        msg.armed = self.armed
        msg.telemetry_hz = self.hz
        self.pub.publish(msg)
    def _housekeep(self):
        with self.lock:
            self.hz = float(self.t_count)
            self.t_count = 0
            link_ok = (time.monotonic() - self.last_t) < self.timeout
        if not link_ok:
            self.get_logger().warn('ESP32 link LOST - wheels zeroed')
    def destroy_node(self):
        self._send('M,0.00,0.00,0.00,0.00')
        self._send('S,0')
        self.ser.close()
        super().destroy_node()

def main():
    rclpy.init()
    node = SafetyBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
