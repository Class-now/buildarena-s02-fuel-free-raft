"""Tilt of the root block's +Y axis relative to the normal of the plane through the four outer arm poles (thrust plane),
in root-body coordinates, for time windows. usage: an_tilt.py <run_dir> t0,t1 [t0,t1 ...]"""
import csv, sys, glob, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fsw.vehicle import parse_bsg
from fsw.mathx import qinv_rot
R = sys.argv[1]
blocks = parse_bsg(glob.glob(os.path.join(R, "*_prepared.bsg"))[0])
poles = [b for b in blocks if b.type_id == 41]
def far(ax, sg): return max(poles, key=lambda b: sg * b.pos[ax]).guid
gE, gW, gN, gS = far(0, 1), far(0, -1), far(2, 1), far(2, -1)
want = {blocks[0].guid: 'R', gE: 'E', gW: 'W', gN: 'N', gS: 'S'}
d = {}
with open(R + '/telemetry.csv') as f:
    rd = csv.reader(f); next(rd)
    for r in rd:
        k = want.get(r[2])
        if k: d.setdefault(r[0], {})[k] = [float(x) for x in (r[1], r[3], r[4], r[5], r[6], r[7], r[8], r[9])]
rows = []
for s, v in d.items():
    if len(v) == 5:
        nrm = np.cross(np.array(v['N'][1:4]) - np.array(v['S'][1:4]), np.array(v['E'][1:4]) - np.array(v['W'][1:4]))
        nb = qinv_rot(np.array(v['R'][4:8]), nrm / np.linalg.norm(nrm))
        rows.append((v['R'][0], nb[0], nb[1], nb[2]))
a = np.array(rows)
for w in sys.argv[2:]:
    t0, t1 = [float(x) for x in w.split(",")]
    m = (a[:, 0] >= t0) & (a[:, 0] <= t1)
    print(f"{t0:.0f}-{t1:.0f}: plane normal in body frame x={a[m][:,1].mean():+.4f} y={a[m][:,2].mean():+.4f} z={a[m][:,3].mean():+.4f}  (std x {a[m][:,1].std():.4f} z {a[m][:,3].std():.4f}) tilt={np.degrees(np.hypot(a[m][:,1].mean(), a[m][:,3].mean())):.2f} deg")
