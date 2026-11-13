"""Reaction-wheel attitude controller.

Measured wheel behaviour (Reaction Steering Block, damper slider = 0):
  LeftKey  -> body angular acceleration NEGATIVE about the wheel axis,
  RightKey -> POSITIVE; magnitude ~ G * (speed - S0) for speed >= ~0.45, almost nothing below ~0.35,
  with ~0.1 s spin-up lag and a momentum kick when the spin direction is reversed.
  G depends on the vehicle inertia about that axis (calibrated per configuration).

To get a linear, lag-free, dead-zone-free actuator, axes that have two wheels with opposite
axes are driven as a *biased pair*: both wheels always spin "RightKey" (their torques oppose),
and the net torque is set by the speed difference:  alpha = G * (s_plus - s_minus).
Axes with a single wheel fall back to a dead-band single-wheel law.
The outer loop is a rate-limited PD (+ small integral) on the thrust-axis pointing error.
"""
import math
import numpy as np

from .mathx import qinv_rot, clip

S0 = 0.35        # wheel speed dead zone
S_MIN = 0.45     # lowest speed in the linear region
S_MAX = 2.0
BIAS = 0.75


class PairChannel:
    def __init__(self, plus_guid, minus_guid, gain):
        self.plus, self.minus, self.gain = plus_guid, minus_guid, gain

    def actuate(self, alpha, out):
        u = alpha / self.gain                       # required speed difference
        a = abs(u)
        hi, lo = BIAS + 0.5 * a, BIAS - 0.5 * a
        if lo < S_MIN:
            lo, hi = S_MIN, S_MIN + a
        if hi > S_MAX:
            hi, lo = S_MAX, 0.0                     # saturate: release the opposing wheel
        sp, sm = (hi, lo) if u >= 0 else (lo, hi)
        out[self.plus] = sp                         # + = RightKey on both wheels
        out[self.minus] = sm


class SingleChannel:
    def __init__(self, guid, sign, gain):
        self.guid, self.sign, self.gain = guid, sign, gain   # sign: wheel axis = sign * body axis

    def actuate(self, alpha, out):
        a = abs(alpha)
        if a < 0.3 * self.gain * (S_MIN - S0):
            out[self.guid] = 0.0
            return
        s = min(S_MAX, max(S_MIN, S0 + a / self.gain))
        out[self.guid] = s * self.sign * (1.0 if alpha > 0 else -1.0)


class AttitudeController:
    def __init__(self, vehicle, gains, kp=2.0, kd=4.0, ki=0.0, rate_max=0.7, roll_kd=3.0):
        """gains: dict axis-name -> rad/s^2 per unit speed difference for 'x', 'z', 'y'."""
        self.kp, self.kd, self.ki, self.rate_max, self.roll_kd = kp, kd, ki, rate_max, roll_kd
        self.ch = {}
        axes = {"x": np.array([1.0, 0, 0]), "y": np.array([0, 1.0, 0]), "z": np.array([0, 0, 1.0])}
        for name, e in axes.items():
            plus = [w for w in vehicle.wheels if float(np.dot(vehicle.wheel_axis[w.guid], e)) > 0.9]
            minus = [w for w in vehicle.wheels if float(np.dot(vehicle.wheel_axis[w.guid], e)) < -0.9]
            if plus and minus:
                self.ch[name] = PairChannel(plus[0].guid, minus[0].guid, gains[name])
            elif plus:
                self.ch[name] = SingleChannel(plus[0].guid, 1.0, gains[name])
            elif minus:
                self.ch[name] = SingleChannel(minus[0].guid, -1.0, gains[name])
        self.err_deg = 0.0
        self.int_max = 0.6
        self.damp_ff = 0.0
        self.damp_ratio = 0.0
        self.rate_err = (0.0, 0.0)
        self.int_x = self.int_z = 0.0
        self.t_prev = None

    def damp(self, name):
        """Rotational damping of the vehicle about this axis [1/s]: the wheels behave like rate servos, so the
        damping is proportional to the wheel gain (damp_ratio = damping / gain, measured in flight)."""
        ch = self.ch.get(name)
        return self.damp_ff + (self.damp_ratio * ch.gain if ch is not None else 0.0)

    def set_gains(self, gains):
        for k, v in gains.items():
            if k in self.ch:
                self.ch[k].gain = v

    def update(self, q, w_world, d_world, lead=0.0, t=None):
        """q: root quaternion, w_world: angular velocity (world), d_world: desired thrust (+Y body) direction.
        Returns dict wheel guid -> signed speed (+ = RightKey, - = LeftKey)."""
        d_b = qinv_rot(q, d_world)
        w_b = qinv_rot(q, w_world)
        ex, ez = d_b[2], -d_b[0]              # y_hat x d_b
        s = math.hypot(ex, ez)
        theta = math.atan2(s, d_b[1])
        self.err_deg = math.degrees(theta)
        if s > 1e-9:
            ex, ez = ex / s * theta, ez / s * theta
        else:
            ex, ez = (theta, 0.0) if d_b[1] < 0 else (0.0, 0.0)
        ex -= lead * w_b[0]
        ez -= lead * w_b[2]
        dt = 0.04 if (t is None or self.t_prev is None) else clip(t - self.t_prev, 0.0, 0.2)
        self.t_prev = t
        if self.ki > 0.0 and theta < 0.35:
            self.int_x = clip(self.int_x + ex * dt, -self.int_max, self.int_max)
            self.int_z = clip(self.int_z + ez * dt, -self.int_max, self.int_max)
        elif theta > 0.5:
            self.int_x = self.int_z = 0.0
        # rate command, limited in magnitude (direction preserved); damp_ff cancels the vehicle's rotational damping
        rx, rz = self.kp * ex, self.kp * ez
        rm = math.hypot(rx, rz)
        if rm > self.rate_max:
            rx, rz = rx * self.rate_max / rm, rz * self.rate_max / rm
        self.rate_err = (rx - w_b[0], rz - w_b[2])       # used by the thruster-couple assist
        cmd = {
            "x": self.kd * (rx - w_b[0]) + self.damp(("x")) * rx + self.ki * self.int_x,
            "z": self.kd * (rz - w_b[2]) + self.damp(("z")) * rz + self.ki * self.int_z,
            "y": -self.roll_kd * w_b[1],
        }
        out = {}
        for name, ch in self.ch.items():
            ch.actuate(cmd[name], out)
        return out
