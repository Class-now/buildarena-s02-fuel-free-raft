"""Full S02 mission: ascent -> circular orbit -> payload release -> stop above the pad -> drop -> landing -> wait
until the payload has completed the required revolutions."""
import math
import numpy as np

from .guidance import AscentGuidance, apsides, vcirc, F2
from .mathx import PLANET_C, clip, norm, unit, qrot


def run(fl):
    c = fl.cfg
    g = AscentGuidance(c["ascent"])
    phase, t_ph = "PRE", 0.0
    X = np.array(c.get("azimuth", [1.0, 0.0, 0.0]))
    hn = None            # fixed orbit-plane normal
    payload = None
    rev = dict(angle=0.0, prev=None, rmin=1e9, t_sep=None)
    n_asc = c.get("n_ascent", 2)
    fire_until = -1.0
    t_land = None
    d_retro = None
    token_done, token_ticks = False, 0
    stall_t, aborted = None, False
    cruise_aligned = False
    h_cruise = 500.0

    def plane(s):
        t_hat = unit(np.cross(hn, s.n))
        return t_hat, float(np.dot(s.vel, t_hat)), float(np.dot(s.vel, hn))

    for s in fl.frames():
        if hn is None:
            hn = unit(np.cross(s.n, X))
            payload = [b for b in fl.veh.blocks if b.guid in set(c.get("payload_guids", []))]
            if not payload:
                # default: every block above the decoupler along +Y of the machine frame, plus the decoupler
                dec = fl.veh.decouplers[0]
                payload = [b for b in fl.veh.blocks if b.pos[1] >= dec.pos[1] - 0.01 and abs(b.pos[0]) < 3 and abs(b.pos[2]) < 3]
            fl.event(s, f"payload blocks: {[b.index for b in payload]}; integ={s.integrity}")
        t_hat, vt, vc_cross = plane(s)

        # ---- payload orbit bookkeeping (after separation) ----
        if rev["t_sep"] is not None:
            pts = [np.array(s.recs[b.guid]["position"], dtype=float) - PLANET_C for b in payload if b.guid in s.recs]
            if pts:
                cen = sum(pts) / len(pts)
                ang = math.atan2(float(np.dot(cen, t_hat0)), float(np.dot(cen, n0)))
                if rev["prev"] is not None:
                    d = (ang - rev["prev"] + math.pi) % (2 * math.pi) - math.pi
                    rev["angle"] += d
                rev["prev"] = ang
                rev["rmin"] = min(rev["rmin"], min(norm(p) for p in pts))
                rev["r"] = norm(cen)

        if phase == "PRE":
            fl.actuate(s, s.n, 0.0, phase=phase)
            if s.t > 1.0:
                if s.integrity is not None and s.integrity < 0.999:
                    fl.event(s, f"ABORT: machine not intact at start (integrity={s.integrity})")
                    break
                fl.nav.alt0 = s.alt            # resting height after the machine has settled on its legs
                phase, t_ph = "ASCENT", s.t
                fl.event(s, "liftoff")
        elif phase == "ASCENT":
            rcs_mode = c.get("propulsion", "booster") == "rcs"
            acc_max = fl.max_acc(s) if rcs_mode else n_asc * F2 / fl.mass(s)
            beta, thr, stage = g.step(s.t, s.r, s.vr, vt, acc_max)
            # stall guard: the thrusters alone cannot lift the loaded vehicle between the fan ceiling and ~250 altitude;
            # if the climb stops there, give up cleanly and land instead of hovering until the timeout
            if stage == "CLIMB" and s.t - t_ph > 8.0 and s.alt < c.get("stall_alt", 320.0) and s.vr < c.get("stall_vr", 2.0):
                stall_t = stall_t or s.t
                if s.t - stall_t > c.get("stall_time", 6.0):
                    fl.event(s, f"ABORT: climb stalled at alt={s.alt:.0f}; landing with the payload attached")
                    aborted = True
                    phase, t_ph = "DROP", s.t
                    continue
            else:
                stall_t = None
            if rcs_mode and not token_done and s.alt > c.get("token_alt", 30.0):
                # token burn of the single booster (keeps the expended fuel finite and non-zero)
                token_ticks += 1
                boo = fl.veh.boosters[0]
                fl.veh.send(thr={boo.guid: c.get("token_f", 0.05)}, wheel=fl.att.update(s.q, s.w, s.n, t=s.t),
                            rcs={b.guid: 1 for q in fl.veh.rcs_quads for b in q}, fan=fl.fan_last)
                if token_ticks >= c.get("token_ticks", 2):
                    token_done = True
                    fl.event(s, f"token booster burn done, fuel={s.fuel:.4f}")
                continue
            d = math.cos(beta) * s.n + math.sin(beta) * t_hat - clip(c.get("cross_k", 0.02) * vc_cross, -0.2, 0.2) * hn
            if rcs_mode:
                acc_cmd = thr * acc_max
            else:
                acc_cmd = (1e3 if thr >= 0.999 else thr * acc_max) if thr > 0 else 0.0
            fl.actuate(s, unit(d), acc_cmd, n_on=n_asc, extra=(math.degrees(beta), thr, vt), phase=stage)
            if stage == "ORBIT":
                rp, ra, ecc = apsides(s.r, s.vr, vt)
                fl.event(s, f"orbit insertion: rp={rp:.1f} ra={ra:.1f} cross_v={vc_cross:.2f}")
                phase, t_ph = "RELEASE", s.t
        elif phase == "RELEASE":
            dt = s.t - t_ph
            settled = fl.att.err_deg < c.get("release_err_deg", 8.0) and norm(s.w) < c.get("release_rate", 0.5)
            if rev["t_sep"] is None and ((dt > c.get("release_wait", 1.0) and settled) or dt > c.get("release_timeout", 8.0)):
                rp, ra, ecc = apsides(s.r, s.vr, vt)
                fl.event(s, f"payload release: rp={rp:.1f} ra={ra:.1f} err={fl.att.err_deg:.1f} integ={s.integrity}")
                rev["t_sep"] = s.t
                n0, t_hat0 = s.n.copy(), t_hat.copy()
                fire_until = s.t + 0.6
                fl.payload_attached = False
                fl.att.set_gains(c["wheel_gain_empty"])
                fl.att.rate_max = c.get("att_rate_max_empty", fl.att.rate_max)
                fl.att.kp = c.get("att_kp_empty", fl.att.kp)      # lighter vehicle: tighter pointing loop for the landing
            keys = [(d_.guid, "ExplodeKey") for d_ in fl.veh.decouplers] if s.t < fire_until else ()
            acc_back = 0.0
            if rev["t_sep"] is not None and s.t - rev["t_sep"] > c.get("backoff_delay", 0.8):
                # back away from the payload with the reverse nozzles (attitude still prograde) before turning:
                # the arms must not sweep through the slowly departing payload
                acc_back = -c.get("backoff_acc", 0.0)
            fl.actuate(s, t_hat, acc_back, keys=keys, phase=phase)
            if rev["t_sep"] is not None and s.t - rev["t_sep"] > c.get("post_release_wait", 4.0):
                root = np.array(s.p)
                sep = min(norm(np.array(s.recs[b.guid]["position"], dtype=float) - root) for b in payload if b.guid in s.recs)
                fl.event(s, f"separated: distance={sep:.1f} integ={s.integrity}")
                if c.get("propulsion", "booster") == "rcs" and c.get("direct_return", True):
                    # still in orbit: turn towards the fly-back attitude first (no free fall while turning),
                    # the fly-back law then brakes and holds the altitude in one closed loop
                    h_cruise = clip(s.h + c.get("cruise_dh", 0.0), c.get("cruise_hmin", 480.0), c.get("cruise_hmax", 900.0))
                    fl.event(s, f"fly back from orbit at h={h_cruise:.0f}, pad_dist={s.pad_dist:.1f}")
                    phase, t_ph = "RETURN", s.t
                elif c.get("propulsion", "booster") == "rcs":
                    phase, t_ph = "BRAKE", s.t
                else:
                    phase, t_ph = "PHASING", s.t
        elif phase == "BRAKE":
            # fuel-free launcher: kill the orbital speed right away with the reverse nozzles (attitude stays prograde)
            a_max = fl.max_acc(s)
            acc = -min(a_max, max(2.0, c.get("brake_gain", 1.0) * vt))
            fl.actuate(s, t_hat, acc if vt > 0.5 else 0.0, extra=(vt, acc, 0), phase=phase)
            if vt < c.get("brake_vtol", 4.0) or s.t - t_ph > 60.0:
                h_cruise = clip(s.h + c.get("cruise_dh", 0.0), c.get("cruise_hmin", 480.0), c.get("cruise_hmax", 900.0))
                fl.event(s, f"brake done: vt={vt:.1f} vr={s.vr:.1f} pad_dist={s.pad_dist:.1f}; fly back at h={h_cruise:.0f}")
                phase, t_ph = "RETURN", s.t
        elif phase == "RETURN":
            # powered fly-back above the atmosphere towards the pad, then descend
            over = dict(c.get("cruise", {}))
            if not cruise_aligned and s.t - t_ph > 1.0 and fl.att.err_deg < c.get("cruise_align_deg", 15.0):
                # first turn done (engines were inhibited meanwhile): from now on the commanded axis is slew-limited so
                # that the engines stay on during the later tilt reversals of the fly-back (no free fall while turning)
                cruise_aligned = True
                fl._d_cmd = None
            if not cruise_aligned:
                over.pop("cruise_slew_deg", None)
            d, acc, info = fl.landing_cmd(s, hold_alt=h_cruise, over=over)
            fl.actuate(s, d, acc, extra=info, phase=phase)
            if (s.pad_dist < c.get("cruise_exit_dist", 40.0) and s.vt < c.get("cruise_exit_v", 15.0)) or s.t - t_ph > 400.0:
                fl.event(s, f"over the pad: pad_dist={s.pad_dist:.1f} vt={s.vt:.1f} h={s.h:.0f}; descending")
                phase, t_ph = "DROP", s.t
        elif phase == "PHASING":
            # point retrograde and wait until the constant-deceleration stop distance equals the distance to the pad
            vh_dir = unit(s.vh)
            fl.actuate(s, -vh_dir, 0.0, phase=phase)
            ohat = unit(np.cross(s.p - PLANET_C, s.vel))
            delta = math.atan2(float(np.dot(np.cross(s.n, fl.nav.n_pad), ohat)), float(np.dot(s.n, fl.nav.n_pad)))
            a_max = fl.max_acc(s)
            a_plan = c.get("deorbit_frac", 0.6) * a_max
            d_stop = s.vt * s.vt / (2.0 * a_plan) + s.vt * c.get("deorbit_latency", 0.08)
            if s.t - t_ph > 3.0 and 0.0 < delta * s.r <= d_stop and fl.att.err_deg < 5.0:
                fl.event(s, f"deorbit burn start: dist={delta*s.r:.1f} units, stop dist={d_stop:.1f}")
                phase, t_ph = "DEORBIT", s.t
        elif phase == "DEORBIT":
            # closed-loop stop above the pad: decelerate at v^2 / (2 d) along the direction captured at burn start
            if d_retro is None:
                d_retro = -unit(s.vh)
                o_retro = unit(np.cross(s.p - PLANET_C, s.vel))
            d_r = unit(d_retro - float(np.dot(d_retro, s.n)) * s.n)
            v_along = -float(np.dot(s.vel, d_r))
            delta = math.atan2(float(np.dot(np.cross(s.n, fl.nav.n_pad), o_retro)), float(np.dot(s.n, fl.nav.n_pad)))
            dist = delta * s.r
            a_max = fl.max_acc(s)
            if dist > 0.3:
                acc = v_along * v_along / (2.0 * dist)
            else:
                acc = a_max
            acc = min(a_max, max(c.get("deorbit_amin", 1.5), acc))
            fl.actuate(s, d_r, acc if v_along > 0.0 else 0.0, extra=(v_along, acc, dist), phase=phase)
            if v_along < c.get("deorbit_vtol", 0.25) or s.t - t_ph > 30.0:
                fl.event(s, f"deorbit done: v_along={v_along:.2f} dist={dist:.2f} pad_dist={s.pad_dist:.1f} r={s.r:.1f} fuel={s.fuel:.2f}")
                phase, t_ph = "DROP", s.t
        elif phase == "DROP":
            # free fall; landing guidance decides when to brake
            if fl.land_step(s, phase="DROP"):
                fl.event(s, f"touchdown vr={s.vr:.2f} vt={s.vt:.2f} pad={s.pad_dist:.2f} integ={s.integrity}")
                phase, t_ph = "LANDED", s.t
                t_land = s.t
        elif phase == "LANDED":
            if c.get("landed_release", False) and s.t - t_land > c.get("landed_release_wait", 3.0):
                fl.veh.rcs_release = True      # everything off: the vehicle rests on the ground with no thrust at all
            fl.veh.send()
            revs = abs(rev["angle"]) / (2 * math.pi)
            if aborted and s.t - t_land > 8.0:
                fl.event(s, f"ABORTED MISSION: landed pad={s.pad_dist:.2f} integ={s.integrity}")
                break
            if int(s.t * 25) % 500 == 0:
                fl.event(s, f"waiting: payload revs={revs:.3f} r={rev.get('r', 0):.1f} rmin={rev['rmin']:.1f} pad={s.pad_dist:.2f} integ={s.integrity}")
            if revs >= c.get("revs_required", 3.08) and s.t - t_land > 15.0:
                fl.event(s, f"MISSION COMPLETE: payload revs={revs:.3f} rmin={rev['rmin']:.1f} pad={s.pad_dist:.2f} integ={s.integrity} fuel={s.fuel:.4f}")
                break
        if s.t > c.get("t_max", 1500.0):
            fl.event(s, "timeout")
            break
    fl.result = dict(phase=phase, revs=abs(rev["angle"]) / (2 * math.pi), rmin=rev["rmin"])
