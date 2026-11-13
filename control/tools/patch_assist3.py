"""One-off patch: attitude assist for the EMPTY vehicle with few thrusters, also as differential thrust while the lift
engines are on (the wheels alone turn the big empty raft at only ~7.5 deg/s)."""
import ast, json
p='fsw/core.py'; s=open(p).read()
i0 = s.index('            if (self.cfg.get("att_assist", False) and not rcs and s.alt > self.cfg.get("assist_alt_min", 300.0)')
i1 = s.index('            rcs.update(self.roll_cmd(s))')
new = '''            if self.cfg.get("att_assist", False):
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
'''
s = s[:i0] + new + s[i1:]
i0 = s.index('    def assist_cmd(self, s):')
i1 = s.index('    def roll_cmd(self, s):')
new = '''    def assist_cmd(self, s):
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

'''
s = s[:i0] + new + s[i1:]
open(p,'w').write(s); ast.parse(s)
c = json.load(open("config_v3j.json"))
c.update({"assist_loaded_only": False, "assist_n": 10, "assist_n_empty": 4, "assist_on_empty": 0.05, "assist_off_empty": 0.02,
          "assist_alt_min": 300.0, "assist_alt_min_empty": 0.0, "att_rate_max_empty": 0.22})
json.dump(c, open("config_v3j.json", "w"), indent=1)
print("ok")
