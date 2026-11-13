"""1-D check of the fly-back cruise lateral loop with a rate-limited tilt (surface distance units for the pad offset).
usage: cruise_loop.py kp kd vmax amax tilt_max_deg slew_deg [v0 d0]"""
import math, sys
kp, kd, vmax, amax, tmax, slew = [float(x) for x in sys.argv[1:7]]
v = float(sys.argv[7]) if len(sys.argv) > 7 else 65.0       # real speed away from the pad
d = float(sys.argv[8]) if len(sys.argv) > 8 else 290.0      # surface distance (pad behind)
g, scale, dt, t = 7.0, 600.0 / 1100.0, 0.04, 0.0
tilt = math.radians(tmax)          # start already braking
tau = 0.5
tilt_cmd_f = tilt
exit_t = None; dmax = d; hist = []
while t < 400:
    v_des = -min(kp * abs(d), vmax) * (1 if d > 0 else -1)   # towards the pad (negative = back)
    a = kd * (v_des - v)
    a = max(-amax, min(amax, a))
    cmd = math.atan2(a, g)
    cmd = max(-math.radians(tmax), min(math.radians(tmax), cmd))
    # slew limiter on the command, then first-order attitude lag
    step = math.radians(slew) * dt
    tilt_cmd_f += max(-step, min(step, cmd - tilt_cmd_f))
    tilt += (tilt_cmd_f - tilt) * dt / tau
    v += g * math.tan(tilt) * dt
    d += v * scale * dt
    t += dt
    dmax = max(dmax, abs(d))
    if exit_t is None and abs(d) < 10 and abs(v) < 2:
        exit_t = t
    if int(t / dt) % 500 == 0: hist.append((round(t), round(d), round(v, 1)))
print(f"exit at t={exit_t}, max |d|={dmax:.0f}; samples (t, d, v): {hist[:14]}")
