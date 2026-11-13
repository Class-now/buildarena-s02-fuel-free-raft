"""One-off patch: well-conditioned attitude commands during the descent."""
import ast, json
p='fsw/core.py'; s=open(p).read()
a='''        # tilt limit
        d = unit(A)
        tilt_max = math.radians(c["tilt_max_deg"])
'''
b='''        # tilt limit
        d = unit(A)
        tilt_max = math.radians(c["tilt_max_deg"])
        if hold_alt is None and a_up < c.get("tilt_aup_ref", 0.0):
            # little thrust (accelerating downwards at the start of the descent): a small lateral demand would ask for a
            # large tilt and flip it again a second later -> stay nearly vertical until the engines carry the weight
            tilt_max = math.radians(c.get("tilt_low_deg", 3.0))
'''
assert a in s; s=s.replace(a,b,1)
a='''        cosu = max(0.3, float(np.dot(s.up, s.n)))
        acc = a_up / cosu
        return d, acc, (v_des, al, a_up)'''
b='''        rate = c.get("cmd_slew_deg", 0.0) if hold_alt is None else 0.0
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
        return d, acc, (v_des, al, a_up)'''
assert a in s; s=s.replace(a,b,1)
open(p,'w').write(s); ast.parse(s)
for f in ("config_v3j.json",):
    c = json.load(open(f))
    c.update({"tilt_aup_ref": 8.0, "tilt_low_deg": 3.0, "cmd_slew_deg": 7.0, "cruise_exit_dist": 10.0, "cruise_exit_v": 2.0})
    json.dump(c, open(f, "w"), indent=1)
print("ok")
