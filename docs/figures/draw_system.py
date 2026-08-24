import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon

fig, ax = plt.subplots(figsize=(9, 14), dpi=200)
ax.set_xlim(0, 10); ax.set_ylim(0, 22); ax.axis('off')

C_PROC, C_DEC, C_SENSE, C_SAFE, C_OK = "#D9E6F2", "#F2D9D9", "#EDEDED", "#F2D9D9", "#FFF6D6"
E = "#7A96B8"

def box(x, y, text, kind='proc', w=2.6, h=1.0):
    if kind == 'dec':
        pts = [(x, y+0.6), (x+w*0.62, y), (x, y-0.6), (x-w*0.62, y)]
        ax.add_patch(Polygon(pts, closed=True, facecolor=C_DEC, edgecolor=E))
    else:
        col = {'proc': C_PROC, 'sense': C_SENSE, 'safe': C_SAFE, 'op': C_OK, 'term': "#CDE5CD"}[kind]
        r = 0.35 if kind in ('term', 'safe', 'op') else 0.12
        ax.add_patch(FancyBboxPatch((x-w/2, y-h/2), w, h,
                   boxstyle=f"round,pad=0.08,rounding_size={r}", facecolor=col, edgecolor=E))
    ax.text(x, y, text, ha='center', va='center', fontsize=8.5, zorder=5)

def arrow(x1, y1, x2, y2, label='', dashed=False, rad=0):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(
        arrowstyle="-|>", color="#404040", shrinkA=6, shrinkB=6,
        linestyle='dashed' if dashed else 'solid',
        connectionstyle=f"arc3,rad={rad}"), zorder=1)
    if label:
        ax.text((x1+x2)/2 + 0.12, (y1+y2)/2, label, fontsize=7.5, color="#333")

box(5, 21,   "Robot boot\n(sensors initialize)", 'term')
box(5, 19.2, "1. Sensors publish\nLiDAR / MQ-4 / encoders", 'sense')
box(3, 17.2, "2. SLAM Toolbox\nmap + pose")
box(7, 16.4, "3. Gas filter\nEMA alpha = 0.15")
box(3, 14.4, "4. Nav2\nplan + avoid")
box(7, 13.6, "5. Gas controller\npatrol / climb / home")
box(2.0, 11.6, "6. Safety interlock\nenabled ?", 'dec', w=2.4)
box(5, 11.6, "7. Motor arbiter\nblend x gate")
box(5, 9.8,  "8. Serial bridge\nROS <-> UART")
box(5, 8.0,  "9. ESP32 firmware\nwatchdog")
box(5, 6.2,  "10. Link OK ?", 'dec', w=2.2)
box(5, 4.4,  "11. Mecanum IK\n+ drivers")
box(5, 2.6,  "12. Robot moves", 'term')
box(8.2, 6.2, "MOTORS CUT", 'safe', w=2.0, h=0.8)
box(8.2, 2.6, "Telemetry ->\nground station", 'op', w=2.2)

arrow(5, 20.5, 5, 19.7)
arrow(4.2, 18.7, 3.2, 17.7, "/scan")
arrow(5.8, 18.7, 6.8, 16.9, "/gas/raw")
arrow(3, 16.7, 3, 14.9, "/map, /pose")
arrow(7, 15.9, 7, 14.1, "g_ema")
arrow(3.4, 13.9, 4.4, 12.1, "/cmd_vel (NAV)")
arrow(6.6, 13.1, 5.6, 12.1, "/cmd_vel (CLIMB)")
arrow(3.5, 11.6, 3.7, 11.6, "motor_enable")
arrow(5, 11.1, 5, 10.3, "/motor_targets")
arrow(5, 9.3, 5, 8.5, "UART")
arrow(5, 7.5, 5, 6.8)
arrow(4.8, 5.7, 4.8, 4.9, "Yes")
arrow(6.4, 6.2, 7.2, 6.2, "No")
arrow(5, 3.9, 5, 3.1)
arrow(6.3, 2.6, 7.1, 2.6, "", True)
arrow(8.2, 3.1, 6.3, 19.2, "cycle repeats", True, rad=-0.3)

plt.savefig('/home/th0r12f4t/robie_ws/docs/figures/robie_system_mpl.png',
            dpi=200, bbox_inches='tight')
print("saved robie_system_mpl.png")
