"""One-off patch: circularisation robustness.
 - burn centred on the real apoapsis also when it overshoots the target a little (circ_ap_margin);
 - never thrust prograde once the tangential speed is reached (was: could run away if still sinking fast);
   a remaining sink rate is corrected by (nearly) radial thrust only;
 - extra exits: fast enough and not sinking; time-out with a lower periapsis floor."""
import ast, json
p='fsw/guidance.py'; s=open(p).read()
a='''            if vr > 0.0 and r_ap < rc + 2.0:'''
b='''            if vr > 0.0 and r_ap < rc + p.get("circ_ap_margin", 2.0):'''
assert a in s; s=s.replace(a,b,1)
i0 = s.index('            dv = math.hypot(dvr, dvt)\n            if dvt > 0.2:\n                beta = math.atan2(dvt, dvr)')
i1 = s.index('            return beta, thr, self.stage\n        return math.pi / 2, 0.0, self.stage')
new = '''            rp, ra, ecc = apsides(r, vr, vt)
            vr_ok = p.get("vr_ok", 1.5)
            if self.t_circ is None:
                self.t_circ = t
            done = (dvt <= 0.3 and abs(vr) < vr_ok) or (rp >= p["rp_ok"] and ra < p.get("ra_ok", 1e9))
            done = done or (dvt <= 0.3 and vr > -vr_ok)                    # fast enough and not sinking
            if done and rp >= p["rp_min"]:
                self.stage = "ORBIT"
                return math.pi / 2, 0.0, self.stage
            if t - self.t_circ > p.get("circ_timeout", 1e9) and dvt <= 0.3 and rp >= p.get("rp_floor", p["rp_min"]):
                self.stage = "ORBIT"                                       # safety net: do not burn for ever
                return math.pi / 2, 0.0, self.stage
            if dvt > 0.2:
                ax_t, ax_r = dvt, dvr
            else:
                # tangential speed reached: NEVER add prograde speed any more; only a remaining sink rate is corrected
                ax_t, ax_r = 0.2, (dvr if dvr > vr_ok else 0.0)
            dv = math.hypot(ax_r, ax_t)
            beta = math.atan2(ax_t, ax_r)
            fine = dv < p.get("dv_clamp", 2.5) and not (dvt <= 0.2 and ax_r > 0.0)
            if fine:
                # the direction of a small velocity-to-go vector is noisy: stay close to prograde, trim along the axis
                lim = p.get("circ_beta_lim", 0.35)
                if abs(dvr) > vr_ok and abs(dvr) > 1.5 * abs(dvt):
                    lim = p.get("circ_beta_lim_radial", lim)   # a real radial error is left: allow a steeper axis
                beta = max(math.pi / 2 - lim, min(math.pi / 2 + lim, beta))
                along = ax_r * math.cos(beta) + ax_t * math.sin(beta)
                thr = max(0.12, along / p.get("dv_fine", 4.0)) if along > 0.3 else 0.0
            elif dvt <= 0.2:
                thr = min(1.0, max(0.12, ax_r / p.get("dv_fine", 4.0))) if ax_r > 0.0 else 0.0
            else:
                thr = 1.0 if dv > p.get("dv_fine", 4.0) else max(0.12, dv / p.get("dv_fine", 4.0))
'''
s = s[:i0] + new + s[i1:]
a='''class AscentGuidance:'''
assert a in s
open(p,'w').write(s); ast.parse(s)
print(s[s.index('class AscentGuidance:'):s.index('class AscentGuidance:')+700])
