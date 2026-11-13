"""Hardware abstraction: parse the prepared .bsg, map roles, read telemetry, send commands."""
import os
import xml.etree.ElementTree as ET
import numpy as np

from .mathx import qrot

ID_START, ID_DECOUPLER, ID_GRABBER, ID_BOOSTER, ID_RW = 0, 4, 27, 90, 101
ID_TANK_S, ID_TANK_B = 92, 99
ID_RCS = 91
ID_FLY = 14

F1 = 211.5          # booster force per unit fthrust (static / retrograde)
PHI_A, PHI_B = 0.00185, 9.36e-5   # thrust loss vs axial speed (at f=2): 1 - a u - b u^2, u = 2 v_ax / f
PHI_FLOOR = 0.155


def phi(v_ax, f):
    """Thrust factor for axial speed v_ax (velocity component along thrust direction) at slider f."""
    if v_ax <= 0.0 or f <= 1e-6:
        return 1.0
    u = 2.0 * v_ax / f
    return max(PHI_FLOOR, 1.0 - PHI_A * u - PHI_B * u * u)


def booster_force(f, v_ax):
    return F1 * f * phi(v_ax, f)


def throttle_for_force(force_per_booster, v_ax):
    """Smallest slider f in [0,2] giving the requested force per booster (bisection; monotonic in f)."""
    if force_per_booster <= 0.0:
        return 0.0
    if booster_force(2.0, v_ax) <= force_per_booster:
        return 2.0
    lo, hi = 0.0, 2.0
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        if booster_force(mid, v_ax) < force_per_booster:
            lo = mid
        else:
            hi = mid
    return hi


class Block:
    __slots__ = ("index", "type_id", "guid", "pos", "quat")

    def __init__(self, index, type_id, guid, pos, quat):
        self.index, self.type_id, self.guid, self.pos, self.quat = index, type_id, guid, pos, quat


def parse_bsg(path):
    root = ET.parse(path).getroot()
    blocks = []
    for i, b in enumerate(root.find("Blocks").findall("Block")):
        tr = b.find("Transform")
        p = tr.find("Position")
        r = tr.find("Rotation")
        blocks.append(Block(i, int(b.get("id")), b.get("guid").lower(),
                            np.array([float(p.get("x")), float(p.get("y")), float(p.get("z"))]),
                            np.array([float(r.get("x")), float(r.get("y")), float(r.get("z")), float(r.get("w"))])))
    return blocks


