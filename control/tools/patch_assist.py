"""One-off patch: optional attitude assist with thruster couples while the lift engines are idle (config att_assist)."""
import ast, json
p='fsw/attitude.py'; s=open(p).read()
a='''        cmd = {
            "x": self.kd * (rx - w_b[0]) + self.damp(("x")) * rx + self.ki * self.int_x,'''
b='''        self.rate_err = (rx - w_b[0], rz - w_b[2])       # used by the thruster-couple assist
        cmd = {
            "x": self.kd * (rx - w_b[0]) + self.damp(("x")) * rx + self.ki * self.int_x,'''
assert a in s; s=s.replace(a,b,1)
a='''        self.damp_ratio = 0.0
'''
b='''        self.damp_ratio = 0.0
        self.rate_err = (0.0, 0.0)
'''
assert a in s; s=s.replace(a,b,1)
open(p,'w').write(s); ast.parse(s)

p='fsw/core.py'; s=open(p).read()
a='''            self.f_last, self.n_last = f, sum(1 for v in rcs.values() if v)
            rcs.update(self.roll_cmd(s))'''
b='''            self.f_last, self.n_last = f, sum(1 for v in rcs.values() if v)
            if self.cfg.get("att_assist", False) and not rcs and s.alt > self.cfg.get("assist_alt_min", 300.0):
                rcs.update(self.assist_cmd(s))
            rcs.update(self.roll_cmd(s))'''
assert a in s; s=s.replace(a,b,1)
a='''    def roll_cmd(self, s):'''
b='''    def assist_cmd(self, s):
        """Attitude assist while the lift engines are idle (turns in coast / in orbit): the outer thrusters of two
        opposite arms fire in opposite directions = pure torque about a body axis (tau_x = -z F_y, tau_z = x F_y).
        Bang-bang on the rate error of the pointing loop, with hysteresis; the reaction wheels do the fine work."""
        c = self.cfg
        if not hasattr(self, "_assist_sets"):
            lift, root, n = self.veh.rcs_lift, self.veh.root.pos, int(c.get("assist_n", 4))

            def arm(axis, sign):
                other = 2 - axis
                cand = [b for b in lift if sign * (b.pos[axis] - root[axis]) > 1.5 and abs(b.pos[other] - root[other]) < 1.0]
                cand.sort(key=lambda b: -abs(b.pos[axis] - root[axis]))
                return cand[:n]
            # (thrusters whose +Y push gives positive torque, thrusters whose +Y push gives negative torque)
            self._assist_sets = ((arm(2, -1), arm(2, +1)), (arm(0, +1), arm(0, -1)))
            self._assist_state = [0, 0]
        on, off = c.get("assist_on", 0.08), c.get("assist_off", 0.04)
        out = {}
        for i in (0, 1):
            err = self.att.rate_err[i]
            st = self._assist_state[i]
            if abs(err) > on:
                st = 1 if err > 0 else -1
            elif abs(err) < off or (st != 0 and (err > 0) != (st > 0)):
                st = 0
            self._assist_state[i] = st
            if st:
                for b in self._assist_sets[i][0]:
                    out[b.guid] = st
                for b in self._assist_sets[i][1]:
                    out[b.guid] = -st
        return out

    def roll_cmd(self, s):'''
assert a in s; s=s.replace(a,b,1)
open(p,'w').write(s); ast.parse(s)

c = json.load(open('config_v3i.json'))
c.update({"m_dry_vehicle": 60.36, "m_payload": 25.23, "com_y_loaded": 3.2, "com_y_empty": 0.25,
          "wheel_gain_loaded": {"x": 0.25, "z": 0.25, "y": 1.8}, "wheel_gain_empty": {"x": 0.45, "z": 0.45, "y": 1.8},
          "att_assist": True, "assist_n": 4, "assist_on": 0.08, "assist_off": 0.04, "assist_alt_min": 300.0,
          "att_rate_max": 0.22, "att_rate_max_empty": 0.32,
          "a_brake": 1.8, "h_flare": 2.5})
json.dump(c, open('config_v3j.json', 'w'), indent=1)
print("ok")
