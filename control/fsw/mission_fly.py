"""Flying Block probe: hold FlyKey with attitude hold, log; release at top altitude."""
import os


def run(fl):
    veh = fl.veh
    fb = [b for b in veh.blocks if b.type_id == 14]
    print("sliders:", [(s.name, s.minimum, s.maximum, s.default) for s in fl.client.sliders if s.block_guid.lower() in {b.guid for b in fb}], flush=True)
    print("channels:", [(c.name) for c in fl.client.channels if c.block_guid.lower() in {b.guid for b in fb}], flush=True)
    top = float(os.environ.get("FLY_TOP", "600"))
    spd = float(os.environ.get("FLY_SPEED", "1.0"))
    tmax = float(os.environ.get("FLY_TMAX", "40"))
    phase, t_ph = "PRE", 0.0
    for s in fl.frames():
        wheel = fl.att.update(s.q, s.w, s.n, t=s.t)
        keys = []
        if phase == "PRE":
            if s.t > 1.0:
                phase, t_ph = "FLY", s.t
        elif phase == "FLY":
            keys = [(b.guid, "FlyKey") for b in fb]
            if s.alt > top or s.t - t_ph > tmax:
                fl.event(s, "release")
                phase, t_ph = "COAST", s.t
        elif phase == "COAST":
            if s.t - t_ph > 5.0:
                fl.event(s, "end")
                break
        veh.send(wheel=wheel, keys=keys, sliders=[(b.guid, 'speed', spd) for b in fb])
        fl.log.write(f"0,{s.t:.3f},{phase},{s.alt:.2f},{s.h:.2f},{s.vr:.3f},{s.vt:.3f},{s.pad_dist:.2f},0,{fl.att.err_deg:.2f},0,0,{s.integrity},{s.alive},0,0,0,0,0\n")
