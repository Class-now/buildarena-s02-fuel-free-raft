"""Navigation state derived from the root (Starting Block) telemetry row."""
import math
import numpy as np

from .mathx import PLANET_C, R_SURF, MU, qrot, unit, norm, gravity, drag_k

Y = np.array([0.0, 1.0, 0.0])


class State:
    pass


class Nav:
    def __init__(self, vehicle):
        self.v = vehicle
        self.t0 = None
        self.n_pad = None
        self.alt0 = None
        self.last = None
        self.com_y = 0.0

    def update(self, frame, recs):
        root = recs.get(self.v.root.guid)
        if root is None:
            return None
        s = State()
        s.t_sim = float(frame.simulation_time)
        if self.t0 is None:
            self.t0 = s.t_sim
        s.t = s.t_sim - self.t0
        s.p = np.array(root["position"], dtype=float)
        s.vel = np.array(root["velocity"], dtype=float)
        s.q = np.array(root["rotation"], dtype=float)
        s.w = np.array(root["angular_velocity"], dtype=float)
        if self.com_y:
            # velocity of the centre of mass (the root block sits below it): removes the rotation-induced part
            s.vel = s.vel + np.cross(s.w, qrot(s.q, Y) * self.com_y)
        rel = s.p - PLANET_C
        s.r = norm(rel)
        s.n = rel / s.r
        s.alt = s.r - R_SURF
        s.vr = float(np.dot(s.vel, s.n))
        s.vh = s.vel - s.vr * s.n
        s.vt = norm(s.vh)
        s.up = qrot(s.q, Y)
        s.g = gravity(s.r)
        s.k = drag_k(s.alt)
        if self.n_pad is None:
            self.n_pad = s.n.copy()
            self.alt0 = s.alt
        s.h = s.alt - self.alt0                      # height of root above its resting height on the pad
        c = float(np.clip(np.dot(s.n, self.n_pad), -1.0, 1.0))
        s.pad_dist = R_SURF * math.acos(c)          # great-circle distance on the surface
        hvec = self.n_pad - c * s.n                  # horizontal direction towards the pad
        s.pad_dir = unit(hvec)
        # fuel
        fuel = 0.0
        for b in self.v.tanks + self.v.boosters:
            row = recs.get(b.guid)
            if row is not None and int(row["fuel_valid"]):
                fuel += float(row["fuel"][0])
        s.fuel = fuel
        s.integrity = frame.machine.machine_integrity
        s.alive = frame.machine.alive_block_count
        # orbital elements (two-body)
        v2 = float(np.dot(s.vel, s.vel))
        s.energy = 0.5 * v2 - MU / s.r
        hvec3 = np.cross(rel, s.vel)
        s.hmag = norm(hvec3)
        e2 = max(0.0, 1.0 + 2.0 * s.energy * s.hmag ** 2 / MU ** 2)
        s.ecc = math.sqrt(e2)
        p_semi = s.hmag ** 2 / MU
        s.rp = p_semi / (1.0 + s.ecc)
        s.ra = p_semi / (1.0 - s.ecc) if s.ecc < 1.0 else float("inf")
        self.last = s
        return s
