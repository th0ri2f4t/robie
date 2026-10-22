#!/usr/bin/env python3
"""R.O.B.I.E. SITL batch harness v2 (run on the laptop, ROS 2 Humble).
Each run gets its own ROS_DOMAIN_ID and process group, so a node left over from an earlier run
cannot publish into a later one; each run's configuration is written to results.csv."""
import argparse, csv, os, signal, subprocess, sys, time

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
    try: os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError: pass
    time.sleep(0.4)
    try: os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError: pass

def run_single(run_id, threshold, noise, leak, mode):
    log = os.path.join(a.out, 'run_%d.csv' % run_id)
    alpha, exit_th = params(threshold, mode)
    env = dict(os.environ, ROS_DOMAIN_ID=str(10 + run_id % 90))
    plume = ['ros2', 'run', 'robie_gas', 'plume_sim', '--ros-args',
             '-p', 'peak:=%f' % (400.0 if leak else 0.0), '-p', 'noise_sigma:=%f' % noise]
    clim = ['ros2', 'run', 'robie_gas', 'gas_climber', '--ros-args',
            '-p', 'threshold:=%f' % threshold, '-p', 'exit_threshold:=%f' % exit_th,
            '-p', 'ema_alpha:=%f' % alpha, '-p', 'log_file:=%s' % log,
            '-p', 'max_run_s:=60.0', '-p', 'timeout_s:=90.0']
    t0 = time.time()
    pp = subprocess.Popen(plume, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(1.5)
    cp = subprocess.Popen(clim, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        cp.wait(timeout=110); status = 'DONE'
    except subprocess.TimeoutExpired:
        status = 'TIMEOUT'
    kill_group(cp); kill_group(pp)
    time.sleep(0.5)
    return status, time.time() - t0

grid = [(th, n, leak, r) for th in a.thresholds for n in a.noise for leak in (True, False) for r in range(a.repeats)]
print('mode=%s  runs=%d  out=%s' % (a.mode, len(grid), a.out))
if a.dry: sys.exit(0)
os.makedirs(a.out, exist_ok=True)
resf = os.path.join(a.out, 'results.csv')
new = not os.path.exists(resf)
start = 1
if not new:
    with open(resf) as f: start = sum(1 for _ in f)
with open(resf, 'a', newline='') as f:
    w = csv.writer(f)
    if new: w.writerow(['run_id', 'threshold', 'noise', 'leak', 'repeat', 'mode', 'status', 'seconds'])
    for i, (th, n, leak, r) in enumerate(grid, 1):
        if i < start: continue
        st, sec = run_single(i, th, n, leak, a.mode)
        w.writerow([i, th, n, int(leak), r, a.mode, st, round(sec, 1)]); f.flush()
        print('[%d/%d] th=%g noise=%g leak=%s -> %s (%.0f s)' % (i, len(grid), th, n, leak, st, sec), flush=True)
print('Batch complete.')
