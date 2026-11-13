import ast, json
p='fsw/guidance.py'; s=open(p).read()
a='''                lim = p.get("circ_beta_lim", 0.35)
                beta = max(math.pi / 2 - lim, min(math.pi / 2 + lim, beta))'''
b='''                lim = p.get("circ_beta_lim", 0.35)
                if abs(dvr) > p.get("vr_ok", 1.5) and abs(dvr) > 1.5 * abs(dvt):
                    lim = p.get("circ_beta_lim_radial", lim)   # a real radial error is left: allow a steeper axis
                beta = max(math.pi / 2 - lim, min(math.pi / 2 + lim, beta))'''
assert a in s; s=s.replace(a,b,1); open(p,'w').write(s); ast.parse(s)
c = json.load(open('config_v3j.json'))
c["assist_n"] = 10
c["ascent"].update({"ra1": 1320.0, "ra_target": 1320.0, "rc_target": 1320.0, "rp_ok": 1270.0, "rp_min": 1215.0,
                    "circ_beta_lim_radial": 1.0})
json.dump(c, open('config_v3j.json', 'w'), indent=1)
print("ok")
