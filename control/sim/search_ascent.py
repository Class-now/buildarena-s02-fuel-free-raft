"""Random + coordinate search of the closed-loop ascent parameters against the offline model."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from sim.closed_loop import sim_ascent, DEFAULT_G

def evalG(P, G):
    if G["h2"] < G["h1"] + 20 or G["ra_target"] < G["ra1"] + 5 or G["ra1"] < 1000 or G["ra_target"] < G["rc_target"] + 10:
        return 1e3
    res = sim_ascent(P, G, dt=0.04)
    if not res["ok"] or res["rp"] < G["rp_min"] + 20:
        return 1e3
    return res["fuel_used"]

def main():
    P = dict(m_dry=float(sys.argv[1]), rho=float(sys.argv[3]), fuel0=float(sys.argv[4]), N=int(sys.argv[2]))
    base = dict(DEFAULT_G)
    if len(sys.argv) > 5:
        base.update(json.loads(sys.argv[5]))
    n = int(sys.argv[6]) if len(sys.argv) > 6 else 300
    rng = np.random.default_rng(1)
    rngs = dict(h1=(20, 150), h2=(250, 520), beta_max=(30, 80), ra1=(1050, 1260), ra_target=(1260, 1500), v_ax=(38, 62), vt_boost_max=(45, 75))
    best, bestG = evalG(P, base), dict(base)
    print("base", round(best, 2))
    for i in range(n):
        G = dict(base)
        for k, (lo, hi) in rngs.items():
            G[k] = float(rng.uniform(lo, hi))
        f = evalG(P, G)
        if f < best:
            best, bestG = f, G
    # coordinate refinement
    for rnd in range(3):
        for k, (lo, hi) in rngs.items():
            for d in (-0.08, -0.03, 0.03, 0.08):
                G = dict(bestG); G[k] = float(np.clip(G[k] + d * (hi - lo), lo, hi))
                f = evalG(P, G)
                if f < best - 0.01:
                    best, bestG = f, G
    res = sim_ascent(P, bestG, dt=0.02)
    print("best", round(best, 2), "check(dt=.02)", round(res["fuel_used"], 2), "rp", round(res["rp"], 1), "ra", round(res["ra"], 1), "t", round(res["t"], 1))
    print(json.dumps({k: round(bestG[k], 1) for k in rngs}))

if __name__ == "__main__":
    main()
