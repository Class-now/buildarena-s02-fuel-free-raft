"""One-off patch: add RCS / lift-fan support (kept for the record)."""
import ast

p = 'fsw/vehicle.py'
s = open(p).read()
s = s.replace("ID_RCS = 91", "ID_RCS = 91\nID_FLY = 14")
s = s.replace('''        # RCS nozzle axis (local +Y) in the machine frame''', '''        self.fans = [b for b in self.blocks if b.type_id == ID_FLY]
        # RCS nozzle axis (local +Y) in the machine frame''')
s = s.replace('''        self.rcs_axis = {b.guid: qrot(b.quat, np.array([0.0, 1.0, 0.0])) for b in self.rcs}''', '''        self.rcs_axis = {b.guid: qrot(b.quat, np.array([0.0, 1.0, 0.0])) for b in self.rcs}
        # measured: LeftKey pushes the vehicle towards the thruster's local +Y, RightKey towards -Y.
        # rcs command convention used by send(): +1 = push towards body +Y (up), -1 = towards body -Y.
        self.rcs_lift = [b for b in self.rcs if abs(self.rcs_axis[b.guid][1]) > 0.9]
        self.rcs_quads = self._quads()''')
s = s.replace('''    # ---------------- telemetry ----------------''', '''    def _quads(self):
        """Group the lift thrusters into torque-free sets (same radius along its arm and same side, one per arm)."""
        groups = {}
        for b in self.rcs_lift:
            x, z = b.pos[0] - self.root.pos[0], b.pos[2] - self.root.pos[2]
            if abs(x) >= abs(z):
                r, side = abs(x), (1 if x * z > 0 else -1)
            else:
                r, side = abs(z), (1 if -z * x > 0 else -1)
            groups.setdefault((round(r), side), []).append(b)
        # fire outer sets first / alternate sides so that partial levels stay balanced
        keys = sorted(groups, key=lambda k: (-k[0], k[1]))
        return [groups[k] for k in keys]

    # ---------------- telemetry ----------------''')
s = s.replace('''    def send(self, thr=None, wheel=None, damper=0.0, keys=(), rcs=None, sliders=()):''',
              '''    def send(self, thr=None, wheel=None, damper=0.0, keys=(), rcs=None, sliders=(), fan=0.0):''')
s = s.replace('''        if self.rcs:
            rcs = rcs or {}
            for b in self.rcs:
                v = rcs.get(b.guid, 0)
                rec.append((self.idx[(b.guid, "LeftKey")], 1.0 if v < 0 else 0.0))
                rec.append((self.idx[(b.guid, "RightKey")], 1.0 if v > 0 else 0.0))''', '''        if self.rcs:
            rcs = rcs or {}
            for b in self.rcs:
                v = rcs.get(b.guid, 0)          # +1: push vehicle to body +Y, -1: to body -Y
                if self.rcs_axis[b.guid][1] < 0:
                    v = -v
                rec.append((self.idx[(b.guid, "LeftKey")], 1.0 if v > 0 else 0.0))
                rec.append((self.idx[(b.guid, "RightKey")], 1.0 if v < 0 else 0.0))
        for b in self.fans:
            sp = min(2.0, max(0.0, float(fan)))
            rec.append((self.idx[(b.guid, "speed")], sp))
            rec.append((self.idx[(b.guid, "FlyKey")], 1.0 if sp > 0.02 else 0.0))''')
open(p, 'w').write(s)

p = 'fsw/mission_rcs.py'
s = open(p).read()
s = s.replace('''        return {g: direction * s * mapping for g, s in up_sign.items()}''', '''        return {g: direction for g in up_sign}''')
open(p, 'w').write(s)

