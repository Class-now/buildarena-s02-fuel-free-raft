"""Arm flex: deflection of a block relative to the root along the root's body +Y, in a time window.
usage: an_flex.py <run_dir> t0 t1 idx[,idx]"""
import csv, sys, glob, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fsw.vehicle import parse_bsg
from fsw.mathx import qrot
R = sys.argv[1]; t0, t1 = float(sys.argv[2]), float(sys.argv[3]); want = [int(x) for x in sys.argv[4].split(",")]
blocks = parse_bsg(glob.glob(os.path.join(R, "*_prepared.bsg"))[0])
g2i = {b.guid: b.index for b in blocks if b.index in want or b.index == 0}
d = {}
with open(R + '/telemetry.csv') as f:
    rd = csv.reader(f); next(rd)
    for r in rd:
        if r[2] in g2i and t0 <= float(r[1]) <= t1:
            d.setdefault(g2i[r[2]], {})[r[0]] = [float(r[1])] + [float(x) for x in r[3:10]]
for i in want:
    ts, defl = [], []
    for k, v in d[i].items():
        if k in d[0]:
            ro = d[0][k]
            up = qrot(np.array(ro[4:8]), np.array([0.0, 1.0, 0.0]))
            ts.append(v[0]); defl.append(float(np.dot(np.array(v[1:4]) - np.array(ro[1:4]), up)))
    ts, defl = np.array(ts), np.array(defl)
    x = defl - defl.mean(); n = len(x); dt = np.median(np.diff(ts))
    sp = np.abs(np.fft.rfft(x * np.hanning(n))); fr = np.fft.rfftfreq(n, dt); k = np.argsort(sp)[-3:][::-1]
    print(f"idx {i}: mean defl={defl.mean():.3f} std={x.std():.4f} peaks=" + ",".join(f"{fr[j]:.1f}Hz" for j in k))
