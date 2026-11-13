import ast, json
p='fsw/vehicle.py'; s=open(p).read()
a='''                if self.rcs_axis[b.guid][1] < 0:
                    v = -v'''
b='''                if self.rcs_axis[b.guid][1] < -0.5:      # lift thruster mounted with its local +Y pointing down
                    v = -v                               # (tip thrusters have a horizontal axis: never flipped)'''
assert a in s; s=s.replace(a,b,1); open(p,'w').write(s); ast.parse(s)

p='fsw/core.py'; s=open(p).read()
a='''        al = norm(a_lat)
        if al > c["lat_amax"]:
            a_lat *= c["lat_amax"] / al
'''
b='''        al = norm(a_lat)
        if al > c["lat_amax"]:
            a_lat *= c["lat_amax"] / al
        dt = clip(s.t - getattr(self, "_land_t", s.t), 0.0, 0.2)
        self._land_t = s.t
        # integral action on the position error near the pad: cancels a constant lateral disturbance
        # (e.g. a small misalignment between the thrust axis and the root block axis)
        li = getattr(self, "lat_int", None)
        if li is None:
            li = np.zeros(3)
        if hold_alt is None and s.pad_dist < c.get("lat_int_dist", 12.0) and s.h < c.get("lat_int_h", 80.0):
            li = li + c.get("lat_ki", 0.04) * s.pad_dir * s.pad_dist * dt
            li = li - float(np.dot(li, s.n)) * s.n
            ln = norm(li)
            if ln > c.get("lat_int_max", 2.5):
                li *= c.get("lat_int_max", 2.5) / ln
        self.lat_int = li
        if hold_alt is None:
            a_lat = a_lat + li
'''
assert a in s; s=s.replace(a,b,1)
a='''        dt = clip(s.t - getattr(self, "_land_t", s.t), 0.0, 0.2)
        self._land_t = s.t
        if c.get("vz_int_always", False)'''
b='''        if c.get("vz_int_always", False)'''
assert a in s; s=s.replace(a,b,1)
open(p,'w').write(s); ast.parse(s)
print("ok")
