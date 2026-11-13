"""One-off patch: orbit mission + guidance adaptations for the fuel-free (RCS + lift fan) launcher."""
import ast
import json

# ---------------- guidance: proportional climb-speed mode ----------------
p = 'fsw/guidance.py'
s = open(p).read()
s = s.replace('''            beta = self.pitch(alt)
            v_ax = vr * math.cos(beta) + vt * math.sin(beta)
            if self.on and v_ax > p["v_ax"] + p["v_hyst"]:
                self.on = False
            elif (not self.on) and v_ax < p["v_ax"] - p["v_hyst"]:
                self.on = True
            r_ap, vt_ap, t_ap = coast_apoapsis(r, vr, vt)
            if r_ap >= p.get("ra1", p["ra_target"]):
                self.stage = "BOOST"
                self.on = False
                return math.pi / 2, 0.0, self.stage
            return beta, (1.0 if self.on else 0.0), self.stage''', '''            beta = self.pitch(alt)
            v_ax = vr * math.cos(beta) + vt * math.sin(beta)
            if self.on and v_ax > p["v_ax"] + p["v_hyst"]:
                self.on = False
            elif (not self.on) and v_ax < p["v_ax"] - p["v_hyst"]:
                self.on = True
            r_ap, vt_ap, t_ap = coast_apoapsis(r, vr, vt)
            if r_ap >= p.get("ra1", p["ra_target"]):
                self.stage = "BOOST"
                self.on = False
                return math.pi / 2, 0.0, self.stage
            if p.get("climb_mode", "pwm") == "prop":
                # fuel-free thrusters have no speed penalty: smooth proportional speed hold (no on/off shocks),
                # speed limit rising with altitude as the air thins out
                v_tgt = p["v_ax"] + p.get("v_gain_alt", 0.0) * max(0.0, alt - p.get("v_alt0", 250.0))
                a = grav(r) * math.cos(beta) + dragk(r) * v_ax + p.get("climb_kv", 1.0) * (v_tgt - v_ax)
                return beta, max(0.0, min(1.0, a / max(1e-6, acc_max))), self.stage
            return beta, (1.0 if self.on else 0.0), self.stage''')
open(p, 'w').write(s)
ast.parse(s)

# ---------------- mission ----------------
p = 'fsw/mission_orbit.py'
s = open(p).read()
s = s.replace('''            acc_max = n_asc * F2 / fl.mass(s)
            beta, thr, stage = g.step(s.t, s.r, s.vr, vt, acc_max)''', '''            rcs_mode = c.get("propulsion", "booster") == "rcs"
            acc_max = fl.max_acc(s) if rcs_mode else n_asc * F2 / fl.mass(s)
            beta, thr, stage = g.step(s.t, s.r, s.vr, vt, acc_max)
            if rcs_mode and not token_done and s.alt > c.get("token_alt", 30.0):
                # token burn of the single booster (keeps the expended fuel finite and non-zero)
                token_ticks += 1
                boo = fl.veh.boosters[0]
                fl.veh.send(thr={boo.guid: c.get("token_f", 0.05)}, wheel=fl.att.update(s.q, s.w, s.n, t=s.t),
                            rcs={b.guid: 1 for q in fl.veh.rcs_quads for b in q}, fan=fl.fan_last)
                if token_ticks >= c.get("token_ticks", 2):
                    token_done = True
                    fl.event(s, f"token booster burn done, fuel={s.fuel:.4f}")
                continue''')
s = s.replace('''            fl.actuate(s, unit(d), (1e3 if thr >= 0.999 else thr * acc_max) if thr > 0 else 0.0, n_on=n_asc,
                       extra=(math.degrees(beta), thr, vt), phase=stage)''', '''            if rcs_mode:
                acc_cmd = thr * acc_max
            else:
                acc_cmd = (1e3 if thr >= 0.999 else thr * acc_max) if thr > 0 else 0.0
            fl.actuate(s, unit(d), acc_cmd, n_on=n_asc, extra=(math.degrees(beta), thr, vt), phase=stage)''')
s = s.replace('''    d_retro = None
''', '''    d_retro = None
    token_done, token_ticks = False, 0
''', 1)
# deorbit / phasing: available acceleration depends on the propulsion type
s = s.replace('''            a_max = len(fl.veh.boosters) * F2 / fl.mass(s)
            a_plan = c.get("deorbit_frac", 0.6) * a_max''', '''            a_max = fl.max_acc(s)
            a_plan = c.get("deorbit_frac", 0.6) * a_max''')
s = s.replace('''            dist = delta * s.r
            a_max = len(fl.veh.boosters) * F2 / fl.mass(s)''', '''            dist = delta * s.r
            a_max = fl.max_acc(s)''')
# end of mission: optional release test
s = s.replace('''                fl.event(s, f"MISSION COMPLETE: payload revs={revs:.3f} rmin={rev['rmin']:.1f} pad={s.pad_dist:.2f} integ={s.integrity} fuel={s.fuel:.2f}")
                break''', '''                fl.event(s, f"MISSION COMPLETE: payload revs={revs:.3f} rmin={rev['rmin']:.1f} pad={s.pad_dist:.2f} integ={s.integrity} fuel={s.fuel:.4f}")
                break''')
open(p, 'w').write(s)
ast.parse(s)

# ---------------- attitude integral clamp ----------------
p = 'fsw/attitude.py'
s = open(p).read()
s = s.replace('''            self.int_x = clip(self.int_x + ex * dt, -0.3, 0.3)
            self.int_z = clip(self.int_z + ez * dt, -0.3, 0.3)''', '''            self.int_x = clip(self.int_x + ex * dt, -self.int_max, self.int_max)
            self.int_z = clip(self.int_z + ez * dt, -self.int_max, self.int_max)''')
s = s.replace('''        self.err_deg = 0.0
        self.int_x = self.int_z = 0.0''', '''        self.err_deg = 0.0
        self.int_max = 0.6
        self.int_x = self.int_z = 0.0''')
s = s.replace('''        if self.ki > 0.0 and theta < 0.15:''', '''        if self.ki > 0.0 and theta < 0.35:''')
open(p, 'w').write(s)
ast.parse(s)

# ---------------- config ----------------
c = json.load(open('config_v3.json'))
c.update({
    "att_ki": 2.5,
    "ascent": {"climb_mode": "prop", "h1": 250.0, "h2": 520.0, "beta_max": 30.0, "v_ax": 35.0, "v_hyst": 1.5,
               "v_gain_alt": 0.25, "v_alt0": 200.0, "climb_kv": 1.0,
               "ra1": 1265.0, "ra_target": 1265.0, "rc_target": 1258.0,
               "circ_kr": 0.0, "circ_tgo": 0.5, "rp_ok": 1235.0, "rp_min": 1190.0, "dv_fine": 6.0, "circ_lead": 0.15,
               "vt_boost_max": 0.0, "boost_fine": 15.0},
    "a_brake": 5.0, "v_desc_max": 120.0, "v_touch": 1.2, "h_flare": 1.0, "h_gate": 8.0, "pad_tol": 2.0,
    "lat_kp": 0.3, "lat_kd": 0.8, "lat_vmax": 15.0, "lat_amax": 4.0, "tilt_max_deg": 12.0,
    "deorbit_frac": 0.6, "deorbit_latency": 0.1,
    "token_f": 0.05, "token_ticks": 2, "token_alt": 30.0,
    "release_wait": 3.0, "revs_required": 3.08, "t_max": 1500.0,
})
json.dump(c, open('config_v3.json', 'w'), indent=1)
print("ok")
