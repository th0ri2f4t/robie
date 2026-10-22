#!/usr/bin/env python3
"""Live view of the R.O.B.I.E. SITL batch (read-only: it only reads log files, never touches ROS).
Left: path of the run in progress, with the simulated leak. Right: raw and EMA gas signal."""
import csv, glob, os
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

LOGS = os.path.expanduser('~/robie_ws/logs')
RUNLOG = os.path.expanduser('~/roc2_run.log')
LEAK = (1.5, 0.5)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

def latest():
    files = glob.glob(os.path.join(LOGS, 'roc2*', 'run_*.csv'))
    return max(files, key=os.path.getmtime) if files else None

def progress():
    try:
        lines = open(RUNLOG).read().splitlines()
    except FileNotFoundError:
        return 'no batch log yet'
    done = [l for l in lines if '->' in l]
    return '%d runs finished | last: %s' % (len(done), done[-1] if done else '-')

def update(_):
    f = latest()
    ax1.clear(); ax2.clear()
    fig.suptitle(progress(), fontsize=9)
    if not f:
        return
    rows = list(csv.DictReader(open(f)))
    if not rows:
        return
    x = [float(r['x']) for r in rows]; y = [float(r['y']) for r in rows]
    t0 = float(rows[0]['t']); t = [float(r['t']) - t0 for r in rows]
    ax1.plot(x, y, '-', lw=1)
    ax1.plot(x[-1], y[-1], 'o', label='robot now')
    ax1.plot(*LEAK, 'r*', ms=15, label='simulated leak')
    ax1.set_title('%s  |  state: %s' % (os.path.relpath(f, LOGS), rows[-1]['state']))
    ax1.set_xlabel('x (m)'); ax1.set_ylabel('y (m)'); ax1.axis('equal'); ax1.legend(loc='upper left')
    ax2.plot(t, [float(r['raw']) for r in rows], lw=0.6, label='raw')
    ax2.plot(t, [float(r['ema']) for r in rows], lw=1.5, label='EMA')
    ax2.set_xlabel('time in run (s)'); ax2.set_ylabel('gas reading (counts)'); ax2.legend(loc='upper left')

ani = FuncAnimation(fig, update, interval=1000, cache_frame_data=False)
plt.tight_layout(); plt.show()
