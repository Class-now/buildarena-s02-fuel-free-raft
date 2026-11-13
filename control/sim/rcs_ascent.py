"""Offline point-mass check of the fuel-free ascent with the real guidance class.
usage: uv run python sim/rcs_ascent.py <config.json> [m_total] [n_thrusters] [n_fans]"""
import json, math, sys
sys.path.insert(0, ".")
from fsw.guidance import AscentGuidance, apsides
MU, R0 = 8456800.0, 600.0
c = json.load(open(sys.argv[1]))
m = float(sys.argv[2]) if len(sys.argv) > 2 else c["m_dry_vehicle"] + c["m_payload"]
nth = int(sys.argv[3]) if len(sys.argv) > 3 else 60
nfan = int(sys.argv[4]) if len(sys.argv) > 4 else 8
g = AscentGuidance(c["ascent"])
r, th, vr, vt = R0 + 0.7, 0.0, 0.0, 0.0
beta_b = 0.0            # actual body pitch from vertical
dt, t = 0.02, 0.0
rate = float(c.get("sim_rate", 0.5))
last = None
while t < 400:
    alt = r - R0
    v_ax = vr * math.cos(beta_b) + vt * math.sin(beta_b)
    fan_scale = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
    # fan model fitted to the v3c/v3d hops: fades with altitude AND with axial speed
    F = nth * c.get("rcs_force", 8.3) + fan_scale * nfan * 127.75 * (c.get("rcs_force", 8.3) / 8.3) * max(0.0, 1.0 - alt / 195.0) * max(0.0, 1.0 - max(0.0, v_ax) / 70.0)
    acc_max = F / m
    beta, thr, stage = g.step(t, r, vr, vt, acc_max)
    if stage != last:
        rp, ra, e = apsides(r, vr, vt)
        print(f"t={t:6.1f} {stage:6s} alt={alt:6.1f} vr={vr:6.1f} vt={vt:6.1f} rp={rp:7.1f} ra={ra:7.1f} accmax={acc_max:.1f}")
        last = stage
    if stage == "ORBIT":
        break
    db = max(-rate * dt, min(rate * dt, beta - beta_b))
    beta_b += db
    a = thr * acc_max if abs(beta - beta_b) < math.radians(25) else 0.0
    k = 0.092 * max(0.0, 1.0 - alt / 450.0)
    grav = min(22.0, MU / r / r)
    ar = a * math.cos(beta_b) - grav + vt * vt / r - k * vr
    at = a * math.sin(beta_b) - vr * vt / r - k * vt
    vr += ar * dt; vt += at * dt; r += vr * dt; th += vt / r * dt; t += dt
    if r < R0:
        print("crashed", t); break
print(f"end t={t:.1f} alt={r-R0:.1f} vr={vr:.1f} vt={vt:.1f}")
