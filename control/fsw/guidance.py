"""Pure guidance functions (no I/O) shared by the flight software and the offline simulator.

Planar quantities: r (radius from planet centre), vr (radial speed), vt (tangential speed, prograde > 0).
Thrust direction is given by beta = angle from the local vertical (radial out) towards prograde.
"""
import math

MU = 8456800.0
R0 = 600.0
GCAP = 22.0
F2 = 423.0
PA, PB, PFLOOR = 0.00185, 9.36e-5, 0.155


def grav(r):
    return min(GCAP, MU / (r * r))


def dragk(r):
    return max(0.0, 0.092 * (1.0 - (r - R0) / 450.0))


def phi(v_ax):
    if v_ax <= 0.0:
        return 1.0
    return max(PFLOOR, 1.0 - PA * v_ax - PB * v_ax * v_ax)


def vcirc(r):
    return math.sqrt(MU / r)


def coast_apoapsis(r, vr, vt, dt=0.25, t_max=600.0):
    """Ballistic coast with drag until apoapsis. Returns (r_ap, vt_ap, t_ap)."""
    t = 0.0
    if vr <= 0.0:
        return r, vt, 0.0
    while t < t_max:
        k = dragk(r)
        ar = vt * vt / r - grav(r) - k * vr
        at = -vr * vt / r - k * vt
        vr_n = vr + ar * dt
        if vr_n <= 0.0:
            frac = vr / (vr - vr_n) if vr != vr_n else 0.0
            return r + vr * dt * frac * 0.5, vt + at * dt * frac, t + dt * frac
        r += 0.5 * (vr + vr_n) * dt
        vt += at * dt
        vr = vr_n
        t += dt
    return r, vt, t


def apsides(r, vr, vt):
    e = 0.5 * (vr * vr + vt * vt) - MU / r
    h = r * vt
    ecc = math.sqrt(max(0.0, 1.0 + 2.0 * e * h * h / (MU * MU)))
    p = h * h / MU
    rp = p / (1.0 + ecc)
    ra = p / (1.0 - ecc) if ecc < 1.0 else float("inf")
    return rp, ra, ecc


