"""One-off patch: roll control with tip thrusters, v3b config."""
import ast
import json

p = 'fsw/vehicle.py'
s = open(p).read()
s = s.replace('''        self.rcs_quads = self._quads()''', '''        self.rcs_quads = self._quads()
        # tip thrusters (horizontal nozzle axis): roll torque coefficient about body +Y per unit command
        self.rcs_tip = []
        for b in self.rcs:
            a = self.rcs_axis[b.guid]
            if abs(a[1]) < 0.1:
                px, pz = b.pos[0] - self.root.pos[0], b.pos[2] - self.root.pos[2]
                self.rcs_tip.append((b, pz * a[0] - px * a[2], a))''')
open(p, 'w').write(s)
ast.parse(s)

p = 'fsw/core.py'
s = open(p).read()
s = s.replace('''            if ok and abs(acc) > 1e-6:
                rcs, fan, f = self.lift_allocate(s, acc)
            self.f_last, self.n_last = f, sum(1 for v in rcs.values() if v)''', '''            if ok and abs(acc) > 1e-6:
                rcs, fan, f = self.lift_allocate(s, acc)
            self.f_last, self.n_last = f, sum(1 for v in rcs.values() if v)
            rcs.update(self.roll_cmd(s))''')
s = s.replace('''    def fan_lift(self, s, speed=1.0):''', '''    def roll_cmd(self, s):
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

    def fan_lift(self, s, speed=1.0):''')
open(p, 'w').write(s)
ast.parse(s)

cfg = json.load(open('config_v3.json'))
cfg.update({
    "m_dry_vehicle": 19.23, "m_payload": 4.27,
    "wheel_gain_loaded": {"x": 5.0, "z": 5.0, "y": 1.8}, "wheel_gain_empty": {"x": 6.5, "z": 6.5, "y": 1.8},
    "att_kp": 1.5, "att_kd": 3.0, "roll_deadband": 0.04,
})
json.dump(cfg, open('config_v3.json', 'w'), indent=1)
print("ok")
