"""Fan force table from a flight log: F_fan = m (dv/dt + g + k v) - n_thr*8.8 (vertical climb, all thrusters on).
usage: an_fan.py <run_dir> <true_mass> <n_lift_thrusters> [phase]"""
import csv, sys
R, m, nth = sys.argv[1], float(sys.argv[2]), int(sys.argv[3]); ph = sys.argv[4] if len(sys.argv) > 4 else "CLIMB"
rows = [r for r in csv.DictReader(open(R + '/fsw_log.csv')) if r['phase'] == ph]
MU = 8456800.0
i = 0
while i + 20 < len(rows):
    a, b = rows[i], rows[i + 20]
    t0, t1 = float(a['t']), float(b['t'])
    alt = 0.5 * (float(a['alt']) + float(b['alt'])); v = 0.5 * (float(a['vr']) + float(b['vr']))
    f = sum(float(x['f']) for x in rows[i:i + 20]) / 20
    acc = (float(b['vr']) - float(a['vr'])) / (t1 - t0)
    g = min(22.0, MU / (600 + alt) ** 2); k = 0.092 * max(0, 1 - alt / 450)
    Ftot = m * (acc + g + k * v)
    if f > 1.02 and alt < 255:
        slider = min(2.0, (f - 1.0) * nth * 8.3 / (8 * 47.0 * (1 - alt / 255.0)))
        ffan = Ftot - nth * 8.8
        print(f"t={t0:5.1f} alt={alt:6.1f} v={v:5.1f} acc={acc:6.2f} slider={slider:.2f} F_fan={ffan:6.1f} per_unit_slider={ffan/slider:6.1f}")
    i += 20