p = 'fsw/core.py'
s = open(p).read()
i0 = s.index('    def actuate(self, s, d_world, acc, n_on=None, keys=(), extra=(0, 0, 0), phase=""):')
i1 = s.index('    def select_boosters(self, n):')
new = '''    def actuate(self, s, d_world, acc, n_on=None, keys=(), extra=(0, 0, 0), phase=""):
        """Point the thrust axis along d_world and produce thrust acceleration `acc` (along the body axis).
        n_on: number of boosters to use (None = all). Engines are inhibited while the pointing error is large.
        With cfg["propulsion"] == "rcs" the thrust comes from the fuel-free thrusters / lift fans instead."""
        wheel = self.att.update(s.q, s.w, d_world, lead=self.cfg.get("att_lead", 0.06), t=s.t)
        thr, rcs, fan = {}, {}, 0.0
        f = 0.0
        ok = self.att.err_deg < self.cfg.get("max_fire_err_deg", 25.0)
        if self.cfg.get("propulsion", "booster") == "rcs":
            if ok and abs(acc) > 1e-6:
                rcs, fan, f = self.lift_allocate(s, acc)
            self.f_last, self.n_last = f, sum(1 for v in rcs.values() if v)
        else:
            boosters = self.veh.boosters
            if n_on is not None:
                boosters = self.select_boosters(n_on)
            if acc > 0.0 and boosters and ok:
                v_ax = float(np.dot(s.vel, s.up))
                force = self.mass(s) * acc / len(boosters)
                f = throttle_for_force(force, v_ax)
                for b in boosters:
                    thr[b.guid] = f
            self.f_last, self.n_last = f, (len(boosters) if f > 0 else 0)
        self.fan_last = fan
        self.veh.send(thr=thr, wheel=wheel, damper=self.cfg.get("wheel_damper", 0.0), keys=keys, rcs=rcs, fan=fan)
        self.log.write(f"{time.time()-self.wall0:.2f},{s.t:.3f},{phase},{s.alt:.2f},{s.h:.2f},{s.vr:.3f},{s.vt:.3f},{s.pad_dist:.2f},{s.fuel:.3f},"
                       f"{self.att.err_deg:.2f},{f:.3f},{self.n_last},{s.integrity},{s.alive},{s.ra:.1f},{s.rp:.1f},"
                       f"{extra[0]:.3f},{extra[1]:.3f},{extra[2]:.3f}\\n")

    def fan_lift(self, s, speed=1.0):
        """Rough model of one lift fan's force per unit slider (fades with altitude)."""
        c = self.cfg
        return c.get("fan_force", 47.0) * speed * max(0.0, 1.0 - s.alt / c.get("fan_ceiling", 255.0))

    def lift_allocate(self, s, acc):
        """Fuel-free thrust: acc (signed, along body +Y). RCS thrusters are switched in torque-free quads with
        sigma-delta dithering; the lift fans (continuous slider) supply what the thrusters cannot (low altitude)."""
        c = self.cfg
        veh = self.veh
        F = acc * self.mass(s)
        fr = c.get("rcs_force", 8.3)
        quads = veh.rcs_quads
        nq = len(quads)
        sign = 1 if F >= 0 else -1
        level = abs(F) / (4.0 * fr)                # quads needed
        fan = 0.0
        if level >= nq:
            k = nq
            if sign > 0 and veh.fans:
                extra = abs(F) - nq * 4.0 * fr
                per = len(veh.fans) * self.fan_lift(s, 1.0)
                fan = min(2.0, extra / per) if per > 1e-6 else 0.0
        else:
            k = int(level)
            self._sd = getattr(self, "_sd", 0.0) + (level - k)
            if self._sd >= 1.0:
                self._sd -= 1.0
                k += 1
        rcs = {}
        for q in quads[:k]:
            for b in q:
                rcs[b.guid] = sign
        return rcs, fan, level / max(1, nq)

'''
s = s[:i0] + new + s[i1:]
s = s.replace('''        a_up = clip(a_up, 0.0, 0.9 * self.max_acc(s))
        A = a_up * s.n + a_lat''', '''        a_up = clip(a_up, 0.0, 0.9 * self.max_acc(s))
        A = a_up * s.n + a_lat''')
i0 = s.index('    def max_acc(self, s, n=None, v_ax=0.0):')
i1 = s.index('    # ------------------------------------------------------------------ landing guidance')
new = '''    def max_acc(self, s, n=None, v_ax=0.0):
        if self.cfg.get("propulsion", "booster") == "rcs":
            F = len(self.veh.rcs_lift) * self.cfg.get("rcs_force", 8.3) + len(self.veh.fans) * self.fan_lift(s, 2.0)
            return F / self.mass(s)
        n = len(self.veh.boosters) if n is None else n
        return n * booster_force(2.0, v_ax) / self.mass(s)

'''
s = s[:i0] + new + s[i1:]
open(p, 'w').write(s)
for f in ['fsw/core.py', 'fsw/vehicle.py', 'fsw/mission_rcs.py']:
    ast.parse(open(f).read())
print("ok")
