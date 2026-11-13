"""Mass from constant-thrust plateaus: m = F_total / a_thrust (thrust along body up, v_ax<0)."""
import sys, csv, numpy as np
sys.path.insert(0, "agent_control/tools")
from tele import *
R = sys.argv[1]
F = float(sys.argv[2]) if len(sys.argv) > 2 else 211.5
d = load(R + "/telemetry.csv")
gs = list(d); root = d[gs[0]]
t = root["t"]; v = root["vel"]
r, vr, vt = radial(root)
rel = root["pos"] - C; n = rel / r[:, None]
g = np.minimum(22.0, MU / r**2)
alt = r - 600
k = np.clip(0.092 * (1 - alt / 450), 0, None)
a = np.gradient(v, t, axis=0)
thr = a + g[:, None] * n + k[:, None] * v
q = root["q"]; x, y, z, w = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
up = np.stack([2*(x*y - w*z), 1 - 2*(x*x + z*z), 2*(y*z + w*x)], axis=1)
ax = np.sum(thr * up, axis=1)
integ = root["integ"]
# plateaus = segments of constant integrity during MEAS (t window from fsw_log)
rows = [r_ for r_ in csv.reader(open(R + "/fsw_log.csv")) if len(r_) > 3 and r_[2] == "MEAS"]
t0 = float(rows[0][1]); t1 = float(rows[-1][1])
off = t[0] - 0.0
# controller t is relative to its first frame; find offset by matching: sim t = t_ctrl + t_first
import json
tfirst = None
for r_ in csv.reader(open(R + "/fsw_log.csv")):
    if r_[0] == "wall": continue
    tfirst = float(r_[1]); break
# use integrity steps directly in sim time
steps = [i for i in range(1, len(t)) if integ[i] != integ[i-1] and t[i] > 5]
print("integrity steps at sim t:", [round(t[i], 2) for i in steps], [round(integ[i], 3) for i in steps])
bounds = [steps[0] - int(0.6 / 0.04)] + steps + [steps[-1] + int(0.6 / 0.04)]
prev_m = None
for j in range(len(bounds) - 1):
    i0, i1 = bounds[j] + 5, bounds[j + 1] - 3
    seg = ax[i0:i1]
    m = F / np.mean(seg)
    print(f"plateau {j}: t={t[i0]:.2f}-{t[i1]:.2f} a_thr={np.mean(seg):.3f} +-{np.std(seg):.3f} m={m:.3f}" + (f" dropped={prev_m - m:.3f}" if prev_m else ""))
    prev_m = m
