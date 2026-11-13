"""Tune the closed-loop ascent guidance parameters against the offline model (Nelder-Mead)."""
import sys, json, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.optimize import minimize
from sim.closed_loop import sim_ascent, DEFAULT_G

def main():
    P = dict(m_dry=float(sys.argv[1]), rho=float(sys.argv[3]), fuel0=float(sys.argv[4]), N=int(sys.argv[2]))
    base = dict(DEFAULT_G)
    if len(sys.argv) > 5:
        base.update(json.loads(sys.argv[5]))
    keys = ["h1", "h2", "beta_max", "ra1", "ra_target", "v_ax"]
    x0 = np.array([base.get("h1", 40.0), base.get("h2", 420.0), base.get("beta_max", 50.0), base.get("ra1", 1180.0), base.get("ra_target", 1300.0), base.get("v_ax", 50.0)])
    scale = np.array([30.0, 60.0, 8.0, 40.0, 40.0, 5.0])
    def f(z):
        G = dict(base)
        x = x0 + z * scale
        for k, v in zip(keys, x):
            G[k] = float(v)
        if G["h2"] < G["h1"] + 20 or G["ra_target"] < G["ra1"] or G["ra1"] < 1050 or G["v_ax"] < 25 or G["beta_max"] < 5 or G["beta_max"] > 85:
            return 1e3
        res = sim_ascent(P, G, dt=0.04)
        if not res["ok"]:
            return 1e3
        pen = 0.0
        if res["rp"] < base["rp_min"]:
            pen += (base["rp_min"] - res["rp"])
        return res["fuel_used"] + pen
    best = None
    for start in (np.zeros(6), np.array([0, 0, 1.0, -1.0, 1.0, 0]), np.array([0, -1.0, 0, -1.5, 2.0, -0.5]), np.array([0, 0, -1.0, 1.0, 0.5, 0.5])):
        r = minimize(f, start, method="Nelder-Mead", options={"maxiter": 400, "xatol": 0.02, "fatol": 0.01})
        if best is None or r.fun < best.fun:
            best = r
    x = x0 + best.x * scale
    G = dict(base)
    for k, v in zip(keys, x):
        G[k] = round(float(v), 1)
    res = sim_ascent(P, G, dt=0.02)
    print("best fuel", round(best.fun, 2), "check", round(res["fuel_used"], 2), "rp", round(res["rp"], 1), "ra", round(res["ra"], 1), "t", round(res["t"], 1))
    print(json.dumps({k: G[k] for k in keys}))

if __name__ == "__main__":
    main()
