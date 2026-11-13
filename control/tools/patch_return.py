"""One-off patch: quick release, reverse-thrust braking and powered fly-back for the fuel-free launcher;
circularisation with gravity compensation; landing guidance overrides."""
import ast
import json

# ---------------- guidance ----------------
p = 'fsw/guidance.py'
s = open(p).read()
# burn-time estimate without the booster speed penalty for fuel-free thrusters
s = s.replace('''                t_burn = max(0.0, dv) / max(1.0, acc_max * phi(0.5 * (vt_ap + vcirc(r_ap))))''',
              '''                pen = 1.0 if p.get("climb_mode", "pwm") == "prop" else phi(0.5 * (vt_ap + vcirc(r_ap)))
                t_burn = max(0.0, dv) / max(1.0, acc_max * pen)''')
open(p, 'w').write(s)
ast.parse(s)

# ---------------- landing guidance: overrides + centrifugal term ----------------
p = 'fsw/core.py'
s = open(p).read()
s = s.replace('''    def landing_cmd(self, s, hold_alt=None):
        """Hover-translate to the pad and descend. Returns (direction, thrust_acc, info)."""
        c = self.cfg''', '''    def landing_cmd(self, s, hold_alt=None, over=None):
        """Hover-translate to the pad and descend. Returns (direction, thrust_acc, info).
        over: optional dict of parameter overrides (used for the high-altitude fly-back)."""
        c = self.cfg if not over else {**self.cfg, **over}''')
s = s.replace('''        a_up = s.g + s.k * s.vr + c["vz_kp"] * (v_des - s.vr) + ff + self.vz_int''',
              '''        a_up = s.g - s.vt * s.vt / s.r + s.k * s.vr + c["vz_kp"] * (v_des - s.vr) + ff + self.vz_int
        a_up = max(a_up, c.get("a_up_min", 0.0))''')
open(p, 'w').write(s)
ast.parse(s)

# ---------------- mission ----------------
p = 'fsw/mission_orbit.py'
s = open(p).read()
old = s[s.index('        elif phase == "RELEASE":'):s.index('        elif phase == "PHASING":')]
new = '''        elif phase == "RELEASE":
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
            keys = [(d_.guid, "ExplodeKey") for d_ in fl.veh.decouplers] if s.t < fire_until else ()
            fl.actuate(s, t_hat, 0.0, keys=keys, phase=phase)
            if rev["t_sep"] is not None and s.t - rev["t_sep"] > c.get("post_release_wait", 4.0):
                root = np.array(s.p)
                sep = min(norm(np.array(s.recs[b.guid]["position"], dtype=float) - root) for b in payload if b.guid in s.recs)
                fl.event(s, f"separated: distance={sep:.1f} integ={s.integrity}")
                if c.get("propulsion", "booster") == "rcs":
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
            d, acc, info = fl.landing_cmd(s, hold_alt=h_cruise, over=c.get("cruise", {}))
            fl.actuate(s, d, acc, extra=info, phase=phase)
            if (s.pad_dist < c.get("cruise_exit_dist", 40.0) and s.vt < c.get("cruise_exit_v", 15.0)) or s.t - t_ph > 400.0:
                fl.event(s, f"over the pad: pad_dist={s.pad_dist:.1f} vt={s.vt:.1f} h={s.h:.0f}; descending")
                phase, t_ph = "DROP", s.t
'''
s = s.replace(old, new)
s = s.replace('''    token_done, token_ticks = False, 0
''', '''    token_done, token_ticks = False, 0
    h_cruise = 500.0
''', 1)
open(p, 'w').write(s)
ast.parse(s)

c = json.load(open('config_v3.json'))
c["ascent"].update({"ra1": 1290.0, "ra_target": 1290.0, "rc_target": 1290.0, "rp_ok": 1250.0, "rp_min": 1200.0,
                    "circ_tgo": 0.3, "circ_tgo_max": 12.0, "vr_ok": 2.0})
c.update({
    "cross_k": 0.06,
    "release_wait": 1.0, "release_err_deg": 8.0, "release_rate": 0.5, "release_timeout": 8.0, "post_release_wait": 2.5,
    "brake_gain": 1.0, "brake_vtol": 4.0,
    "cruise_hmin": 480.0, "cruise_hmax": 900.0, "cruise_exit_dist": 15.0, "cruise_exit_v": 6.0,
    "cruise": {"lat_kp": 0.12, "lat_kd": 0.6, "lat_vmax": 60.0, "lat_amax": 9.0, "tilt_max_deg": 60.0, "alt_kp": 0.4},
    "a_brake": 4.0, "a_up_min": 2.0, "tilt_max_deg": 20.0,
})
json.dump(c, open('config_v3.json', 'w'), indent=1)
print("ok")