class AscentGuidance:
    """Phase 1: climb with the thrust-axis speed held near the efficient value, pitching over with altitude,
    until the ballistic apoapsis reaches the target. Phase 2: coast. Phase 3: circularise at apoapsis."""

    def __init__(self, p):
        self.p = p
        self.on = False
        self.stage = "CLIMB"
        self.t_circ = None

    def pitch(self, alt):
        p = self.p
        x = (alt - p["h1"]) / max(1.0, p["h2"] - p["h1"])
        x = 0.0 if x < 0 else 1.0 if x > 1 else x
        b = p["beta_max"] * x * x * (3.0 - 2.0 * x)
        h3 = p.get("h3", 0.0)
        if h3 > p["h2"] and alt > p["h2"]:
            y = min(1.0, (alt - p["h2"]) / (h3 - p["h2"]))
            b += (p.get("beta2", p["beta_max"]) - p["beta_max"]) * y
        return math.radians(b)

    def step(self, t, r, vr, vt, acc_max):
        """acc_max: thrust acceleration available at phi=1 with the boosters in use.
        Returns (beta, throttle 0..1, stage).

        CLIMB : pitch program + axial-speed hold until the ballistic apoapsis reaches ra1.
        BOOST : horizontal prograde thrust (efficient while vt < ~60) until the apoapsis reaches ra_target (> rc_target).
        COAST : over the top; the final burn starts on the way down at rc_target (or at apoapsis if it is below it).
        CIRC  : thrust along the velocity-to-go vector (0 - vr, vcirc - vt); while sinking the radial part of the
                thrust keeps the axial speed low, i.e. the burn stays efficient.
        """
        p = self.p
        alt = r - R0
        if self.stage == "CLIMB":
            beta = self.pitch(alt)
            v_ax = vr * math.cos(beta) + vt * math.sin(beta)
            if self.on and v_ax > p["v_ax"] + p["v_hyst"]:
                self.on = False
            elif (not self.on) and v_ax < p["v_ax"] - p["v_hyst"]:
                self.on = True
            r_ap, vt_ap, t_ap = coast_apoapsis(r, vr, vt)
            if r_ap >= p.get("ra1", p["ra_target"]):
                self.stage = "BOOST"
                self.on = False
                return math.pi / 2, 0.0, self.stage
            if p.get("climb_mode", "pwm") == "prop":
                # fuel-free thrusters have no speed penalty: smooth proportional speed hold (no on/off shocks),
                # speed limit rising with altitude as the air thins out
                v_tgt = p["v_ax"] + p.get("v_gain_alt", 0.0) * max(0.0, alt - p.get("v_alt0", 250.0))
                a = grav(r) * math.cos(beta) + dragk(r) * v_ax + p.get("climb_kv", 1.0) * (v_tgt - v_ax)
                return beta, max(0.0, min(1.0, a / max(1e-6, acc_max))), self.stage
            return beta, (1.0 if self.on else 0.0), self.stage
        if self.stage == "BOOST":
            r_ap, vt_ap, t_ap = coast_apoapsis(r, vr, vt)
            if r_ap >= p["ra_target"] or vr <= 1.0:
                self.stage = "COAST"
                return math.pi / 2, 0.0, self.stage
            # horizontal prograde; throttle down when close to the target apoapsis
            thr = 1.0 if p["ra_target"] - r_ap > p.get("boost_fine", 15.0) else 0.3
            if vt > p.get("vt_boost_max", 68.0):
                thr = 0.0
            return math.pi / 2, thr, self.stage
        if self.stage == "COAST":
            rc = p["rc_target"]
            r_ap, vt_ap, t_ap = coast_apoapsis(r, vr, vt)
            if vr > 0.0 and r_ap < rc + p.get("circ_ap_margin", 2.0):
                # apoapsis will not rise above the target radius: circularise at apoapsis
                dv = vcirc(r_ap) - vt_ap
                pen = 1.0 if p.get("climb_mode", "pwm") == "prop" else phi(0.5 * (vt_ap + vcirc(r_ap)))
                t_burn = max(0.0, dv) / max(1.0, acc_max * pen)
                if t_ap <= 0.5 * t_burn + p.get("circ_lead", 0.1) or vr <= 0.3:
                    self.stage = "CIRC"
            elif vr <= 0.0:
                dvr, dvt = -vr, vcirc(rc) - vt
                dv = math.hypot(dvr, dvt)
                bta = math.atan2(dvt, dvr)
                v_ax = vr * math.cos(bta) + vt * math.sin(bta)
                t_burn = dv / max(1.0, acc_max * phi(v_ax))
                if r <= rc + 0.5 * (-vr) * t_burn + (-vr) * p.get("circ_lead", 0.1) or r <= rc:
                    self.stage = "CIRC"
            # pre-point for the final burn
            dvr, dvt = -min(vr, 0.0), max(1.0, vcirc(rc) - vt)
            return math.atan2(dvt, dvr), 0.0, self.stage
        if self.stage == "CIRC":
            rc = p["rc_target"]
            vc = vcirc(r)
            g_eff = grav(r) - vt * vt / r
            dvt = vc - vt
            # remaining burn time: gravity keeps pulling while the tangential speed is built up, so the radial
            # velocity-to-go includes the gravity loss over the rest of the burn (about half of g_eff * t_go)
            t_go = min(p.get("circ_tgo_max", 12.0), max(0.0, dvt) / max(1.0, acc_max))
            dvr = -vr + p.get("circ_kr", 0.0) * (rc - r) + g_eff * max(p.get("circ_tgo", 0.3), 0.5 * t_go)
            rp, ra, ecc = apsides(r, vr, vt)
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
            return beta, thr, self.stage
        return math.pi / 2, 0.0, self.stage
