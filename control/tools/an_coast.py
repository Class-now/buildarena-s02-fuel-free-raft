"""Non-gravitational acceleration (specific force) in phases where the lift thrusters are not commanded.
usage: an_coast.py <run_dir> <phase> [alt_min]"""
import csv, sys, math
R, ph = sys.argv[1], sys.argv[2]; altmin = float(sys.argv[3]) if len(sys.argv) > 3 else 455.0
rows = [r for r in csv.DictReader(open(R + '/fsw_log.csv'))]
MU = 8456800.0
i = 0
while i + 25 < len(rows):
    a, b = rows[i], rows[i + 25]
    if a['phase'] == ph and b['phase'] == ph and float(a['alt']) > altmin and max(float(x['n_on']) for x in rows[i:i+25]) < 1:
        t0, t1 = float(a['t']), float(b['t'])
        alt = 0.5 * (float(a['alt']) + float(b['alt'])); r = 600 + alt
        vr = 0.5 * (float(a['vr']) + float(b['vr'])); vt = 0.5 * (float(a['vt']) + float(b['vt']))
        ar = (float(b['vr']) - float(a['vr'])) / (t1 - t0) + MU / r / r - vt * vt / r
        at = (float(b['vt']) - float(a['vt'])) / (t1 - t0) + vr * vt / r
        err = sum(float(x['err']) for x in rows[i:i+25]) / 25
        print(f"t={t0:6.1f} alt={alt:6.1f} spec.force radial={ar:+.2f} tangential={at:+.2f} |f|={math.hypot(ar,at):.2f} mean err={err:.1f}")
    i += 25
