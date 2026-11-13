"""Dominant vibration frequencies of selected blocks (by bsg index) in a time window.
usage: an_spec.py <run_dir> t0 t1 idx[,idx...]"""
import csv, sys, glob, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fsw.vehicle import parse_bsg
R = sys.argv[1]; t0, t1 = float(sys.argv[2]), float(sys.argv[3]); want = [int(x) for x in sys.argv[4].split(",")]
blocks = parse_bsg(glob.glob(os.path.join(R, "*_prepared.bsg"))[0])
g2i = {b.guid: b.index for b in blocks if b.index in want}
d = {}
with open(R + '/telemetry.csv') as f:
    rd = csv.reader(f); next(rd)
    for r in rd:
        if r[2] in g2i and t0 <= float(r[1]) <= t1:
            d.setdefault(g2i[r[2]], []).append((float(r[1]), float(r[3]), float(r[4]), float(r[5])))
for i in want:
    a = np.array(d[i]); dt = np.median(np.diff(a[:, 0])); n = len(a)
    fr = np.fft.rfftfreq(n, dt)
    s = ""
    for ax, name in ((1, "x"), (2, "y"), (3, "z")):
        x = a[:, ax] - np.polyval(np.polyfit(a[:, 0], a[:, ax], 1), a[:, 0])
        sp = np.abs(np.fft.rfft(x * np.hanning(n)))
        k = np.argsort(sp)[-2:][::-1]
        s += f" {name}: std={x.std():.4f} peaks=" + ",".join(f"{fr[j]:.1f}Hz" for j in k)
    print(f"idx {i:3d} dt={dt:.3f}{s}")
