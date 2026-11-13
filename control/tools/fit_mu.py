"""Fit the gravitational parameter from a coasting object's telemetry (energy / angular momentum constancy)."""
import sys, glob, numpy as np
sys.path.insert(0, "agent_control/tools"); sys.path.insert(0, "agent_control")
from tele import *
from fsw.vehicle import parse_bsg
R = sys.argv[1]; idx = int(sys.argv[2]); t0 = float(sys.argv[3]); t1 = float(sys.argv[4])
bs = parse_bsg(glob.glob(R + "/*_prepared.bsg")[0])
d = load(R + "/telemetry.csv")[bs[idx].guid]
m = (d["t"] >= t0) & (d["t"] <= t1)
t = d["t"][m]; rel = d["pos"][m] - C; v = d["vel"][m]
r = np.linalg.norm(rel, axis=1); v2 = np.sum(v * v, axis=1)
h = np.linalg.norm(np.cross(rel, v), axis=1)
print("r range", r.min().round(1), r.max().round(1), "h std/mean", (h.std() / h.mean()).round(5))
# energy E = v2/2 - mu/r constant  =>  v2/2 = E + mu*(1/r): linear regression
A = np.stack([np.ones_like(r), 1.0 / r], axis=1)
coef, res, *_ = np.linalg.lstsq(A, 0.5 * v2, rcond=None)
print("fit mu =", coef[1].round(0), "E =", coef[0].round(1), "rms resid", np.sqrt(np.mean((A @ coef - 0.5 * v2) ** 2)).round(3))
for mu in (8456800.0, 7920000.0, coef[1]):
    E = 0.5 * v2 - mu / r
    print("mu", round(mu), "energy std", E.std().round(3))
