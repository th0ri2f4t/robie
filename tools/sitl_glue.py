#!/usr/bin/env python3
"""SITL fixture: translates sim outputs into web_bridge protocol topics.
1) GasReading.raw on /robie/gas_sim -> Int32MultiArray raw counts on /robie/gas.
2) Human-readable /robie/event strings -> L,/C, CSV the dashboard renders.
Retired on the real robot, where gas_node publishes raw ADC counts directly."""
import re
import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32MultiArray, String
try:
    from robie_msgs.msg import GasReading
except Exception:
    GasReading = None

LEAK_RE = re.compile(r'x=(-?\d+\.?\d*).*?y=(-?\d+\.?\d*).*?peak=(\d+)')

class SitlGlue(Node):
    def __init__(self):
        super().__init__('sitl_glue')
        self.gas_pub = self.create_publisher(Int32MultiArray, '/robie/gas', 10)
        self.event_pub = self.create_publisher(String, '/robie/event', 10)
        if GasReading is not None:
            self.create_subscription(GasReading, '/robie/gas_sim', self._gas, 10)
        self.create_subscription(String, '/robie/event', self._event, 10)
        self.get_logger().info('sitl_glue up: gas_sim.raw->counts, event text->L/C CSV')

    def _gas(self, m):
        raw = float(m.raw)
        arr = Int32MultiArray()
        # MQ-4: raw ADC (0-4095), scale to realistic range
        # MQ-6: slightly different response curve
        arr.data = [max(0, min(4095, int(600 + raw * 0.15))),
                    max(0, min(4095, int(480 + raw * 0.10)))]
        self.gas_pub.publish(arr)

    def _event(self, m):
        t = m.data.strip()
        if t.startswith(('L,', 'C,')): return   # our own CSV republish: no loop
        kind = 'L' if 'LEAK' in t.upper() else ('C' if 'CRACK' in t.upper() else None)
        mt = LEAK_RE.search(t)
        if kind is None or not mt: return
        x, y, peak = float(mt.group(1)), float(mt.group(2)), float(mt.group(3))
        conf = max(0.0, min(1.0, peak / 500.0))
        self.event_pub.publish(String(data='%s,%.2f,%.2f,%.2f' % (kind, conf, x, y)))

def main():
    rclpy.init(); rclpy.spin(SitlGlue())

if __name__ == '__main__': main()
