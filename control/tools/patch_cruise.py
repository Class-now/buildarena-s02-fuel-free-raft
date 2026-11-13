"""One-off patch: slew-limited attitude commands also in the fly-back cruise (after the first alignment), gentler cruise."""
import ast, json
p='fsw/core.py'; s=open(p).read()
a='''        rate = c.get("cmd_slew_deg", 0.0) if hold_alt is None else 0.0'''
b='''        rate = c.get("cmd_slew_deg", 0.0) if hold_alt is None else c.get("cruise_slew_deg", 0.0)'''
assert a in s; s=s.replace(a,b,1); open(p,'w').write(s); ast.parse(s)

p='fsw/mission_orbit.py'; s=open(p).read()
a='''            d, acc, info = fl.landing_cmd(s, hold_alt=h_cruise, over=c.get("cruise", {}))'''
b='''            over = dict(c.get("cruise", {}))
            if not cruise_aligned and s.t - t_ph > 1.0 and fl.att.err_deg < c.get("cruise_align_deg", 15.0):
                # first turn done (engines were inhibited meanwhile): from now on the commanded axis is slew-limited so
                # that the engines stay on during the later tilt reversals of the fly-back (no free fall while turning)
                cruise_aligned = True
                fl._d_cmd = None
            if not cruise_aligned:
                over.pop("cruise_slew_deg", None)
            d, acc, info = fl.landing_cmd(s, hold_alt=h_cruise, over=over)'''
assert a in s; s=s.replace(a,b,1)
a='''    stall_t, aborted = None, False
'''
b='''    stall_t, aborted = None, False
    cruise_aligned = False
'''
assert a in s; s=s.replace(a,b,1)
open(p,'w').write(s); ast.parse(s)
c = json.load(open("config_v3j.json"))
c["cruise"].update({"lat_vmax": 45.0, "lat_amax": 5.0, "tilt_max_deg": 40.0, "cruise_slew_deg": 7.0})
json.dump(c, open("config_v3j.json", "w"), indent=1)
print("ok", c["cruise"])
