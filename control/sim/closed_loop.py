"""Closed-loop offline simulation of the flight guidance (fsw/guidance.py) against the fitted point-mass model."""
import math, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fsw.guidance import *


def sim_ascent(P, G, dt=0.02, ctrl_dt=0.04, delay=0.06, rate=math.radians(40.0), verbose=False, t_end=400.0):
    """P: vehicle (m_dry, rho, fuel0, N). G: guidance params. Returns dict with result."""
    g = AscentGuidance(G)
    r, th, vr, vt, fuel = R0 + 4.4, 0.0, 0.0, 0.0, P["fuel0"]
    beta = 0.0            # actual thrust direction
    cmd = (0.0, 0.0)      # (beta_cmd, throttle) in effect
    pend = []             # delayed commands
    t, t_next = 0.0, 0.0
    stage = "CLIMB"
    log = []
    while t < t_end:
        m = P["m_dry"] + P["rho"] * fuel
        acc_max = P["N"] * F2 / m
        if t >= t_next - 1e-9:
            b, thr, stage = g.step(t, r, vr, vt, acc_max)
            pend.append((t + delay, b, thr))
            t_next += ctrl_dt
            if verbose and (len(log) % 25 == 0):
                rp, ra, ecc = apsides(r, vr, vt)
                print(f"t={t:6.2f} {stage:6s} alt={r-R0:7.1f} vr={vr:6.1f} vt={vt:6.1f} beta={math.degrees(beta):5.1f} thr={cmd[1]:.2f} fuel={fuel:6.2f} ra={ra:8.1f} rp={rp:7.1f}")
            log.append((t, stage, r, vr, vt, beta, cmd[1], fuel))
            if stage == "ORBIT":
                break
        while pend and pend[0][0] <= t:
            cmd = (pend[0][1], pend[0][2]); pend.pop(0)
        # attitude follows command with a rate limit
        err = cmd[0] - beta
        step = max(-rate * dt, min(rate * dt, err))
        beta += step
        thr = cmd[1] if (abs(cmd[0] - beta) < math.radians(25.0) and fuel > 0) else 0.0
        vax = vr * math.cos(beta) + vt * math.sin(beta)
        aT = thr * acc_max * phi(vax)
        k = dragk(r)
        ar = vt * vt / r - grav(r) + aT * math.cos(beta) - k * vr
        at = -vr * vt / r + aT * math.sin(beta) - k * vt
        r += vr * dt + 0.5 * ar * dt * dt
        th += vt / r * dt
        vr += ar * dt
        vt += at * dt
        fuel -= thr * P["N"] * 2.0 * dt
        t += dt
        if r < R0:
            break
    rp, ra, ecc = apsides(r, vr, vt)
    return dict(ok=(stage == "ORBIT"), t=t, fuel_used=P["fuel0"] - fuel, r=r, vr=vr, vt=vt, rp=rp, ra=ra, th=th, log=log)


DEFAULT_G = dict(h1=40.0, h2=420.0, beta_max=50.0, v_ax=50.0, v_hyst=1.5, ra1=1180.0, ra_target=1300.0, rc_target=1240.0,
                 circ_kr=0.0, circ_tgo=0.3, rp_ok=1225.0, rp_min=1180.0, dv_fine=4.0, circ_lead=0.1, vt_boost_max=68.0)

if __name__ == "__main__":
    P = dict(m_dry=float(sys.argv[1]), rho=float(sys.argv[4]) if len(sys.argv) > 4 else 0.035, fuel0=float(sys.argv[5]) if len(sys.argv) > 5 else 104.0, N=int(sys.argv[2]))
    G = dict(DEFAULT_G)
    if len(sys.argv) > 3:
        G.update(json.loads(sys.argv[3]))
    res = sim_ascent(P, G, verbose=True)
    print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in res.items() if k != "log"})
