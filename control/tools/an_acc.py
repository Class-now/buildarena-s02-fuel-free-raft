"""Thrust acceleration from the flight log (2-D orbital-plane kinematics), per phase, where engines are at a given level.
usage: an_acc.py <run_dir> [alt_min]   -> prints mean thrust accel, commanded level f and n_on for windows of 1 s"""
import csv, sys, math
R = sys.argv[1]; altmin = float(sys.argv[2]) if len(sys.argv) > 2 else 260.0
rows = list(csv.DictReader(open(R + '/fsw_log.csv')))
MU = 8456800.0
out = []
i = 0
while i + 25 < len(rows):
    a, b = rows[i], rows[i + 25]
    t0, t1 = float(a['t']), float(b['t'])
    alt = 0.5 * (float(a['alt']) + float(b['alt']))
    if alt > altmin and a['phase'] == b['phase'] and t1 > t0:
        r = 600 + alt; vr = 0.5 * (float(a['vr']) + float(b['vr'])); vt = 0.5 * (float(a['vt']) + float(b['vt']))
        ar = (float(b['vr']) - float(a['vr'])) / (t1 - t0) + MU / r / r - vt * vt / r
        at = (float(b['vt']) - float(a['vt'])) / (t1 - t0) + vr * vt / r
        k = 0.092 * max(0.0, 1 - alt / 450.0)
        ar += k * vr; at += k * vt
        seg = rows[i:i + 25]
        f = sum(float(x['f']) for x in seg) / 25; n = sum(float(x['n_on']) for x in seg) / 25
        out.append((t0, a['phase'], alt, math.hypot(ar, at), f, n))
    i += 25
for o in out:
    if o[5] > 1:
        print(f"t={o[0]:6.1f} {o[1]:7s} alt={o[2]:6.1f} thrust_acc={o[3]:6.2f} f={o[4]:.2f} n_on={o[5]:5.1f} acc_per_thruster={o[3]/o[5]:.4f}")
