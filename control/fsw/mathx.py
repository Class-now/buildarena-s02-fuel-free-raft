"""Small vector / quaternion helpers (Unity convention: quaternion = (x, y, z, w), y up)."""
import math
import numpy as np

PLANET_C = np.array([0.0, -600.0, 0.0])
R_SURF = 600.0
MU = 8456800.0
G_CAP = 22.0


def norm(v):
    return float(math.sqrt(float(np.dot(v, v))))


def unit(v):
    n = norm(v)
    return v / n if n > 1e-12 else np.zeros(3)


def qrot(q, v):
    """Rotate vector v by quaternion q=(x,y,z,w)."""
    u = np.array([q[0], q[1], q[2]])
    w = q[3]
    return v + 2.0 * np.cross(u, np.cross(u, v) + w * v)


def qinv_rot(q, v):
    return qrot(np.array([-q[0], -q[1], -q[2], q[3]]), v)


def gravity(r):
    return min(G_CAP, MU / (r * r))


def drag_k(alt):
    """Linear atmospheric drag coefficient (1/s): a = -k v. Fitted from probe flights."""
    return max(0.0, 0.092 * (1.0 - alt / 450.0))


def clip(x, lo, hi):
    return lo if x < lo else hi if x > hi else x
