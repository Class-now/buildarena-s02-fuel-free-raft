import ast, json
p = 'fsw/attitude.py'
s = open(p).read()
a = '''            "x": self.kd * (rx - w_b[0]) + self.damp_ff * rx + self.ki * self.int_x,
            "z": self.kd * (rz - w_b[2]) + self.damp_ff * rz + self.ki * self.int_z,'''
b = '''            "x": self.kd * (rx - w_b[0]) + self.damp(("x")) * rx + self.ki * self.int_x,
            "z": self.kd * (rz - w_b[2]) + self.damp(("z")) * rz + self.ki * self.int_z,'''
assert a in s
s = s.replace(a, b)
a = '''    def set_gains(self, gains):'''
b = '''    def damp(self, name):
        """Rotational damping of the vehicle about this axis [1/s]: the wheels behave like rate servos, so the
        damping is proportional to the wheel gain (damp_ratio = damping / gain, measured in flight)."""
        ch = self.ch.get(name)
        return self.damp_ff + (self.damp_ratio * ch.gain if ch is not None else 0.0)

    def set_gains(self, gains):'''
assert a in s
s = s.replace(a, b, 1)
a = '''        self.damp_ff = 0.0
'''
b = '''        self.damp_ff = 0.0
        self.damp_ratio = 0.0
'''
assert a in s
s = s.replace(a, b, 1)
open(p, 'w').write(s); ast.parse(s)

p = 'fsw/core.py'
s = open(p).read()
a = '''        self.att.damp_ff = self.cfg.get("att_damp_ff", 0.0)'''
b = '''        self.att.damp_ff = self.cfg.get("att_damp_ff", 0.0)
        self.att.damp_ratio = self.cfg.get("att_damp_ratio", 0.0)'''
assert a in s
s = s.replace(a, b, 1)
open(p, 'w').write(s); ast.parse(s)

c = json.load(open('config_v3.json'))
c["att_damp_ratio"] = 0.69
json.dump(c, open('config_v3.json', 'w'), indent=1)
c.update({"m_dry_vehicle": 24.99, "m_payload": 12.13,
          "wheel_gain_loaded": {"x": 1.8, "z": 1.8, "y": 1.8}, "wheel_gain_empty": {"x": 2.9, "z": 2.9, "y": 1.8}})
json.dump(c, open('config_v3c.json', 'w'), indent=1)
print("ok", c["wheel_gain_loaded"], c.get("att_rate_max"))