class Vehicle:
    def __init__(self, client, bsg_path=None):
        self.client = client
        self.blocks = parse_bsg(bsg_path or os.environ["BUILDARENA_MACHINE_BSG"])
        self.by_guid = {b.guid: b for b in self.blocks}
        self.root = next(b for b in self.blocks if b.type_id == ID_START)
        self.boosters = [b for b in self.blocks if b.type_id == ID_BOOSTER]
        self.wheels = [b for b in self.blocks if b.type_id == ID_RW]
        self.grabbers = [b for b in self.blocks if b.type_id == ID_GRABBER]
        self.decouplers = [b for b in self.blocks if b.type_id == ID_DECOUPLER]
        self.tanks = [b for b in self.blocks if b.type_id in (ID_TANK_S, ID_TANK_B)]
        self.rcs = [b for b in self.blocks if b.type_id == ID_RCS]
        self.fans = [b for b in self.blocks if b.type_id == ID_FLY]
        # RCS nozzle axis (local +Y) in the machine frame
        self.rcs_axis = {b.guid: qrot(b.quat, np.array([0.0, 1.0, 0.0])) for b in self.rcs}
        # measured: LeftKey pushes the vehicle towards the thruster's local +Y, RightKey towards -Y.
        # rcs command convention used by send(): +1 = push towards body +Y (up), -1 = towards body -Y.
        self.rcs_lift = [b for b in self.rcs if abs(self.rcs_axis[b.guid][1]) > 0.9]
        self.rcs_quads = self._quads()
        # tip thrusters (horizontal nozzle axis): roll torque coefficient about body +Y per unit command
        self.rcs_tip = []
        for b in self.rcs:
            a = self.rcs_axis[b.guid]
            if abs(a[1]) < 0.1:
                px, pz = b.pos[0] - self.root.pos[0], b.pos[2] - self.root.pos[2]
                self.rcs_tip.append((b, pz * a[0] - px * a[2], a))
        # wheel axis in the machine (= root body) frame
        self.wheel_axis = {w.guid: qrot(w.quat, np.array([0.0, 0.0, 1.0])) for w in self.wheels}
        self.idx = {}
        for c in client.channels:
            self.idx[(c.block_guid.lower(), c.name)] = c.index
        for s in client.sliders:
            self.idx[(s.block_guid.lower(), s.name)] = s.index
        self.tindex = {i: g.lower() for i, g in client._block_guids.items()}
        self.gindex = {g: i for i, g in self.tindex.items()}

    def _quads(self):
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

    # ---------------- telemetry ----------------
    def read(self, frame):
        """Return dict guid -> record row (numpy void) for valid targets."""
        out = {}
        recs = frame.records
        for row in recs:
            if int(row["valid"]) == 0:
                continue
            g = self.tindex.get(int(row["target_index"]))
            if g is not None:
                out[g] = row
        return out

    # ---------------- commands ----------------
    def send(self, thr=None, wheel=None, damper=0.0, keys=(), rcs=None, sliders=(), fan=0.0):
        """thr: dict guid->f (0..2). wheel: dict guid->signed speed (+ = RightKey, - = LeftKey).
        keys: iterable of (guid, channel_name) to hold this tick. Everything is resent every tick."""
        rec = []
        thr = thr or {}
        wheel = wheel or {}
        for b in self.boosters:
            f = float(thr.get(b.guid, 0.0))
            f = 0.0 if f < 0.02 else min(2.0, f)
            rec.append((self.idx[(b.guid, "fthrust")], f))
            rec.append((self.idx[(b.guid, "ThrustKey")], 1.0 if f > 0.0 else 0.0))
        for w in self.wheels:
            s = float(wheel.get(w.guid, 0.0))
            a = min(2.0, abs(s))
            rec.append((self.idx[(w.guid, "speed")], a))
            rec.append((self.idx[(w.guid, "damper")], float(damper)))
            rec.append((self.idx[(w.guid, "RightKey")], 1.0 if s > 1e-6 else 0.0))
            rec.append((self.idx[(w.guid, "LeftKey")], 1.0 if s < -1e-6 else 0.0))
        if self.rcs:
            rcs = rcs or {}
            for b in self.rcs:
                v = rcs.get(b.guid, 0)          # +1: push vehicle to body +Y, -1: to body -Y
                if self.rcs_axis[b.guid][1] < -0.5:      # lift thruster mounted with its local +Y pointing down
                    v = -v                               # (tip thrusters have a horizontal axis: never flipped)
                if v == 0 and getattr(self, "rcs_idle_both", False) and not getattr(self, "rcs_release", False):
                    # both nozzles on: zero net force, and the block's own auto-stabilisation stays overridden
                    rec.append((self.idx[(b.guid, "LeftKey")], 1.0))
                    rec.append((self.idx[(b.guid, "RightKey")], 1.0))
                else:
                    rec.append((self.idx[(b.guid, "LeftKey")], 1.0 if v > 0 else 0.0))
                    rec.append((self.idx[(b.guid, "RightKey")], 1.0 if v < 0 else 0.0))
        for b in self.fans:
            sp = min(2.0, max(0.0, float(fan)))
            rec.append((self.idx[(b.guid, "speed")], sp))
            rec.append((self.idx[(b.guid, "FlyKey")], 1.0 if sp > 0.02 else 0.0))
        for g, name in keys:
            rec.append((self.idx[(g, name)], 1.0))
        for g, name, val in sliders:
            rec.append((self.idx[(g, name)], float(val)))
        return self.client.send_indexes(rec)
