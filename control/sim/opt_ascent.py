"""Open-loop fuel-optimal ascent (direct shooting, piecewise-linear controls) for insight into the best profile."""
import sys, json
import numpy as np
from scipy.optimize import minimize
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from model import *

def simulate(x, P, K, sub=8, record=False):
    """x: (B, 2K+1): beta nodes (K), tau nodes (K), T. Returns final state (B,5) [+ trajectory]."""
    B = x.shape[0]
    beta = x[:, :K]; tau = np.clip(x[:, K:2 * K], 0.0, 1.0); T = np.maximum(x[:, 2 * K], 5.0)
    y = np.zeros((B, 5)); y[:, 0] = R0 + P.get("h0", 5.0); y[:, 4] = P["fuel0"]
    dt = (T / K / sub)[:, None]
    traj = []
    for k in range(K):
        for j in range(sub):
            y = rk4(y, beta[:, k], tau[:, k], P, dt)
            if record: traj.append(y.copy())
    return (y, traj) if record else y

def cost(x, P, K, rc_min, w=1.0):
    y = simulate(x, P, K)
    r, vr, vt, fuel = y[:, 0], y[:, 2], y[:, 3], y[:, 4]
    used = P["fuel0"] - fuel
    vc = np.sqrt(MU / np.maximum(r, 300.0))
    pen = 2.0 * (vr) ** 2 + 2.0 * (vt - vc) ** 2 + 0.05 * np.maximum(0.0, rc_min - r) ** 2
    c = used + w * pen
    return np.where(np.isfinite(c), c, 1e9)

def solve(P, K=30, rc_min=1180.0, T0=45.0, seed=0, iters=600):
    rng = np.random.default_rng(seed)
    x0 = np.concatenate([np.clip(np.linspace(-0.6, 1.5, K), 0, 1.5), np.concatenate([np.full(K // 3, 0.55), np.full(K - K // 3, 0.25)]), [T0]])
    best = None
    for w in (0.01, 0.1, 1.0, 10.0):
        def f(x):
            return float(cost(x[None, :], P, K, rc_min, w)[0])
        def g(x):
            eps = 1e-4
            X = np.repeat(x[None, :], len(x) + 1, axis=0)
            for i in range(len(x)):
                X[i + 1, i] += eps * (10.0 if i == 2 * K else 1.0)
            c = cost(X, P, K, rc_min, w)
            gr = (c[1:] - c[0]) / eps
            gr[2 * K] /= 10.0
            return gr
        bounds = [(-0.3, 2.2)] * K + [(0.0, 1.0)] * K + [(15.0, 300.0)]
        res = minimize(f, x0, jac=g, method="L-BFGS-B", bounds=bounds, options={"maxiter": iters})
        x0 = res.x
    return x0

if __name__ == "__main__":
    m_dry = float(sys.argv[1]); N = int(sys.argv[2]); rc = float(sys.argv[3]); fuel0 = float(sys.argv[4]) if len(sys.argv) > 4 else 100.0
    P = dict(m_dry=m_dry, rho=(float(sys.argv[5]) if len(sys.argv) > 5 else 0.035), N=N, fuel0=fuel0)
    K = 30
    x = solve(P, K, rc)
    y, traj = simulate(x[None, :], P, K, record=True)
    r, th, vr, vt, fuel = y[0]
    print(f"m_dry={m_dry} N={N} rc_min={rc}: T={x[2*K]:.1f}s fuel_used={fuel0-fuel:.2f} r={r:.1f} vr={vr:.2f} vt={vt:.2f} vc={np.sqrt(MU/r):.2f} th={np.degrees(th):.1f}deg")
    T = x[2 * K]
    for k in range(K):
        s = traj[(k + 1) * 8 - 1][0]
        print(f" t={T*(k+1)/K:6.1f} beta={np.degrees(x[k]):6.1f} tau={np.clip(x[K+k],0,1):.2f} alt={s[0]-600:7.1f} vr={s[2]:6.1f} vt={s[3]:6.1f} fuel={s[4]:6.1f}")
