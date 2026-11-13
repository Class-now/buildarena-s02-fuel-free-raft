"""RCS probe test: find the key->direction mapping, climb on thrusters only, then reverse thrust."""
import os
import numpy as np


def run(fl):
    veh = fl.veh
    up_sign = {b.guid: (1 if veh.rcs_axis[b.guid][1] > 0 else -1) for b in veh.rcs}   # +1: local +Y points to body up
    mapping = 1          # hypothesis: RightKey (+1) thrusts the vehicle along local +Y
    phase, t_ph = "PRE", 0.0
    top = float(os.environ.get("RCS_TOP", "700"))
    h_try = None

    def cmd(direction):
        """direction +1: push vehicle towards body up; -1: towards body down."""
        return {g: direction for g in up_sign}

    for s in fl.frames():
        wheel = fl.att.update(s.q, s.w, s.n, t=s.t)
        rc = {}
        if phase == "PRE":
            if s.t > 1.0:
                phase, t_ph, h_try = "TRY", s.t, s.h
        elif phase == "TRY":
            rc = cmd(+1)
            if s.t - t_ph > 1.5:
                if s.h - h_try < 0.3:
                    mapping = -1
                fl.event(s, f"mapping={mapping} (rose {s.h - h_try:.2f})")
                phase, t_ph = "CLIMB", s.t
        elif phase == "CLIMB":
            rc = cmd(+1)
            if s.alt > top:
                fl.event(s, "reverse thrust")
                phase, t_ph = "REV", s.t
        elif phase == "REV":
            rc = cmd(-1)
            if s.t - t_ph > 6.0:
                fl.event(s, "coast")
                phase, t_ph = "COAST", s.t
        elif phase == "COAST":
            if s.t - t_ph > 4.0 or s.alt < 30:
                fl.event(s, "end")
                break
        veh.send(wheel=wheel, rcs=rc)
        fl.log.write(f"0,{s.t:.3f},{phase},{s.alt:.2f},{s.h:.2f},{s.vr:.3f},{s.vt:.3f},{s.pad_dist:.2f},0,{fl.att.err_deg:.2f},0,0,{s.integrity},{s.alive},0,0,0,0,0\n")
        if s.t > 200:
            break
