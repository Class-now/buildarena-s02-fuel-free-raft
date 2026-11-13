"""One-off patch: integrator option in landing guidance, hop mission parameters, v3 config."""
import ast
import json

p = 'fsw/core.py'
s = open(p).read()
s = s.replace('''        if hold_alt is None and s.h < c.get("h_int", 6.0):
            self.vz_int = clip(getattr(self, "vz_int", 0.0) + c.get("vz_ki", 4.0) * (v_des - s.vr) * dt, -15.0, 5.0)''',
              '''        if c.get("vz_int_always", False) or (hold_alt is None and s.h < c.get("h_int", 6.0)):
            self.vz_int = clip(getattr(self, "vz_int", 0.0) + c.get("vz_ki", 4.0) * (v_des - s.vr) * dt,
                               -15.0, c.get("vz_int_max", 5.0))''')
open(p, 'w').write(s)
ast.parse(s)

p = 'fsw/mission_hop.py'
s = open(p).read()
s = s.replace('''            a = s.g + s.k * s.vr + c["vz_kp"] * (30.0 - s.vr)
            fl.actuate(s, s.n, clip(a, 0.0, 60.0), phase=phase)''',
              '''            a = s.g + s.k * s.vr + c["vz_kp"] * (float(os.environ.get("HOP_VCLIMB", "30")) - s.vr)
            fl.actuate(s, s.n, clip(a, 0.0, min(60.0, 0.95 * fl.max_acc(s))), phase=phase)''')
s = s.replace('''            tilt = math.radians(15.0)''', '''            tilt = math.radians(float(os.environ.get("HOP_TILT", "15")))''')
open(p, 'w').write(s)
ast.parse(s)

cfg = json.load(open('config.json'))
cfg.update({
    "propulsion": "rcs",
    "m_dry_vehicle": 22.76, "m_payload": 6.89, "fuel_density": 0.0,
    "rcs_force": 8.3, "fan_force": 47.0, "fan_ceiling": 255.0,
    "wheel_gain_loaded": {"x": 2.5, "z": 2.5, "y": 1.8}, "wheel_gain_empty": {"x": 3.3, "z": 3.3, "y": 1.8},
    "att_kp": 1.5, "att_kd": 3.0,
    "a_brake": 6.0, "v_desc_max": 25.0, "lat_kp": 0.3, "lat_amax": 4.0, "lat_vmax": 12.0, "tilt_max_deg": 12.0,
    "vz_kp": 1.5, "vz_ki": 2.0, "vz_int_always": True, "vz_int_max": 15.0, "pad_tol": 2.0,
})
json.dump(cfg, open('config_v3.json', 'w'), indent=1)
print("ok")
