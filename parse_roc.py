import math, os, itertools
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

THRESHOLDS = [50, 100, 150, 200, 250, 300]
NOISE_LEVELS = [0, 2, 4, 8, 16]
REPEATS = 3
LEAK_POS = (1.5, 0.5)
LOCALISE_RADIUS = 0.75
log_dir = os.path.expanduser('~/robie_ws/logs/roc')

grid = []
for threshold, noise in itertools.product(THRESHOLDS, NOISE_LEVELS):
    for leak_present in [True, False]:
        for _ in range(REPEATS):
            grid.append((threshold, noise, leak_present))

results = []
skipped = 0

for run_id, (threshold, noise, leak_present) in enumerate(grid, start=1):
    path = os.path.join(log_dir, 'run_%d.csv' % run_id)
    min_dist = float('inf')
    best_loc = None

    if os.path.exists(path) and os.path.getsize(path) > 0:
        try:
            with open(path, 'r', errors='ignore') as f:
                f.readline()  # skip header
                for line in f:
                    line = line.replace('\0', '').strip()
                    if not line: continue
                    parts = line.split(',')
                    if len(parts) >= 4 and parts[1] == 'LOCALISED':
                        try:
                            x, y = float(parts[2]), float(parts[3])
                            dist = math.hypot(x - LEAK_POS[0], y - LEAK_POS[1])
                            if dist < min_dist:
                                min_dist = dist
                                best_loc = (x, y)
                        except ValueError:
                            continue
        except Exception:
            pass
    else:
        skipped += 1

    if best_loc is not None and min_dist < LOCALISE_RADIUS:
        outcome = 'TP' if leak_present else 'FP'
    else:
        outcome = 'FN' if leak_present else 'TN'

    results.append({'threshold': threshold, 'leak_present': leak_present, 'outcome': outcome})

print('Parsed %d runs. Missing/empty files: %d' % (len(results), skipped))

threshold_stats = {}
for r in results:
    th = r['threshold']
    if th not in threshold_stats:
        threshold_stats[th] = {'tp': 0, 'fp': 0, 'fn': 0, 'tn': 0}
    if r['leak_present']:
        if r['outcome'] == 'TP': threshold_stats[th]['tp'] += 1
        else: threshold_stats[th]['fn'] += 1
    else:
        if r['outcome'] == 'FP': threshold_stats[th]['fp'] += 1
        else: threshold_stats[th]['tn'] += 1

tpr_list, fpr_list = [], []
thresholds_sorted = sorted(threshold_stats.keys())

print('\n--- ROC Summary ---')
for th in thresholds_sorted:
    s = threshold_stats[th]
    tpr = s['tp'] / (s['tp'] + s['fn']) if (s['tp'] + s['fn']) else 0
    fpr = s['fp'] / (s['fp'] + s['tn']) if (s['fp'] + s['tn']) else 0
    tpr_list.append(tpr)
    fpr_list.append(fpr)
    print('Threshold %d: TPR=%.3f FPR=%.3f (TP:%d FP:%d FN:%d TN:%d)'
          % (th, tpr, fpr, s['tp'], s['fp'], s['fn'], s['tn']))

plt.figure(figsize=(8, 6))
plt.plot(fpr_list, tpr_list, marker='o', linewidth=2, markersize=8, label='Gas Climber v3')
plt.plot([0, 1], [0, 1], 'k--', alpha=0.5, label='Random guess')
plt.xlabel('False Positive Rate (1 - Specificity)')
plt.ylabel('True Positive Rate (Sensitivity)')
plt.title('ROC Curve: Gas Leak Detection Performance')
plt.grid(True, alpha=0.3)
plt.legend()
plt.xlim([-0.05, 1.05])
plt.ylim([-0.05, 1.05])
for i, th in enumerate(thresholds_sorted):
    plt.annotate('%d' % th, (fpr_list[i], tpr_list[i]), textcoords='offset points', xytext=(6, 4), fontsize=9)

roc_path = os.path.expanduser('~/robie_ws/logs/roc_curve_final.png')
plt.savefig(roc_path, dpi=150, bbox_inches='tight')
print('\nROC curve saved to: %s' % roc_path)
