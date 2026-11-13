"""Mass-measurement mission: climb, coast, constant-thrust descent while firing decouplers one by one, then land."""
import os
import numpy as np

from .mathx import clip


def run(fl):
    c = fl.cfg
    f0 = float(os.environ.get("RIG_F0", "0.25"))
    plateau = float(os.environ.get("RIG_PLATEAU", "0.7"))
    phase, t_ph = "PRE", 0.0
    decs = sorted(fl.veh.decouplers, key=lambda b: b.index)
    k = 0
    fire_until = -1.0
    for s in fl.frames():
        if phase == "PRE":
            fl.actuate(s, s.n, 0.0, phase=phase)
            if s.t > 1.0:
                phase, t_ph = "CLIMB", s.t
                fl.event(s, f"liftoff integ={s.integrity}")
        elif phase == "CLIMB":
            a = s.g + s.k * s.vr + c["vz_kp"] * (55.0 - s.vr)
            fl.actuate(s, s.n, clip(a, 0.0, 90.0), phase=phase)
            if s.h > 260:
                phase, t_ph = "COAST", s.t
                fl.event(s, "coast")
        elif phase == "COAST":
            dt = s.t - t_ph
            if os.environ.get("RIG_RCS", "0") == "1" and 0.5 <= dt < 4.0:
                key = "LeftKey" if dt < 2.0 else ("RightKey" if dt >= 2.5 else None)
                keys = [(b.guid, key) for b in fl.veh.rcs] if key else ()
                fl.actuate(s, s.n, 0.0, keys=keys, phase="RCS_" + str(key))
            else:
                fl.actuate(s, s.n, 0.0, phase=phase)
            if s.vr < -30.0:
                phase, t_ph = "MEAS", s.t
                fl.event(s, "measure start")
        elif phase == "MEAS":
            dt = s.t - t_ph
            keys = []
            if k < len(decs) and dt >= plateau * (k + 1):
                fire_until = s.t + 0.25
                fl.event(s, f"fire decoupler {k} (bsg idx {decs[k].index}) integ={s.integrity}")
                k += 1
            if s.t < fire_until:
                keys.append((decs[k - 1].guid, "ExplodeKey"))
            wheel = fl.att.update(s.q, s.w, s.n, lead=c.get("att_lead", 0.06))
            thr = {b.guid: f0 for b in fl.veh.boosters}
            fl.veh.send(thr=thr, wheel=wheel, damper=0.0, keys=keys)
            fl.log.write(f"0,{s.t:.3f},MEAS,{s.alt:.2f},{s.h:.2f},{s.vr:.3f},{s.vt:.3f},{s.pad_dist:.2f},{s.fuel:.3f},{fl.att.err_deg:.2f},{f0:.3f},4,{s.integrity},{s.alive},0,0,{k},0,0\n")
            if dt >= plateau * (len(decs) + 1) + 0.2:
                phase, t_ph = "LAND", s.t
                fl.payload_attached = False
                fl.att.set_gains(c["wheel_gain_empty"])
                fl.event(s, f"land integ={s.integrity}")
        elif phase == "LAND":
            d, acc, info = fl.landing_cmd(s)
            if s.h < 0.25 and abs(s.vr) < 3.0:
                phase, t_ph = "DOWN", s.t
                fl.event(s, f"touchdown vr={s.vr:.2f} vt={s.vt:.2f} pad={s.pad_dist:.2f}")
                fl.veh.send()
                continue
            fl.actuate(s, d, acc, extra=info, phase=phase)
        elif phase == "DOWN":
            fl.veh.send()
            if s.t - t_ph > 4:
                fl.event(s, f"done integ={s.integrity} pad={s.pad_dist:.2f} h={s.h:.2f}")
                break
        if s.t > 120:
            fl.event(s, "timeout")
            break
