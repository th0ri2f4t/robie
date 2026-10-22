#!/usr/bin/env python3
"""R.O.B.I.E. SITL batch harness v3 (laptop, ROS 2 Humble).
Each run is ONE process (tools/sitl_runner.py) in its own process group, killed as a group afterwards,
so nothing survives into the next run. The row count of every run log is checked; the batch stops
after 3 empty logs in a row so an overnight run cannot silently produce nothing."""
import argparse, csv, os, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, 'sitl_runner.py')

p = argparse.ArgumentParser()
p.add_argument('--out', default=os.path.expanduser('~/robie_ws/logs/roc2'))
p.add_argument('--thresholds', type=float, nargs='+', default=[50, 100, 150, 200])
p.add_argument('--noise', type=float, nargs='+', default=[0, 2, 4, 8, 16])
p.add_argument('--repeats', type=int, default=3)
p.add_argument('--mode', choices=['full', 'noema', 'nohyst', 'raw'], default='full')
p.add_argument('--dry', action='store_true', help='print the plan and exit')
a = p.parse_args()

def params(threshold, mode):
    alpha = 1.0 if mode in ('noema', 'raw') else 0.2
    exit_th = threshold if mode in ('nohyst', 'raw') else threshold * 0.6
    return alpha, exit_th

def kill_group(proc):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try: os.killpg(os.getpgid(proc.pid), sig)
        except ProcessLookupError: return
        time.sleep(0.4)

def rows_in(path):
    try:
        with open(path) as f: return sum(1 for _ in f) - 1
    except FileNotFoundError:
        return -1

def run_single(run_id, threshold, noise, leak, mode):
    log = os.path.join(a.out, 'run_%d.csv' % run_id)
    alpha, exit_th = params(threshold, mode)
    cmd = ['python3', RUNNER, '--ros-args',
           '-p', 'plume_sim:peak:=%f' % (400.0 if leak else 0.0),
           '-p', 'plume_sim:noise_sigma:=%f' % noise,
           '-p', 'gas_climber:threshold:=%f' % threshold,
           '-p', 'gas_climber:exit_threshold:=%f' % exit_th,
           '-p', 'gas_climber:ema_alpha:=%f' % alpha,
           '-p', 'gas_climber:log_file:=%s' % log,
           '-p', 'gas_climber:max_run_s:=60.0',
           '-p', 'gas_climber:timeout_s:=90.0']
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        proc.wait(timeout=180); status = 'DONE'
    except subprocess.TimeoutExpired:
        status = 'TIMEOUT'
    kill_group(proc)
    time.sleep(0.5)
    return status, time.time() - t0, rows_in(log)

grid = [(th, n, leak, r) for th in a.thresholds for n in a.noise for leak in (True, False) for r in range(a.repeats)]
print('mode=%s  runs=%d  out=%s' % (a.mode, len(grid), a.out), flush=True)
if a.dry: sys.exit(0)
if not os.path.exists(RUNNER): sys.exit('sitl_runner.py not found next to this script: ' + RUNNER)
os.makedirs(a.out, exist_ok=True)
resf = os.path.join(a.out, 'results.csv')
new = not os.path.exists(resf)
start = 1
if not new:
    with open(resf) as f: start = sum(1 for _ in f)
empty = 0
with open(resf, 'a', newline='') as f:
    w = csv.writer(f)
    if new: w.writerow(['run_id', 'threshold', 'noise', 'leak', 'repeat', 'mode', 'status', 'seconds', 'rows'])
    for i, (th, n, leak, r) in enumerate(grid, 1):
        if i < start: continue
        st, sec, rows = run_single(i, th, n, leak, a.mode)
        w.writerow([i, th, n, int(leak), r, a.mode, st, round(sec, 1), rows]); f.flush()
        print('[%d/%d] th=%g noise=%g leak=%s -> %s (%.0f s, %d rows)' % (i, len(grid), th, n, leak, st, sec, rows), flush=True)
        empty = empty + 1 if rows <= 0 else 0
        if empty >= 3:
            sys.exit('STOPPED: 3 empty logs in a row - the nodes are not exchanging data.')
print('Batch complete.', flush=True)
