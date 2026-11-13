"""Average non-gravitational, non-model-drag acceleration (world + body frame) per fsw phase label."""
import sys, csv, numpy as np
sys.path.insert(0, "agent_control/tools")
from tele import *
R = sys.argv[1]
d = load(R + "/telemetry.csv")
gs = list(d); root = d[gs[0]]
t = root["t"]; v = root["vel"]
r, vr, vt = radial(root)
rel = root["pos"] - C; n = rel / r[:, None]
g = np.minimum(22.0, MU / r**2)
alt = r - 600
k = np.clip(0.092 * (1 - alt / 450), 0, None)
a = np.gradient(v, t, axis=0)
res = a + g[:, None] * n + k[:, None] * v
q = root["q"]
def inv_rot(q, v):
    x, y, z, w = -q[:, 0], -q[:, 1], -q[:, 2], q[:, 3]
    u = np.stack([x, y, z], axis=1)
    return v + 2 * np.cross(u, np.cross(u, v) + w[:, None] * v)
resb = inv_rot(q, res)
vb = inv_rot(q, v)
rows = list(csv.reader(open(R + "/fsw_log.csv")))[1:]
t0 = t[0] - float(rows[0][1])  # sim time offset of controller t
# controller t=0 corresponds to the first frame it saw; find offset from first PRE row wall? use first telemetry time ~3.1
import bisect
phases = {}
for r_ in rows:
    phases.setdefault(r_[2], []).append(float(r_[1]))
tfirst = None
# estimate offset: controller t = sim_time - sim_time_first_frame; the first controller frame is at about sim 3.1-3.7 s
# use fuel: find the first sim sample where fuel drops and the first log row where fuel drops
fuel_tot = np.nansum(np.stack([np.nan_to_num(d[g_]["fuel"][:len(t)]) for g_ in gs if len(d[g_]["t"]) >= len(t)]), axis=0)
i_sim = int(np.argmax(fuel_tot < fuel_tot[0] - 0.01))
j = next(i for i, r_ in enumerate(rows) if float(r_[8]) < float(rows[0][8]) - 0.01)
off = t[i_sim] - float(rows[j][1])
print("time offset", round(off, 2))
for ph, ts in phases.items():
    if not (ph.startswith("RCS") or ph == "COAST"):
        continue
    lo, hi = min(ts) + off + 0.3, max(ts) + off - 0.1
    m = (t >= lo) & (t <= hi)
    if m.sum() < 3: continue
    print(f"{ph:12s} t={lo:.2f}-{hi:.2f} res_world={np.round(res[m].mean(axis=0), 3)} res_body={np.round(resb[m].mean(axis=0), 3)} v_body={np.round(vb[m].mean(axis=0), 1)} alt={alt[m].mean():.0f}")
