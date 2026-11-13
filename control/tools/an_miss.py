"""Closest approach between the launcher root and the payload (top flywheel) after separation.
usage: an_miss.py <run_dir> <t_after>"""
import csv, sys, glob, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fsw.vehicle import parse_bsg
R = sys.argv[1]; t_after = float(sys.argv[2])
blocks = parse_bsg(glob.glob(os.path.join(R, "*_prepared.bsg"))[0])
fw = sorted([b for b in blocks if b.type_id == 88], key=lambda b: b.pos[1])
gr, gp = blocks[0].guid, fw[len(fw) // 2].guid
a, b = {}, {}
with open(R + '/telemetry.csv') as f:
    rd = csv.reader(f); next(rd)
    for r in rd:
        if float(r[1]) < t_after: continue
        if r[2] == gr: a[r[0]] = (float(r[1]), float(r[3]), float(r[4]), float(r[5]))
        elif r[2] == gp: b[r[0]] = (float(r[3]), float(r[4]), float(r[5]))
best = []
for k, v in a.items():
    if k in b:
        d = float(np.linalg.norm(np.array(v[1:]) - np.array(b[k])))
        best.append((d, v[0], np.linalg.norm(np.array(v[1:]) + np.array([0, 600.0, 0])), np.linalg.norm(np.array(b[k]) + np.array([0, 600.0, 0]))))
best.sort()
for d, t, rv, rp in best[:1]:
    print(f"closest approach {d:.1f} at t={t:.2f}: vehicle r={rv:.1f} payload r={rp:.1f}")
# local minima per orbit pass
arr = sorted((t, d, rv, rp) for d, t, rv, rp in best)
for i in range(1, len(arr) - 1):
    if arr[i][1] < arr[i - 1][1] and arr[i][1] <= arr[i + 1][1] and arr[i][1] < 400:
        print(f"  pass: t={arr[i][0]:.2f} dist={arr[i][1]:.1f} vehicle r={arr[i][2]:.1f} payload r={arr[i][3]:.1f}")
