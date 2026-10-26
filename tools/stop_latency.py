#!/usr/bin/env python3
"""Measure the operator-stop interval on the Pi (run with robie.launch.py already running and the WHEELS OFF THE SURFACE).
For each trial it keeps commanding forward motion, sends POST /estop to the safety_node endpoint, and times:
  reply      the HTTP reply from the endpoint
  enable     the first /motor_enable = False
  zero       the first all-zero message on the drive topic after the stop
  last_move  the last non-zero message on the drive topic after the stop
Usage: python3 stop_latency.py --drive-topic <topic> [--cmd-topic /cmd_vel] [--trials 5] [--speed 0.3]"""
import argparse, csv, os, statistics, sys, threading, time, urllib.request

def post(url):
    t = time.perf_counter()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=b'', method='POST'), timeout=2).read()
    except Exception as e:
        print('POST failed:', url, e); sys.exit(1)
    return t, time.perf_counter()

def all_zero(d, eps=1e-6):
    if isinstance(d, dict): return all(all_zero(v, eps) for v in d.values() if not isinstance(v, str))
    if isinstance(d, (list, tuple)): return all(all_zero(v, eps) for v in d)
    if isinstance(d, bool): return True
    if isinstance(d, (int, float)): return abs(d) < eps
    return True

def summarise(rows):
    out = {}
    for k in ('reply', 'enable', 'zero', 'last_move'):
        v = [r[k] for r in rows if r.get(k) is not None]
        out[k] = (statistics.mean(v), statistics.pstdev(v) if len(v) > 1 else 0.0, min(v), max(v), len(v)) if v else None
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--drive-topic', required=True); ap.add_argument('--cmd-topic', default='/cmd_vel'); ap.add_argument('--trials', type=int, default=5); ap.add_argument('--speed', type=float, default=0.3); ap.add_argument('--url', default='http://127.0.0.1:8082')
    a = ap.parse_args()
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Bool
    from geometry_msgs.msg import Twist
    from rosidl_runtime_py.utilities import get_message
    from rosidl_runtime_py.convert import message_to_ordereddict
    rclpy.init(); node = Node('stop_latency')
    types = {}
    for _ in range(50):
        types = dict(node.get_topic_names_and_types())
        if a.drive_topic in types: break
        time.sleep(0.1)
    if a.drive_topic not in types:
        print('Drive topic not found. Topics that look relevant:'); [print('  ', t) for t in sorted(types) if any(k in t for k in ('motor', 'wheel', 'target', 'cmd'))]; sys.exit(1)
    mtype = get_message(types[a.drive_topic][0]); print('drive topic', a.drive_topic, 'type', types[a.drive_topic][0])
    log = {'drive': [], 'enable': []}; lock = threading.Lock()
    node.create_subscription(mtype, a.drive_topic, lambda m: log['drive'].append((time.perf_counter(), all_zero(message_to_ordereddict(m)))), 50)
    node.create_subscription(Bool, '/motor_enable', lambda m: log['enable'].append((time.perf_counter(), bool(m.data))), 50)
    pub = node.create_publisher(Twist, a.cmd_topic, 10)
    def send():
        m = Twist(); m.linear.x = a.speed; pub.publish(m)
    node.create_timer(0.05, send)
    th = threading.Thread(target=rclpy.spin, args=(node,), daemon=True); th.start()
    rows = []; print('Keep a hand on the 12 V adapter. Wheels must be off the surface. Starting in 3 s...'); time.sleep(3)
    for n in range(1, a.trials + 1):
        post(a.url + '/reset'); time.sleep(1.5)
        moving = [z for t, z in log['drive'][-10:] if not z]
        if not moving: print('Trial %d: the drive topic is not carrying motion before the stop; check --drive-topic and --cmd-topic' % n)
        log['drive'].clear(); log['enable'].clear()
        t0, t_reply = post(a.url + '/estop'); time.sleep(1.2)
        drive = [(t, z) for t, z in log['drive'] if t >= t0]; enable = [(t, v) for t, v in log['enable'] if t >= t0 and not v]
        zero = next((t for t, z in drive if z), None); moving_after = [t for t, z in drive if not z]
        r = {'trial': n, 'reply': (t_reply - t0) * 1000, 'enable': (enable[0][0] - t0) * 1000 if enable else None, 'zero': (zero - t0) * 1000 if zero else None, 'last_move': (moving_after[-1] - t0) * 1000 if moving_after else None}
        rows.append(r); print('Trial %d  reply %s  enable_false %s  drive_zero %s  last_nonzero %s  (ms)' % (n, *['%.0f' % r[k] if r[k] is not None else 'n/a' for k in ('reply', 'enable', 'zero', 'last_move')]))
        post(a.url + '/reset'); time.sleep(0.8)
    post(a.url + '/reset')
    path = os.path.expanduser('~/stop_latency.csv')
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['trial', 'reply', 'enable', 'zero', 'last_move']); w.writeheader(); w.writerows(rows)
    print('\nSummary (ms): mean, sd, min, max, n')
    for k, v in summarise(rows).items(): print('  %-10s %s' % (k, ('%.0f %.0f %.0f %.0f %d' % v) if v else 'n/a'))
    print('Saved', path); rclpy.shutdown()
if __name__ == '__main__': main()
