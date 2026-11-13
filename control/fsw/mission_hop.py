"""Test mission: climb, hover with attitude steps, return to pad and land."""
import math
import os
import numpy as np

from .mathx import clip, unit


def run(fl):
    c = fl.cfg
    hover_h = float(os.environ.get("HOP_ALT", "170"))
    phase = "PRE"
    t_ph = 0.0
    rest_t = None
    X = np.array([1.0, 0.0, 0.0]); Z = np.array([0.0, 0.0, 1.0])
    for s in fl.frames():
        if phase == "PRE":
            fl.actuate(s, s.n, 0.0, phase=phase)
            if s.t > 1.0:
                fl.nav.alt0 = s.alt
                phase, t_ph = "CLIMB", s.t
                fl.event(s, "liftoff")
        elif phase == "CLIMB":
            a = s.g + s.k * s.vr + c["vz_kp"] * (float(os.environ.get("HOP_VCLIMB", "30")) - s.vr)
            fl.actuate(s, s.n, clip(a, 0.0, min(60.0, 0.95 * fl.max_acc(s))), phase=phase)
            if s.h > hover_h - 20:
                phase, t_ph = "HOVER", s.t
                fl.event(s, "hover")
        elif phase == "HOVER":
            dt = s.t - t_ph
            d, acc, info = fl.landing_cmd(s, hold_alt=hover_h)
            tilt = math.radians(float(os.environ.get("HOP_TILT", "15")))
            if 4 <= dt < 7:
                d = unit(math.cos(tilt) * s.n + math.sin(tilt) * X)
            elif 10 <= dt < 13:
                d = unit(math.cos(tilt) * s.n + math.sin(tilt) * Z)
            elif dt < 16:
                d = s.n
            fl.actuate(s, d, acc, extra=info, phase=phase)
            if dt > float(os.environ.get('HOP_HOVER', '16')):
                phase, t_ph = "LAND", s.t
                fl.event(s, f"descend, pad_dist={s.pad_dist:.1f}")
        elif phase == "LAND":
            if fl.land_step(s):
                phase, t_ph = "DOWN", s.t
                fl.event(s, f"touchdown vr={s.vr:.2f} vt={s.vt:.2f} pad={s.pad_dist:.2f}")
        elif phase == "DOWN":
            if s.t - t_ph > float(os.environ.get("HOP_RELEASE", "1e9")):
                if not getattr(fl.veh, "rcs_release", False):
                    fl.event(s, f"all keys released integ={s.integrity} pad={s.pad_dist:.2f}")
                fl.veh.rcs_release = True
            fl.veh.send()
            if int(s.t * 25) % 50 == 0:
                fl.event(s, f"down integ={s.integrity} pad={s.pad_dist:.2f} h={s.h:.2f} w={float(np.linalg.norm(s.w)):.3f}")
            if s.t - t_ph > float(os.environ.get("HOP_DOWN", "12")):
                fl.event(s, f"done integ={s.integrity} pad={s.pad_dist:.2f} h={s.h:.2f}")
                break
        if s.t > 150:
            fl.event(s, "timeout")
            break
