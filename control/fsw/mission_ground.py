"""Ground test: which idle command gives a quiet vehicle on the pad? (no flight)"""
import os
import numpy as np


def run(fl):
    veh = fl.veh
    seg = float(os.environ.get("GROUND_SEG", "8"))
    modes = os.environ.get("GROUND_MODES", "both,down,down_inner,alt,release,down").split(",")
    last = None
    for s in fl.frames():
        i = int(s.t // seg)
        if i >= len(modes):
            fl.event(s, f"done integ={s.integrity}")
            break
        mode = modes[i]
        if mode != last:
            fl.event(s, f"mode {mode} integ={s.integrity} pad={s.pad_dist:.2f} h={s.h:.2f}")
            last = mode
        veh.rcs_release = False
        rcs = {}
        if mode == "down":
            rcs = {b.guid: -1 for b in veh.rcs_lift}
        elif mode == "down_inner":
            rcs = {b.guid: -1 for q in veh.rcs_quads[-6:] for b in q}
        elif mode == "alt":
            for j, q in enumerate(veh.rcs_quads):
                for b in q:
                    rcs[b.guid] = 1 if j % 2 == 0 else -1
        elif mode == "release":
            veh.rcs_release = True
        if mode == "none":
            continue                      # send nothing at all: every command expires
        if mode == "rwdamp":
            veh.send(rcs=rcs, damper=1.0)
        elif mode == "attctl":
            fl.actuate(s, s.n, 0.0, phase=mode)
        elif mode == "attup":
            from .mathx import qrot
            fl.actuate(s, qrot(s.q, np.array([0.0, 1.0, 0.0])), 0.0, phase=mode)   # zero pointing error: pure rate damping
        else:
            veh.send(rcs=rcs)
