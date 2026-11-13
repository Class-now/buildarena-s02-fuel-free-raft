import ast, json
p='fsw/mission_orbit.py'; s=open(p).read()
a='''            beta, thr, stage = g.step(s.t, s.r, s.vr, vt, acc_max)
'''
b='''            beta, thr, stage = g.step(s.t, s.r, s.vr, vt, acc_max)
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
'''
assert a in s; s=s.replace(a,b,1)
a='''    token_done, token_ticks = False, 0
'''
b='''    token_done, token_ticks = False, 0
    stall_t, aborted = None, False
'''
assert a in s; s=s.replace(a,b,1)
a='''            revs = abs(rev["angle"]) / (2 * math.pi)
'''
b='''            revs = abs(rev["angle"]) / (2 * math.pi)
            if aborted and s.t - t_land > 8.0:
                fl.event(s, f"ABORTED MISSION: landed pad={s.pad_dist:.2f} integ={s.integrity}")
                break
'''
assert a in s; s=s.replace(a,b,1)
a='''                fl.att.set_gains(c["wheel_gain_empty"])
'''
b='''                fl.att.set_gains(c["wheel_gain_empty"])
                fl.att.rate_max = c.get("att_rate_max_empty", fl.att.rate_max)
'''
assert a in s; s=s.replace(a,b,1)
open(p,'w').write(s); ast.parse(s)

p='fsw/core.py'; s=open(p).read()
a='''        return c.get("fan_force", 47.0) * speed * max(0.0, 1.0 - s.alt / c.get("fan_ceiling", 255.0))'''
b='''        f = c.get("fan_force", 47.0) * speed * max(0.0, 1.0 - s.alt / c.get("fan_ceiling", 255.0))
        if "fan_vmax" in c:
            # measured: the fan force also fades with the speed along its axis
            v_ax = float(np.dot(s.vel, s.up))
            f *= max(0.2, 1.0 - max(0.0, v_ax) / c["fan_vmax"])
        return f'''
assert a in s; s=s.replace(a,b,1)
open(p,'w').write(s); ast.parse(s)

c=json.load(open('config_v3dl.json'))
c.update({"rcs_force": 8.8, "fan_force": 67.75, "fan_ceiling": 195.0, "fan_vmax": 70.0,
          "m_dry_vehicle": 38.17, "m_payload": 16.06, "com_y_loaded": 1.78, "com_y_empty": 0.25,
          "wheel_gain_loaded": {"x": 0.92, "z": 0.92, "y": 1.8}, "wheel_gain_empty": {"x": 1.46, "z": 1.46, "y": 1.8},
          "att_rate_max": 0.3, "att_rate_max_empty": 0.45})
json.dump(c, open('config_v3e.json','w'), indent=1)
print("ok")
