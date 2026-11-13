"""Offline 2-D (polar) point-mass model of the LONE ORB flight physics, fitted to telemetry.
Vectorised over a batch dimension so that finite-difference gradients are cheap."""
import numpy as np

MU = 8456800.0
R0 = 600.0
GCAP = 22.0
F2 = 423.0          # booster force at f=2 (static / retro)
PA, PB, PFLOOR = 0.00185, 9.36e-5, 0.155
FUEL_RATE = 2.0     # units/s per booster at f=2


def grav(r):
    return np.minimum(GCAP, MU / (r * r))


def dragk(r):
    return np.maximum(0.0, 0.092 * (1.0 - (r - R0) / 450.0))


def phi(v_ax):
    v = np.maximum(v_ax, 0.0)
    return np.maximum(PFLOOR, 1.0 - PA * v - PB * v * v)


def deriv(y, beta, tau, P):
    """y: (..., 5) = r, th, vr, vt, fuel. beta: thrust angle from local vertical towards prograde. tau: duty 0..1."""
    r, th, vr, vt, fuel = (y[..., i] for i in range(5))
    m = P["m_dry"] + P["rho"] * fuel
    vax = vr * np.cos(beta) + vt * np.sin(beta)
    on = (fuel > 0.0) * tau
    aT = on * P["N"] * F2 * phi(vax) / m
    k = dragk(r)
    d = np.empty_like(y)
    d[..., 0] = vr
    d[..., 1] = vt / r
    d[..., 2] = vt * vt / r - grav(r) + aT * np.cos(beta) - k * vr
    d[..., 3] = -vr * vt / r + aT * np.sin(beta) - k * vt
    d[..., 4] = -on * P["N"] * FUEL_RATE
    return d


def rk4(y, beta, tau, P, dt):
    k1 = deriv(y, beta, tau, P)
    k2 = deriv(y + 0.5 * dt * k1, beta, tau, P)
    k3 = deriv(y + 0.5 * dt * k2, beta, tau, P)
    k4 = deriv(y + dt * k3, beta, tau, P)
    return y + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)


def apsides(r, vr, vt):
    e = 0.5 * (vr * vr + vt * vt) - MU / r
    h = r * vt
    ecc = np.sqrt(np.maximum(0.0, 1.0 + 2.0 * e * h * h / MU ** 2))
    p = h * h / MU
    return p / (1.0 + ecc), p / np.maximum(1e-9, 1.0 - ecc)
