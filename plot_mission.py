import csv, math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

rows = []
with open('/home/th0r12f4t/robie_ws/logs/mission_demo.csv') as f:
    for row in csv.DictReader(f):
        try:
            rows.append({'t': float(row['t']), 'state': row['state'],
                         'x': float(row['x']), 'y': float(row['y']),
                         'raw': float(row['raw']), 'ema': float(row['ema'])})
        except (ValueError, KeyError):
            pass

t0 = rows[0]['t']
ts = [p['t'] - t0 for p in rows]
states = [p['state'] for p in rows]
colors = {'PATROL': 'gray', 'DRIVE': 'dodgerblue', 'TURN': 'orange',
          'HOME': 'purple', 'LOCALISED': 'red'}

loc = next((p for p in rows if p['state'] == 'LOCALISED'), None)
dist = math.hypot(loc['x'] - 1.5, loc['y'] - 0.5) if loc else float('inf')

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
for i in range(len(rows) - 1):
    c = colors.get(states[i], 'black')
    ax1.plot([rows[i]['x'], rows[i+1]['x']], [rows[i]['y'], rows[i+1]['y']],
             color=c, lw=1.2)
for p in rows:
    if p['state'] == 'LOCALISED':
        ax1.plot(p['x'], p['y'], 'ro', ms=5, alpha=0.6)
ax1.plot(1.5, 0.5, marker='*', color='red', ms=18, label='True leak (1.5, 0.5)')
if loc:
    ax1.plot(loc['x'], loc['y'], marker='X', color='green', ms=11,
             label='First localisation (%.2f m away)' % dist)
ax1.set_xlabel('x (m)'); ax1.set_ylabel('y (m)')
ax1.set_title('Full-stack mission trajectory (colour = state)')
ax1.grid(alpha=0.3); ax1.legend(); ax1.set_aspect('equal')

ax2.plot(ts, [p['raw'] for p in rows], lw=0.7, alpha=0.5, label='raw sensor')
ax2.plot(ts, [p['ema'] for p in rows], lw=2, label='EMA (filtered)')
ax2.axhline(50, color='red', ls='--', label='Trigger threshold (50)')
ax2.set_xlabel('time (s)'); ax2.set_ylabel('sensor reading')
ax2.set_title('Sensor response during mission')
ax2.grid(alpha=0.3); ax2.legend()

plt.tight_layout()
out = '/home/th0r12f4t/robie_ws/logs/mission_demo.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
print('Saved: %s' % out)
print('Localisation distance to true leak: %.2f m -> %s'
      % (dist, 'TRUE POSITIVE' if dist < 0.75 else 'FALSE NEGATIVE'))
