"""Ground-rest quality of the root block: drift and jitter over the last part of a run.
usage: an_rest.py <run_dir> [t0 t1]"""
import csv, sys
import numpy as np
R = sys.argv[1]
rows = []
with open(R + '/telemetry.csv') as f:
    rd = csv.reader(f); hdr = next(rd); g0 = None
    for r in rd:
        if g0 is None: g0 = r[2]
        if r[2] == g0: rows.append((float(r[1]), float(r[3]), float(r[4]), float(r[5])))
a = np.array(rows); t, p = a[:, 0], a[:, 1:]
t0 = float(sys.argv[2]) if len(sys.argv) > 2 else t[-1] - 30
t1 = float(sys.argv[3]) if len(sys.argv) > 3 else t[-1]
m = (t >= t0) & (t <= t1)
d = p[m][-1] - p[m][0]
v = np.diff(p[m], axis=0) / np.diff(t[m])[:, None]
sp = np.sqrt((v ** 2).sum(1))
# 1-s averaged speed (what a scorer with smoothing would see)
n = 25
v1 = (p[m][n:] - p[m][:-n]) / (t[m][n:] - t[m][:-n])[:, None]
print(f"{t0:.1f}-{t1:.1f}: drift={np.linalg.norm(d):.3f} ({np.linalg.norm(d)/(t1-t0):.4f}/s) fd-speed rms={np.sqrt((sp**2).mean()):.3f} max={sp.max():.3f}  1s-avg speed max={np.sqrt((v1**2).sum(1)).max():.3f}")
