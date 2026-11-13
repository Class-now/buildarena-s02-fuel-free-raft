"""Lean of the payload stack: lateral offset (root body frame) of selected payload blocks vs time.
usage: an_lean.py <run_dir> t0 t1 step"""
import csv, sys, glob, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fsw.vehicle import parse_bsg
from fsw.mathx import qinv_rot
R = sys.argv[1]; t0, t1, step = float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
blocks = parse_bsg(glob.glob(os.path.join(R, "*_prepared.bsg"))[0])
fw = [b for b in blocks if b.type_id == 88]
fw.sort(key=lambda b: b.pos[1])
sel = {blocks[0].guid: 'R', fw[0].guid: 'bot', fw[len(fw) // 2].guid: 'mid', fw[-1].guid: 'top'}
d = {}
with open(R + '/telemetry.csv') as f:
    rd = csv.reader(f); next(rd)
    for r in rd:
        k = sel.get(r[2])
        if k and t0 <= float(r[1]) <= t1:
            d.setdefault(r[0], {})[k] = [float(x) for x in (r[1], r[3], r[4], r[5], r[6], r[7], r[8], r[9])]
last = -1e9
for s, v in d.items():
    if len(v) == 4 and v['R'][0] - last >= step:
        last = v['R'][0]
        q = np.array(v['R'][4:8]); p0 = np.array(v['R'][1:4])
        out = []
        for k in ('bot', 'mid', 'top'):
            b = qinv_rot(q, np.array(v[k][1:4]) - p0)
            out.append(f"{k}: lat=({b[0]:+.2f},{b[2]:+.2f}) y={b[1]:.2f}")
        print(f"t={v['R'][0]:6.2f} " + " | ".join(out))
