import csv, math, os, time, sys
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

class GasClimber(Node):
    PATROL, DRIVE, TURN, HOME, LOCALISED = range(5)
    NAMES = ['PATROL', 'DRIVE', 'TURN', 'HOME', 'LOCALISED']

    def __init__(self):
        super().__init__('gas_climber')
        self.create_subscription(Float64, '/gas/raw', self.gas_cb, 10)
        self.create_subscription(Odometry, '/odom', self.odom_cb, 10)
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_timer(0.1, self.tick)

        self.declare_parameter('threshold', 150.0)
        self.declare_parameter('drive_speed', 0.25)
        self.declare_parameter('step_time', 2.0)
        self.declare_parameter('margin', 5.0)
        self.declare_parameter('probe_deg', 60.0)
        self.declare_parameter('max_steps', 15)
        self.declare_parameter('timeout_s', 90.0)
        self.declare_parameter('ema_alpha', 0.2)
        self.declare_parameter('home_dist', 0.15)
        self.declare_parameter('max_run_s', 0.0)  # 0.0 = infinite (manual), >0 = batch mode
        self.declare_parameter('log_file', '')

        log_path = self.get_parameter('log_file').value
        if not log_path:
            os.makedirs(os.path.expanduser('~/robie_ws/logs'), exist_ok=True)
            stamp = time.strftime('%Y%m%d_%H%M%S')
            log_path = os.path.expanduser('~/robie_ws/logs/gas_%s.csv' % stamp)
        else:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self.csv = open(log_path, 'w', newline='')
        self.writer = csv.writer(self.csv)
        self.writer.writerow(['t', 'state', 'x', 'y', 'yaw', 'raw', 'ema'])

        self.state = self.PATROL
        self.armed = True
        self.raw = self.ema = 0.0
        self.x = self.y = self.yaw = 0.0
        self.baseline = 0.0
        self.step_end = 0.0
        self.best_x = self.best_y = self.best_ema = 0.0
        self.last_good = 0.0
        self.turn_sign = 1
        self.fail_count = 0
        self.n_steps = 0
        self.pending_heading = 0.0
        self.localise_on_arrive = False
        self.hold_until = 0.0
        self.climb_start = 0.0
        self.start_time = time.time()
        self.get_logger().info('GasClimber ready, state=PATROL')

    def gas_cb(self, msg):
        self.raw = msg.data
        a = self.get_parameter('ema_alpha').value
        self.ema += a * (self.raw - self.ema)
        self.log()

    def odom_cb(self, msg):
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        self.yaw = math.atan2(2 * q.w * q.z, 1 - 2 * q.z * q.z)

    def log(self):
        self.writer.writerow([round(time.time(), 3), self.NAMES[self.state],
                              round(self.x, 3), round(self.y, 3), round(self.yaw, 3),
                              round(self.raw, 1), round(self.ema, 1)])

    def set_state(self, s):
        self.get_logger().warn('%s -> %s' % (self.NAMES[self.state], self.NAMES[s]))
        self.state = s
        self.log()

    def stop(self):
        self.cmd_pub.publish(Twist())

    def ang_diff(self, a, b):
        return (a - b + math.pi) % (2 * math.pi) - math.pi

    def start_drive(self):
        self.baseline = self.ema
        self.step_end = time.time() + self.get_parameter('step_time').value
        self.set_state(self.DRIVE)

    def go_home(self, localise):
        self.localise_on_arrive = localise
        self.set_state(self.HOME)

    def tick(self):
        now = time.time()
        th = self.get_parameter('threshold').value
        max_run = self.get_parameter('max_run_s').value

        # BULLETPROOF SHUTDOWN: If max_run > 0 and we've been patrolling too long, die.
        if max_run > 0.0 and self.state == self.PATROL and (now - self.start_time) > max_run:
            self.get_logger().info('Max run time reached in PATROL, exiting')
            raise SystemExit(0)

        if self.state == self.PATROL:
            if not self.armed and self.ema < th * 0.5:
                self.armed = True
            cmd = Twist(); cmd.linear.x = 0.15
            self.cmd_pub.publish(cmd)
            if self.armed and self.ema > th:
                self.armed = False
                self.climb_start = now
                self.n_steps = 0
                self.fail_count = 0
                self.turn_sign = 1
                self.best_x, self.best_y, self.best_ema = self.x, self.y, self.ema
                self.last_good = self.yaw
                self.start_drive()

        elif self.state == self.DRIVE:
            cmd = Twist(); cmd.linear.x = self.get_parameter('drive_speed').value
            self.cmd_pub.publish(cmd)
            if now > self.step_end:
                self.eval_step()

        elif self.state == self.TURN:
            err = self.ang_diff(self.pending_heading, self.yaw)
            if abs(err) < 0.1:
                self.stop()
                self.start_drive()
            else:
                cmd = Twist()
                cmd.angular.z = 0.8 if err > 0 else -0.8
                self.cmd_pub.publish(cmd)

        elif self.state == self.HOME:
            dist = math.hypot(self.best_x - self.x, self.best_y - self.y)
            if dist < self.get_parameter('home_dist').value:
                self.stop()
                if self.localise_on_arrive:
                    self.localise()
                else:
                    self.pending_heading = self.last_good + \
                        math.radians(self.get_parameter('probe_deg').value) * self.turn_sign
                    self.turn_sign *= -1
                    self.set_state(self.TURN)
            else:
                bearing = math.atan2(self.best_y - self.y, self.best_x - self.x)
                err = self.ang_diff(bearing, self.yaw)
                if abs(err) > 0.15:
                    cmd = Twist()
                    cmd.angular.z = 0.8 if err > 0 else -0.8
                    self.cmd_pub.publish(cmd)
                else:
                    cmd = Twist(); cmd.linear.x = self.get_parameter('drive_speed').value
                    self.cmd_pub.publish(cmd)

        elif self.state == self.LOCALISED:
            self.stop()
            if now > self.hold_until:
                # BULLETPROOF SHUTDOWN: If max_run > 0 and we finished localising, die.
                if max_run > 0.0:
                    self.get_logger().info('Localised and hold complete, exiting')
                    raise SystemExit(0)
                else:
                    self.set_state(self.PATROL)

        if self.state in (self.DRIVE, self.TURN, self.HOME) and \
           (now - self.climb_start) > self.get_parameter('timeout_s').value:
            if self.best_ema > th:
                self.get_logger().error('CLIMB TIMEOUT -> localise at best')
                self.go_home(True)
            else:
                self.get_logger().error('CLIMB TIMEOUT, no signal -> PATROL')
                self.set_state(self.PATROL)

    def eval_step(self):
        improvement = self.ema - self.baseline
        self.n_steps += 1
        self.get_logger().warn('step %d at (%.2f, %.2f): ema=%.0f improvement=%+.0f'
                               % (self.n_steps, self.x, self.y, self.ema, improvement))
        th = self.get_parameter('threshold').value

        if improvement > self.get_parameter('margin').value:
            self.fail_count = 0
            if self.ema > self.best_ema:
                self.best_x, self.best_y, self.best_ema = self.x, self.y, self.ema
                self.last_good = self.yaw
            self.start_drive()
        else:
            self.fail_count += 1
            if self.fail_count >= 3 or self.n_steps >= self.get_parameter('max_steps').value:
                if self.best_ema > th:
                    self.go_home(True)
                else:
                    self.get_logger().error('CLIMB FAILED (never above threshold) -> PATROL')
                    self.set_state(self.PATROL)
            else:
                self.go_home(False)

    def localise(self):
        self.get_logger().warn('LEAK LOCALISED at x=%.2f y=%.2f peak=%.0f'
                               % (self.x, self.y, self.best_ema))
        self.hold_until = time.time() + 5.0
        self.set_state(self.LOCALISED)

def main(args=None):
    rclpy.init(args=args)
    node = GasClimber()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass  # Clean exit triggered by our max_run_s logic
    finally:
        node.csv.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
