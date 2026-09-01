import math, os, statistics
THRESHOLDS = [50, 100, 150, 200, 250, 300]
NOISE = [0, 2, 4, 8, 16]
LEAK = (1.5, 0.5)
R = 0.75
LOG = os.path.expanduser('~/robie_ws/logs/roc')
grid = []
for th in THRESHOLDS:
    for n in NOISE:
        for lp in (True, False):
            for _ in range(3):
                grid.append((th, n, lp))
rows = []
for run_id, (th, n, lp) in enumerate(grid, 1):
    p = os.path.join(LOG, 'run_%d.csv' % run_id)
    best = 1e9
    if os.path.exists(p):
        for line in open(p, errors='ignore'):
            c = line.replace('\0', '').strip().split(',')
            if len(c) >= 4 and c[1] == 'LOCALISED':
                try:
                    d = math.hypot(float(c[2]) - LEAK[0], float(c[3]) - LEAK[1])
                    best = min(best, d)
                except ValueError:
                    pass
    rows.append((th, lp, best < R, best))
print('Thresh  TPR    FPR    MeanErr  SDErr  N_TP')
for th in THRESHOLDS:
    tp = fp = fn = tn = 0
    errs = []
    for (t, lp, hit, best) in rows:
        if t != th:
            continue
        if hit and lp: tp += 1; errs.append(best)
        elif hit: fp += 1
        elif lp: fn += 1
        else: tn += 1
    tpr = tp / (tp + fn) if tp + fn else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    m = statistics.mean(errs) if errs else float('nan')
    s = statistics.stdev(errs) if len(errs) > 1 else 0.0
    print('%6d %5.1f%% %5.1f%% %7.3f %6.3f %5d' % (th, tpr*100, fpr*100, m, s, tp))
op = [r for r in rows if r[0] == 50]
tp = sum(1 for r in op if r[1] and r[2])
fn = sum(1 for r in op if r[1] and not r[2])
fp = sum(1 for r in op if not r[1] and r[2])
tn = sum(1 for r in op if not r[1] and not r[2])
errs = [r[3] for r in op if r[1] and r[2]]
m = statistics.mean(errs) if errs else float('nan')
s = statistics.stdev(errs) if len(errs) > 1 else 0.0
print()
print('ABSTRACT SENTENCE (threshold=50):')
print('In simulation the algorithm localises a leak within %.2f +/- %.2f m (TP rate %.1f%%, FP rate %.1f%%, N=%d) at the ROC-selected operating point.' % (m, s, 100.0*tp/(tp+fn) if tp+fn else 0, 100.0*fp/(fp+tn) if fp+tn else 0, tp))
