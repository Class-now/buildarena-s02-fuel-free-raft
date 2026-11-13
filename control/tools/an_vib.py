"""Per-block vibration at rest: rms finite-difference speed and reported speed by block type.
usage: an_vib.py <run_dir> t0 t1"""
import csv, sys, glob, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fsw.vehicle import parse_bsg
R = sys.argv[1]; t0, t1 = float(sys.argv[2]), float(sys.argv[3])
blocks = parse_bsg(glob.glob(os.path.join(R, "*_prepared.bsg"))[0])
typ = {b.guid: b.type_id for b in blocks}
idx = {b.guid: b.index for b in blocks}
d = {}
with open(R + '/telemetry.csv') as f:
    rd = csv.reader(f); hdr = next(rd)
    iv = hdr.index('vx'); ia = hdr.index('avx')
    for r in rd:
        t = float(r[1])
        if t0 <= t <= t1:
            d.setdefault(r[2], []).append((t, float(r[3]), float(r[4]), float(r[5]), float(r[iv]), float(r[iv+1]), float(r[iv+2]), float(r[ia]), float(r[ia+1]), float(r[ia+2])))
out = {}
for g, rows in d.items():
    a = np.array(rows)
    v = np.diff(a[:, 1:4], axis=0) / np.diff(a[:, 0])[:, None]
    fd = np.sqrt((v ** 2).sum(1).mean()); rep = np.sqrt((a[:, 4:7] ** 2).sum(1).mean()); av = np.sqrt((a[:, 7:10] ** 2).sum(1).mean())
    out.setdefault(typ.get(g, -1), []).append((fd, rep, av, idx.get(g, -1)))
for ty, v in sorted(out.items()):
    a = np.array(v)
    print(f"type {ty:3d} n={len(v):2d} fd rms mean={a[:,0].mean():.3f} max={a[:,0].max():.3f} | reported v mean={a[:,1].mean():.3f} max={a[:,1].max():.3f} | ang mean={a[:,2].mean():.3f} max={a[:,2].max():.3f} (idx {int(a[a[:,0].argmax(),3])})")
