#!/usr/bin/env python3
"""Analysis for roc_harness_v2 output. Usage: python3 roc_analysis.py [DIR] [--traj RUN_ID]"""
import csv, math, os, statistics, sys
LEAK = (1.5, 0.5); R = 0.75; PEAK = 400.0; SIGMA = 0.5
d = os.path.expanduser('~/robie_ws/logs/roc2')
args = sys.argv[1:]; traj = None
if '--traj' in args:
    i = args.index('--traj'); traj = int(args[i + 1]); del args[i:i + 2]
if args: d = os.path.expanduser(args[0])

def read_log(rid):
    pts = []
    p = os.path.join(d, 'run_%d.csv' % rid)
    if not os.path.exists(p): return None
    for line in open(p, errors='ignore'):
        c = line.replace('\0', '').strip().split(',')
        if len(c) >= 7:
            try: pts.append((float(c[0]), c[1], float(c[2]), float(c[3])))
            except ValueError: pass
    return pts

def wilson(k, n, z=1.96):
    if n == 0: return (float('nan'), float('nan'))
    ph = k / n; den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den; h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)

runs = []
for r in csv.DictReader(open(os.path.join(d, 'results.csv'))):
    rid = int(r['run_id']); pts = read_log(rid)
    if pts is None or r['status'] != 'DONE': continue
    loc = next(((x, y) for t, s, x, y in pts if s == 'LOCALISED'), None)
    err = math.hypot(loc[0] - LEAK[0], loc[1] - LEAK[1]) if loc else None
    runs.append(dict(id=rid, th=float(r['threshold']), noise=float(r['noise']), leak=r['leak'] == '1', loc=loc, err=err, mode=r['mode']))
print('Mode: %s | runs analysed: %d | success criterion: localised within %.2f m of the source\n' % (runs[0]['mode'] if runs else '-', len(runs), R))

def table(label, rows):
    L = [x for x in rows if x['leak']]; N = [x for x in rows if not x['leak']]
    tp = [x for x in L if x['err'] is not None and x['err'] <= R]
    far = [x for x in L if x['err'] is not None and x['err'] > R]
    none = [x for x in L if x['err'] is None]
    fp = [x for x in N if x['loc'] is not None]
    e = [x['err'] for x in tp]
    tpr = len(tp) / len(L) if L else float('nan'); fpr = len(fp) / len(N) if N else float('nan')
    lo, hi = wilson(len(tp), len(L)); flo, fhi = wilson(len(fp), len(N))
    m = statistics.mean(e) if e else float('nan'); s = statistics.stdev(e) if len(e) > 1 else float('nan')
    print('%-14s leak runs %2d: hit %2d, far %2d, none %2d | TPR %5.1f%% [%4.1f-%4.1f] | no-leak runs %2d: false alarms %2d | FPR %5.1f%% [%4.1f-%4.1f] | error of hits %.3f +/- %.3f m (n=%d)'
          % (label, len(L), len(tp), len(far), len(none), 100 * tpr, 100 * lo, 100 * hi, len(N), len(fp), 100 * fpr, 100 * flo, 100 * fhi, m, s, len(e)))
    return tpr, fpr

print('By threshold (all noise levels pooled):')
roc = {}
for th in sorted({x['th'] for x in runs}):
    roc[th] = table('th=%g' % th, [x for x in runs if x['th'] == th])
print('\nBy threshold and noise:')
for th in sorted({x['th'] for x in runs}):
    for n in sorted({x['noise'] for x in runs}):
        rows = [x for x in runs if x['th'] == th and x['noise'] == n]
        if rows: table('th=%g n=%g' % (th, n), rows)
try:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5, 4.5))
    pts = sorted(roc.items())
    ax.plot([v[1] for k, v in pts], [v[0] for k, v in pts], 'o-')
    for k, v in pts: ax.annotate('%g' % k, (v[1], v[0]), textcoords='offset points', xytext=(5, 4), fontsize=8)
    ax.plot([0, 1], [0, 1], '--', color='grey'); ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel('False-positive rate'); ax.set_ylabel('True-positive rate'); ax.set_title('ROC over detection thresholds (labels = threshold)')
    fig.tight_layout(); fig.savefig(os.path.join(d, 'roc_curve.png'), dpi=200); print('\nwrote roc_curve.png')
    if traj is not None:
        pts = read_log(traj); xs = [p[2] for p in pts]; ys = [p[3] for p in pts]
        import numpy as np
        g = np.linspace(-0.5, 3.5, 200); X, Y = np.meshgrid(g, np.linspace(-1.5, 2.5, 200))
        Z = PEAK * np.exp(-((X - LEAK[0]) ** 2 + (Y - LEAK[1]) ** 2) / (2 * SIGMA ** 2))
        fig, ax = plt.subplots(figsize=(6, 4.5)); cs = ax.contourf(X, Y, Z, 20, cmap='YlOrRd'); fig.colorbar(cs, label='concentration (counts)')
        ax.plot(xs, ys, 'k-', lw=1.5, label='robot path'); ax.plot(*LEAK, 'b*', ms=14, label='source')
        loc = next(((p[2], p[3]) for p in pts if p[1] == 'LOCALISED'), None)
        if loc: ax.plot(*loc, 'g^', ms=10, label='localised')
        ax.set_aspect('equal'); ax.legend(); ax.set_xlabel('x (m)'); ax.set_ylabel('y (m)')
        fig.tight_layout(); fig.savefig(os.path.join(d, 'trajectory_run_%d.png' % traj), dpi=200); print('wrote trajectory_run_%d.png' % traj)
except ImportError:
    print('\n(matplotlib not installed: skipped the plots)')
