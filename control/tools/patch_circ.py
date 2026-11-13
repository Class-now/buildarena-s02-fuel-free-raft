import ast, json
p='fsw/guidance.py'; s=open(p).read()
a='''            if dvt > 0.2:
                beta = math.atan2(dvt, dvr)
            else:
                beta = math.pi / 2                 # stay horizontal (prograde) for the payload release
'''
b='''            if dvt > 0.2:
                beta = math.atan2(dvt, dvr)
            else:
                beta = math.pi / 2                 # stay horizontal (prograde) for the payload release
            fine = dv < p.get("dv_clamp", 2.5)
            if fine:
                # the direction of a small velocity-to-go vector is noisy: stay close to prograde, trim along the axis
                lim = p.get("circ_beta_lim", 0.35)
                beta = max(math.pi / 2 - lim, min(math.pi / 2 + lim, beta))
'''
assert a in s; s=s.replace(a,b,1)
a='''            thr = 1.0 if dv > p.get("dv_fine", 4.0) else max(0.12, dv / p.get("dv_fine", 4.0))
            if dvt <= 0.2 and abs(dvr) < 0.5:
                thr = 0.0
            return beta, thr, self.stage'''
b='''            thr = 1.0 if dv > p.get("dv_fine", 4.0) else max(0.12, dv / p.get("dv_fine", 4.0))
            if dvt <= 0.2 and abs(dvr) < 0.5:
                thr = 0.0
            if fine:
                along = dvr * math.cos(beta) + dvt * math.sin(beta)
                thr = max(0.12, along / p.get("dv_fine", 4.0)) if along > 0.3 else 0.0
            return beta, thr, self.stage'''
assert a in s; s=s.replace(a,b,1)
open(p,'w').write(s); ast.parse(s)

p='fsw/nav.py'; s=open(p).read()
a='''        s.w = np.array(root["angular_velocity"], dtype=float)
'''
b='''        s.w = np.array(root["angular_velocity"], dtype=float)
        if self.com_y:
            # velocity of the centre of mass (the root block sits below it): removes the rotation-induced part
            s.vel = s.vel + np.cross(s.w, qrot(s.q, Y) * self.com_y)
'''
assert a in s; s=s.replace(a,b,1)
a='''        self.last = None
'''
b='''        self.last = None
        self.com_y = 0.0
'''
assert a in s; s=s.replace(a,b,1)
open(p,'w').write(s); ast.parse(s)

p='fsw/core.py'; s=open(p).read()
a='''            recs = self.veh.read(fr)
            s = self.nav.update(fr, recs)'''
b='''            recs = self.veh.read(fr)
            self.nav.com_y = self.cfg.get("com_y_loaded", 0.0) if self.payload_attached else self.cfg.get("com_y_empty", 0.0)
            s = self.nav.update(fr, recs)'''
assert a in s; s=s.replace(a,b,1)
open(p,'w').write(s); ast.parse(s)
c=json.load(open('config_v3dl.json')); c.update({"com_y_loaded": 0.86, "com_y_empty": 0.26}); json.dump(c, open('config_v3dl.json','w'), indent=1)
print("ok")
