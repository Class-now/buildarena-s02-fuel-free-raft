import sys, numpy as np
sys.path.insert(0, "agent_control/tools")
from tele import *
d = load(sys.argv[1] + "/telemetry.csv")
t0, t1, step = float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
gs = list(d)
root = d[gs[0]]
r, vr, vt = radial(root)
t = root["t"]; v = root["vel"]; sp = np.linalg.norm(v, axis=1)
a = np.gradient(v, t, axis=0)
rel = root["pos"] - C; n = rel / r[:, None]
g = np.minimum(22.0, MU / r**2)
ang = a + g[:, None] * n
alt = r - 600
k = np.clip(0.092 * (1 - alt / 450), 0, None)
thr = ang + k[:, None] * v
q = root["q"]; x, y, z, w = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
up = np.stack([2*(x*y - w*z), 1 - 2*(x*x + z*z), 2*(y*z + w*x)], axis=1)
tm = np.linalg.norm(thr, axis=1)
along = np.sum(thr * up, axis=1)
vup = np.sum(v * up, axis=1)
for i in range(len(t)):
    if t0 <= t[i] <= t1 and i % step == 0:
        print(f"t={t[i]:6.2f} alt={alt[i]:7.1f} sp={sp[i]:6.1f} v_axial={vup[i]:6.1f} |thr|={tm[i]:6.2f} thr_axial={along[i]:6.2f} offaxis={np.degrees(np.arccos(np.clip(along[i]/max(tm[i],1e-9),-1,1))):5.1f}")
