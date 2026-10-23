#!/usr/bin/env python3
"""R.O.B.I.E. web_bridge: ROS 2 <-> Mission Control protocol bridge.
Emits P/T/H/B/G/Z and event lines as UDP to 127.0.0.1:9999 (server.py ros mode).
Listens on UDP 9998 for W/D/E/A commands and maps them to ROS 2 actions.
v1 goto is a straight-line mecanum translation; swap for a Nav2 action client in v2.
"""
import base64
import math
import queue
import socket
import threading
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, Float32, Int32MultiArray, String
from robie_msgs.msg import SafetyState

SERVER_ADDR = ("127.0.0.1", 9999)
CMD_PORT = 9998

class WebBridge(Node):
    def __init__(self):
        super().__init__('web_bridge')
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cmd_sock.bind(("127.0.0.1", CMD_PORT))
        self.cmd_sock.settimeout(0.2)
        self.cmdq = queue.Queue()
        threading.Thread(target=self._cmd_loop, daemon=True).start()
        self.safety = (False, False, False)
        self.pose = None
        self.scan = None
        self.gas = None
        self.batt = None
        self.vel = None
        self.vel_until = 0.0
        self.target = None
        self.remote_estop = False
        self.t0 = time.time()
        self.create_subscription(SafetyState, '/safety_state', self._on_safety, 10)
        self.create_subscription(PoseStamped, '/pose', self._on_pose, 10)
        self.create_subscription(PoseStamped, '/amcl_pose', self._on_pose, 10)
        self.create_subscription(LaserScan, '/scan', self._on_scan, 10)
        self.create_subscription(Int32MultiArray, '/robie/gas', self._on_gas, 10)
        self.create_subscription(Float32, '/robie/battery', self._on_batt, 10)
        self.create_subscription(String, '/robie/event', self._on_event, 10)
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.estop_pub = self.create_publisher(Bool, '/sw/estop', 10)
        self.create_timer(0.05, self._tick)
        self.create_timer(0.4, self._scan_tick)
        self.create_timer(1.0, self._hb)
        self.get_logger().info('web_bridge up: lines->9999, cmds<-9998')
    def _emit(self, line):
        try:
            self.sock.sendto(line.encode(), SERVER_ADDR)
        except Exception:
            pass
    def _cmd_loop(self):
        while True:
            try:
                data, _ = self.cmd_sock.recvfrom(512)
            except Exception:
                time.sleep(0.05)
                continue
            self.cmdq.put(data.decode(errors='ignore').strip())
    def _on_safety(self, m):
        self.safety = (m.estop_pressed, m.bumper_front, m.bumper_rear)
    def _on_pose(self, m):
        q = m.pose.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        self.pose = (m.pose.position.x, m.pose.position.y, yaw)
    def _on_scan(self, m):
        self.scan = m
    def _on_gas(self, m):
        if len(m.data) >= 2:
            self.gas = (int(m.data[0]), int(m.data[1]))
    def _on_batt(self, m):
        self.batt = float(m.data)
    def _on_event(self, m):
        self._emit(m.data)
    def _tick(self):
        now = time.monotonic()
        while not self.cmdq.empty():
            self._command(self.cmdq.get())
        e, bf, br = self.safety
        self._emit('T,%d,%d,%d' % (1 if e else 0, 1 if bf else 0, 1 if br else 0))
        if self.pose is not None:
            self._emit('P,%.2f,%.2f,%.2f' % self.pose)
        if self.gas is not None:
            self._emit('G,%d,%d' % self.gas)
        if self.batt is not None:
            self._emit('B,%.2f' % self.batt)
        tw = Twist()
        active = False
        if self.vel is not None and now < self.vel_until:
            tw.linear.x = self.vel[0]
            tw.linear.y = self.vel[1]
            tw.angular.z = self.vel[2]
            active = True
        elif self.target is not None and self.pose is not None:
            dx = self.target[0] - self.pose[0]
            dy = self.target[1] - self.pose[1]
            d = math.hypot(dx, dy)
            if d < 0.15:
                self.target = None
            else:
                speed = min(0.5, 0.8 * d)
                wx = dx / d * speed
                wy = dy / d * speed
                c = math.cos(self.pose[2])
                s = math.sin(self.pose[2])
                tw.linear.x = wx * c + wy * s
                tw.linear.y = -wx * s + wy * c
                active = True
        if active and not self.remote_estop:
            self.cmd_pub.publish(tw)
    def _scan_tick(self):
        m = self.scan
        if m is None or len(m.ranges) == 0:
            return
        n = len(m.ranges)
        out = []
        for a in range(360):
            i = int(a / 360.0 * n) % n
            r = m.ranges[i]
            if not math.isfinite(r) or r <= 0.05:
                r = 8.0
            out.append(max(1, min(80, int(r * 10))))
        self._emit('Z,' + base64.b64encode(bytes(out)).decode())
    def _hb(self):
        self._emit('H,%d' % int((time.time() - self.t0) * 1000))
    def _command(self, line):
        p = line.split(',')
        if p[0] == 'D' and len(p) == 4:
            self.vel = (float(p[1]), float(p[2]), float(p[3]))
            self.vel_until = time.monotonic() + 0.5
            self.target = None
        elif p[0] == 'W' and len(p) == 3:
            self.target = (float(p[1]), float(p[2]))
            self.vel = None
        elif p[0] == 'E' and len(p) == 2:
            self.remote_estop = p[1] == '1'
            b = Bool()
            b.data = self.remote_estop
            self.estop_pub.publish(b)
        elif p[0] == 'A' and len(p) == 2:
            self.vel = None
            self.target = None
            self.get_logger().info('autonomy handoff: bridge teleop cleared')

def main():
    rclpy.init()
    node = WebBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
