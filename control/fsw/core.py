"""Flight core: main loop plumbing, thrust allocation, powered-landing guidance, logging."""
import json
import math
import os
import time
from pathlib import Path

import numpy as np

from controller_sdk import ControllerClient

from .attitude import AttitudeController
from .mathx import clip, norm, unit
from .nav import Nav
from .vehicle import Vehicle, throttle_for_force, booster_force, F1


class Flight:
    def __init__(self, cfg):
        self.cfg = cfg
        self.client = ControllerClient.from_environment()
        self.run_dir = Path(os.environ.get("BUILDARENA_RUN_DIR", "."))
        self.log = None
        self.events = []

    # ------------------------------------------------------------------ setup
    def start(self):
        self.client.arm()
        ready = os.environ.get("BUILDARENA_CONTROLLER_READY")
        if ready:
            # prestart mode: tell the runner we are ready before physics starts
            from controller_sdk.protocol import atomic_write_json
            atomic_write_json(Path(ready), {"schema": "buildarena.controller_ready.v1",
                                            "run_id": os.environ["BUILDARENA_RUN_ID"]})
        first = self.client.wait_until_running(timeout=120)
        # in prestart mode the block table appears shortly after physics starts: wait for it
        t_dead = time.time() + 30.0
        while True:
            try:
                self.client.load_block_table()
                break
            except Exception:
                if time.time() > t_dead:
                    raise
                time.sleep(0.02)
        self.veh = Vehicle(self.client)
        self.veh.rcs_idle_both = bool(self.cfg.get("rcs_idle_both", False))
        self.nav = Nav(self.veh)
        self.att = AttitudeController(self.veh, self.cfg["wheel_gain_loaded"], kp=self.cfg.get("att_kp", 2.0), kd=self.cfg.get("att_kd", 4.0), ki=self.cfg.get("att_ki", 0.0))
        self.att.damp_ff = self.cfg.get("att_damp_ff", 0.0)
        self.att.damp_ratio = self.cfg.get("att_damp_ratio", 0.0)
        self.att.rate_max = self.cfg.get("att_rate_max", 0.7)
        self.log = open(self.run_dir / "fsw_log.csv", "w", buffering=1)
        self.log.write("wall,t,phase,alt,h,vr,vt,pad,fuel,err,f,n_on,integ,alive,ra,rp,ex1,ex2,ex3\n")
        self.payload_attached = True
        self.wall0 = time.time()
        self.f_last, self.n_last = 0.0, 0
        return first

    def event(self, s, msg):
        line = f"[t={s.t:7.2f} alt={s.alt:7.1f} vr={s.vr:6.1f} vt={s.vt:6.1f} fuel={s.fuel:6.1f}] {msg}"
        print(line, flush=True)
        self.events.append(line)

    def mass(self, s):
        m = self.cfg["m_dry_vehicle"] + self.cfg["fuel_density"] * s.fuel
        if self.payload_attached:
            m += self.cfg["m_payload"]
        return m

    # ------------------------------------------------------------------ actuation
    def actuate(self, s, d_world, acc, n_on=None, keys=(), extra=(0, 0, 0), phase=""):
        """Point the thrust axis along d_world and produce thrust acceleration `acc` (along the body axis).
        n_on: number of boosters to use (None = all). Engines are inhibited while the pointing error is large.
        With cfg["propulsion"] == "rcs" the thrust comes from the fuel-free thrusters / lift fans instead."""
        wheel = self.att.update(s.q, s.w, d_world, lead=self.cfg.get("att_lead", 0.06), t=s.t)
        thr, rcs, fan = {}, {}, 0.0
        f = 0.0
        ok = self.att.err_deg < self.cfg.get("max_fire_err_deg", 25.0)
        if self.cfg.get("propulsion", "booster") == "rcs":
            if ok and abs(acc) > 1e-6:
                rcs, fan, f = self.lift_allocate(s, acc)
            self.f_last, self.n_last = f, sum(1 for v in rcs.values() if v)
            if self.cfg.get("att_assist", False):
                loaded = self.payload_attached
                alt_min = self.cfg.get("assist_alt_min", 300.0) if loaded else self.cfg.get("assist_alt_min_empty", 0.0)
                if s.alt > alt_min and (loaded or not self.cfg.get("assist_loaded_only", True)):
                    plus, minus = self.assist_cmd(s)
                    if not rcs:
                        # lift engines idle: pure couple (opposite arms push in opposite directions)
                        for b in plus:
                            rcs[b.guid] = 1
                        for b in minus:
                            rcs[b.guid] = -1
                    elif acc > 0.0 and not loaded:
                        # empty vehicle with the engines on: differential thrust (one arm tip on, the opposite one off)
                        for b in plus:
                            rcs[b.guid] = 1
                        for b in minus:
                            rcs.pop(b.guid, None)
            rcs.update(self.roll_cmd(s))
        else:
            boosters = self.veh.boosters
            if n_on is not None:
                boosters = self.select_boosters(n_on)
            if acc > 0.0 and boosters and ok:
                v_ax = float(np.dot(s.vel, s.up))
                force = self.mass(s) * acc / len(boosters)
                f = throttle_for_force(force, v_ax)
                for b in boosters:
                    thr[b.guid] = f
            self.f_last, self.n_last = f, (len(boosters) if f > 0 else 0)
        self.fan_last = fan
        self.veh.send(thr=thr, wheel=wheel, damper=self.cfg.get("wheel_damper", 0.0), keys=keys, rcs=rcs, fan=fan)
        self.log.write(f"{time.time()-self.wall0:.2f},{s.t:.3f},{phase},{s.alt:.2f},{s.h:.2f},{s.vr:.3f},{s.vt:.3f},{s.pad_dist:.2f},{s.fuel:.3f},"
                       f"{self.att.err_deg:.2f},{f:.3f},{self.n_last},{s.integrity},{s.alive},{s.ra:.1f},{s.rp:.1f},"
                       f"{extra[0]:.3f},{extra[1]:.3f},{extra[2]:.3f}\n")

    def assist_cmd(self, s):
        """Attitude assist with the outer lift thrusters of two opposite arms (tau_x = -z F_y, tau_z = x F_y).
        Returns (thrusters that should push towards +Y, thrusters that should push towards -Y / be switched off).
        Bang-bang on the rate error of the pointing loop, with hysteresis; the reaction wheels do the fine work."""
        c = self.cfg
        loaded = self.payload_attached
        n = int(c.get("assist_n", 4) if loaded else c.get("assist_n_empty", c.get("assist_n", 4)))
        if not hasattr(self, "_assist_sets"):
            self._assist_sets = {}
            self._assist_state = [0, 0]
        if n not in self._assist_sets:
            lift, root = self.veh.rcs_lift, self.veh.root.pos

            def arm(axis, sign):
                other = 2 - axis
                cand = [b for b in lift if sign * (b.pos[axis] - root[axis]) > 1.5 and abs(b.pos[other] - root[other]) < 1.0]
                cand.sort(key=lambda b: -abs(b.pos[axis] - root[axis]))
                return cand[:n]
            # per axis: (thrusters whose +Y push gives positive torque, thrusters whose +Y push gives negative torque)
            self._assist_sets[n] = ((arm(2, -1), arm(2, +1)), (arm(0, +1), arm(0, -1)))
        sets = self._assist_sets[n]
        on = c.get("assist_on", 0.08) if loaded else c.get("assist_on_empty", c.get("assist_on", 0.08))
        off = c.get("assist_off", 0.04) if loaded else c.get("assist_off_empty", c.get("assist_off", 0.04))
        plus, minus = [], []
        for i in (0, 1):
            err = self.att.rate_err[i]
            st = self._assist_state[i]
            if abs(err) > on:
                st = 1 if err > 0 else -1
            elif abs(err) < off or (st != 0 and (err > 0) != (st > 0)):
                st = 0
            self._assist_state[i] = st
            if st > 0:
                plus += sets[i][0]; minus += sets[i][1]
            elif st < 0:
                plus += sets[i][1]; minus += sets[i][0]
        return plus, minus

    def roll_cmd(self, s):
        """Roll-rate damping with the tangential tip thrusters (bang-bang with a dead band)."""
        from .mathx import qinv_rot
        out = {}
        if not self.veh.rcs_tip:
            return out
        wy = float(qinv_rot(s.q, s.w)[1])
        db = self.cfg.get("roll_deadband", 0.04)
        if abs(wy) > db:
            sgn = -1.0 if wy > 0 else 1.0            # desired torque sign about body +Y
            for b, c, a in self.veh.rcs_tip:
                if abs(c) > 0.5:
                    out[b.guid] = 1 if sgn * c > 0 else -1
        return out

    def fan_lift(self, s, speed=1.0):
        """Rough model of one lift fan's force per unit slider (fades with altitude)."""
        c = self.cfg
        f = c.get("fan_force", 47.0) * speed * max(0.0, 1.0 - s.alt / c.get("fan_ceiling", 255.0))
        if "fan_vmax" in c:
            # measured: the fan force also fades with the speed along its axis
            v_ax = float(np.dot(s.vel, s.up))
            f *= max(0.2, 1.0 - max(0.0, v_ax) / c["fan_vmax"])
        return f

    def lift_allocate(self, s, acc):
        """Fuel-free thrust: acc (signed, along body +Y). RCS thrusters are switched in torque-free quads with
        sigma-delta dithering; the lift fans (continuous slider) supply what the thrusters cannot (low altitude)."""
        c = self.cfg
        veh = self.veh
        F = acc * self.mass(s)
        fr = c.get("rcs_force", 8.3)
        quads = veh.rcs_quads
        nq = len(quads)
        sign = 1 if F >= 0 else -1
        level = abs(F) / (4.0 * fr)                # quads needed
        fan = 0.0
        if level >= nq:
            k = nq
            if sign > 0 and veh.fans:
                extra = abs(F) - nq * 4.0 * fr
                per = len(veh.fans) * self.fan_lift(s, 1.0)
                fan = min(2.0, extra / per) if per > 1e-6 else 0.0
        else:
            k = int(level)
            self._sd = getattr(self, "_sd", 0.0) + (level - k)
            if self._sd >= 1.0:
                self._sd -= 1.0
                k += 1
        rcs = {}
        for q in quads[:k]:
            for b in q:
                rcs[b.guid] = sign
        return rcs, fan, level / max(1, nq)

    def select_boosters(self, n):
        """Symmetric subsets: pairs of opposite boosters (sorted by position)."""
        bs = self.veh.boosters
        if n >= len(bs):
            return bs
        pairs = []
        used = set()
        for a in bs:
            if a.guid in used:
                continue
            for b in bs:
                if b.guid in used or b is a:
                    continue
                if abs(a.pos[0] + b.pos[0]) < 0.05 and abs(a.pos[2] + b.pos[2]) < 0.05:
                    pairs.append((a, b))
                    used.update((a.guid, b.guid))
                    break
        out = []
        for a, b in pairs:
            if len(out) + 2 <= n:
                out += [a, b]
        return out

    def max_acc(self, s, n=None, v_ax=0.0):
        if self.cfg.get("propulsion", "booster") == "rcs":
            F = len(self.veh.rcs_lift) * self.cfg.get("rcs_force", 8.3) + len(self.veh.fans) * self.fan_lift(s, 2.0)
            return F / self.mass(s)
        n = len(self.veh.boosters) if n is None else n
        return n * booster_force(2.0, v_ax) / self.mass(s)

    # ------------------------------------------------------------------ landing guidance
    def landing_cmd(self, s, hold_alt=None, over=None):
        """Hover-translate to the pad and descend. Returns (direction, thrust_acc, info).
        over: optional dict of parameter overrides (used for the high-altitude fly-back)."""
        c = self.cfg if not over else {**self.cfg, **over}
        # lateral channel: velocity command towards the pad, limited
        vh_des = s.pad_dir * clip(c["lat_kp"] * s.pad_dist, 0.0, c["lat_vmax"])
        a_lat = c["lat_kd"] * (vh_des - s.vh) + s.k * s.vh
        al = norm(a_lat)
        if al > c["lat_amax"]:
            a_lat *= c["lat_amax"] / al
        dt = clip(s.t - getattr(self, "_land_t", s.t), 0.0, 0.2)
        self._land_t = s.t
        # integral action on the position error near the pad: cancels a constant lateral disturbance
        # (e.g. a small misalignment between the thrust axis and the root block axis)
        li = getattr(self, "lat_int", None)
        if li is None:
            li = np.zeros(3)
        if hold_alt is None and s.pad_dist < c.get("lat_int_dist", 12.0) and s.h < c.get("lat_int_h", 80.0):
            li = li + c.get("lat_ki", 0.0) * s.pad_dir * s.pad_dist * dt
            li = li - float(np.dot(li, s.n)) * s.n
            ln = norm(li)
            if ln > c.get("lat_int_max", 2.5):
                li *= c.get("lat_int_max", 2.5) / ln
        self.lat_int = li
        if hold_alt is None:
            a_lat = a_lat + li
        # vertical channel
        if hold_alt is not None:
            v_des = clip(c["alt_kp"] * (hold_alt - s.h), -c["v_desc_max"], 20.0)
            ff = 0.0
        else:
            h_eff = max(s.h - c["h_flare"], 0.0)
            v_prof = math.sqrt(2.0 * c["a_brake"] * h_eff + c["v_touch"] ** 2)
            if v_prof < c["v_desc_max"]:
                # feed-forward deceleration only in proportion to how fast we are actually sinking
                ratio = clip(-s.vr / v_prof, 0.0, 1.0)
                v_des, ff = -v_prof, (c["a_brake"] * ratio * ratio if h_eff > 0 else 0.0)
            else:
                v_des, ff = -c["v_desc_max"], 0.0
            # do not descend the last metres until we are over the pad
            tol, vt_lim = c["pad_tol"], c.get("commit_vt", 1.5)
            if s.h < c["h_gate"]:
                self._gate_t0 = getattr(self, "_gate_t0", None) or s.t
                if s.t - self._gate_t0 > c.get("gate_timeout", 40.0):
                    tol, vt_lim = c.get("pad_tol_late", 8.0), 5.0   # do not hover for ever: land close to the pad anyway
            # hysteresis: once the final descent has started it is only broken off if the offset becomes large
            if getattr(self, "_committed", False):
                if s.pad_dist > c.get("pad_tol_abort", 6.0):
                    self._committed = False
                else:
                    tol = max(tol, c.get("pad_tol_abort", 6.0))
            elif s.h < c["h_gate"] and s.pad_dist <= tol and s.vt < vt_lim:
                self._committed = True
            if s.h < c["h_gate"] and (s.pad_dist > tol or not getattr(self, "_committed", False)):
                v_des, ff = max(v_des, 0.3 * (c["h_gate"] * 0.6 - s.h)), 0.0
        # integral action near the ground: boosters get a ground-effect cushion (hover at ~0.7 with 80 % weight)
        if c.get("vz_int_always", False) or (hold_alt is None and s.h < c.get("h_int", 6.0)):
            self.vz_int = clip(getattr(self, "vz_int", 0.0) + c.get("vz_ki", 4.0) * (v_des - s.vr) * dt,
                               -15.0, c.get("vz_int_max", 5.0))
        else:
            self.vz_int = 0.0
        a_up = s.g - s.vt * s.vt / s.r + s.k * s.vr + c["vz_kp"] * (v_des - s.vr) + ff + self.vz_int
        a_up = max(a_up, c.get("a_up_min", 0.0))
        a_up = clip(a_up, 0.0, 0.9 * self.max_acc(s))
        A = a_up * s.n + a_lat
        if a_up < 1.0:
            # engines off (free fall / coasting up): stay vertical, ready for the braking burn
            return s.n, 0.0, (v_des, al, a_up)
        # tilt limit
        d = unit(A)
        tilt_max = math.radians(c["tilt_max_deg"])
        if hold_alt is None and a_up < c.get("tilt_aup_ref", 0.0):
            # little thrust (accelerating downwards at the start of the descent): a small lateral demand would ask for a
            # large tilt and flip it again a second later -> stay nearly vertical until the engines carry the weight
            tilt_max = math.radians(c.get("tilt_low_deg", 3.0))
        ct = float(np.dot(d, s.n))
        if ct < math.cos(tilt_max):
            lat = unit(d - ct * s.n)
            d = math.cos(tilt_max) * s.n + math.sin(tilt_max) * lat
        rate = c.get("cmd_slew_deg", 0.0) if hold_alt is None else c.get("cruise_slew_deg", 0.0)
        if rate > 0.0:
            # slew-rate limit of the commanded axis (landing only): the command starts from the present attitude and
            # never moves faster than the vehicle can follow, so the pointing error stays small and the engines stay on
            prev = getattr(self, "_d_cmd", None)
            if prev is None:
                prev = s.up
            ang = math.acos(clip(float(np.dot(prev, d)), -1.0, 1.0))
            max_ang = math.radians(rate) * max(dt, 0.02)
            if ang > max_ang:
                d = unit(prev + (d - prev) * (max_ang / ang))
            self._d_cmd = d
        cosu = max(0.3, float(np.dot(s.up, s.n)))
        acc = a_up / cosu
        return d, acc, (v_des, al, a_up)

    def land_step(self, s, phase="LAND"):
        """One tick of the terminal landing. Returns True once touchdown is detected (engines are cut)."""
        c = self.cfg
        if s.h < c.get("h_cut", 0.2) and abs(s.vr) < 3.0:
            self.veh.send()
            return True
        # second criterion (independent of the exact resting height): standing still close to the ground
        if s.h < c.get("h_still", 1.0) and abs(s.vr) < 0.2 and s.vt < 0.4:
            self._still_t = getattr(self, "_still_t", None) or s.t
            if s.t - self._still_t > c.get("t_still", 1.5):
                self.veh.send()
                return True
        else:
            self._still_t = None
        d, acc, info = self.landing_cmd(s)
        self.actuate(s, d, acc, extra=info, phase=phase)
        return False

    # ------------------------------------------------------------------ loop helpers
    def frames(self):
        """Generator of (state) at telemetry rate; tolerant to short telemetry gaps."""
        misses = 0
        while True:
            try:
                fr = self.client.next_sample(timeout=2.0)
            except TimeoutError:
                # the game sometimes stalls for tens of seconds; physics is frozen meanwhile, so just wait
                misses += 1
                if misses > 300:
                    raise
                continue
            misses = 0
            recs = self.veh.read(fr)
            self.nav.com_y = self.cfg.get("com_y_loaded", 0.0) if self.payload_attached else self.cfg.get("com_y_empty", 0.0)
            s = self.nav.update(fr, recs)
            if s is None:
                continue
            s.recs = recs
            yield s

    def close(self):
        try:
            if self.log:
                self.log.close()
            (self.run_dir / "fsw_events.json").write_text(json.dumps(self.events, indent=1))
        finally:
            self.client.close()
