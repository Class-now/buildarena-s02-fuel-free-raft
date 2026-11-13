"""One-off patch: attitude rate feed-forward (cancels the measured rotational damping), direct RETURN from orbit,
optional full key release after landing."""
import ast

p = 'fsw/attitude.py'
s = open(p).read()
a = '''        cmd = {
            "x": self.kd * (clip(self.kp * ex, -self.rate_max, self.rate_max) - w_b[0]) + self.ki * self.int_x,
            "z": self.kd * (clip(self.kp * ez, -self.rate_max, self.rate_max) - w_b[2]) + self.ki * self.int_z,
            "y": -self.roll_kd * w_b[1],
        }'''
b = '''        # rate command, limited in magnitude (direction preserved); damp_ff cancels the vehicle's rotational damping
        rx, rz = self.kp * ex, self.kp * ez
        rm = math.hypot(rx, rz)
        if rm > self.rate_max:
            rx, rz = rx * self.rate_max / rm, rz * self.rate_max / rm
        cmd = {
            "x": self.kd * (rx - w_b[0]) + self.damp_ff * rx + self.ki * self.int_x,
            "z": self.kd * (rz - w_b[2]) + self.damp_ff * rz + self.ki * self.int_z,
            "y": -self.roll_kd * w_b[1],
        }'''
assert a in s
s = s.replace(a, b)
a = '''        self.int_max = 0.6
'''
b = '''        self.int_max = 0.6
        self.damp_ff = 0.0
'''
assert a in s
s = s.replace(a, b, 1)
open(p, 'w').write(s); ast.parse(s)

p = 'fsw/core.py'
s = open(p).read()
a = '''        self.log = open(self.run_dir / "fsw_log.csv", "w", buffering=1)'''
b = '''        self.att.damp_ff = self.cfg.get("att_damp_ff", 0.0)
        self.att.rate_max = self.cfg.get("att_rate_max", 0.7)
        self.log = open(self.run_dir / "fsw_log.csv", "w", buffering=1)'''
assert a in s
s = s.replace(a, b, 1)
open(p, 'w').write(s); ast.parse(s)

p = 'fsw/vehicle.py'
s = open(p).read()
a = '''                if v == 0 and getattr(self, "rcs_idle_both", False):'''
b = '''                if v == 0 and getattr(self, "rcs_idle_both", False) and not getattr(self, "rcs_release", False):'''
assert a in s
s = s.replace(a, b, 1)
open(p, 'w').write(s); ast.parse(s)

p = 'fsw/mission_orbit.py'
s = open(p).read()
a = '''                if c.get("propulsion", "booster") == "rcs":
                    phase, t_ph = "BRAKE", s.t'''
b = '''                if c.get("propulsion", "booster") == "rcs" and c.get("direct_return", True):
                    # still in orbit: turn towards the fly-back attitude first (no free fall while turning),
                    # the fly-back law then brakes and holds the altitude in one closed loop
                    h_cruise = clip(s.h + c.get("cruise_dh", 0.0), c.get("cruise_hmin", 480.0), c.get("cruise_hmax", 900.0))
                    fl.event(s, f"fly back from orbit at h={h_cruise:.0f}, pad_dist={s.pad_dist:.1f}")
                    phase, t_ph = "RETURN", s.t
                elif c.get("propulsion", "booster") == "rcs":
                    phase, t_ph = "BRAKE", s.t'''
assert a in s
s = s.replace(a, b, 1)
a = '''        elif phase == "LANDED":
            fl.veh.send()'''
b = '''        elif phase == "LANDED":
            if c.get("landed_release", False) and s.t - t_land > c.get("landed_release_wait", 3.0):
                fl.veh.rcs_release = True      # everything off: the vehicle rests on the ground with no thrust at all
            fl.veh.send()'''
assert a in s
s = s.replace(a, b, 1)
open(p, 'w').write(s); ast.parse(s)

p = 'fsw/mission_hop.py'
s = open(p).read()
a = '''        elif phase == "DOWN":
            fl.veh.send()   # everything released
            if s.t - t_ph > 12:'''
b = '''        elif phase == "DOWN":
            if s.t - t_ph > float(os.environ.get("HOP_RELEASE", "1e9")):
                if not getattr(fl.veh, "rcs_release", False):
                    fl.event(s, f"all keys released integ={s.integrity} pad={s.pad_dist:.2f}")
                fl.veh.rcs_release = True
            fl.veh.send()
            if int(s.t * 25) % 50 == 0:
                fl.event(s, f"down integ={s.integrity} pad={s.pad_dist:.2f} h={s.h:.2f} w={float(np.linalg.norm(s.w)):.3f}")
            if s.t - t_ph > float(os.environ.get("HOP_DOWN", "12")):'''
assert a in s
s = s.replace(a, b, 1)
open(p, 'w').write(s); ast.parse(s)
print("ok")
