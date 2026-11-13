"""Telemetry loading helpers (analysis only)."""
import csv, math
from collections import defaultdict
import numpy as np

C = np.array([0.0, -600.0, 0.0])
MU = 8456800.0

def load(path):
    """Return dict guid -> dict of numpy arrays (t, pos(3), vel(3), q(4), av(3), fuel, integ, alive)."""
    rows = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as fh:
        rd = csv.reader(fh)
        hdr = next(rd)
        ix = {h: i for i, h in enumerate(hdr)}
        def f(r, k):
            v = r[ix[k]]
            return float(v) if v != "" else float("nan")
        for r in rd:
            rows[r[ix["block_guid"]]].append((
                f(r, "simulation_time"), f(r, "x"), f(r, "y"), f(r, "z"),
                f(r, "vx"), f(r, "vy"), f(r, "vz"),
                f(r, "qx"), f(r, "qy"), f(r, "qz"), f(r, "qw"),
                f(r, "avx"), f(r, "avy"), f(r, "avz"),
                f(r, "fuel"), f(r, "health"), f(r, "machine_integrity"), f(r, "alive_block_count")))
    out = {}
    for g, lst in rows.items():
        a = np.array(lst)
        out[g] = dict(t=a[:, 0], pos=a[:, 1:4], vel=a[:, 4:7], q=a[:, 7:11], av=a[:, 11:14],
                      fuel=a[:, 14], health=a[:, 15], integ=a[:, 16], alive=a[:, 17])
    return out

def radial(d):
    rel = d["pos"] - C
    r = np.linalg.norm(rel, axis=1)
    n = rel / r[:, None]
    vr = np.sum(d["vel"] * n, axis=1)
    vt = np.linalg.norm(d["vel"] - vr[:, None] * n, axis=1)
    return r, vr, vt
