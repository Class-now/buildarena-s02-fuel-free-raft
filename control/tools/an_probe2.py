import sys, numpy as np
sys.path.insert(0, "agent_control/tools")
from tele import *
d = load(sys.argv[1] + "/telemetry.csv")
step = int(sys.argv[2]) if len(sys.argv) > 2 else 10
gs = list(d)
root = d[gs[0]]
r, vr, vt = radial(root)
t = root["t"]
v = root["vel"]
sp = np.linalg.norm(v, axis=1)
a = np.gradient(v, t, axis=0)
rel = root["pos"] - C
n = rel / r[:, None]
g = np.minimum(22.0, MU / r**2)
# non-gravitational acceleration
ang = a + g[:, None] * n
vhat = v / np.maximum(sp, 1e-6)[:, None]
a_along = np.sum(ang * vhat, axis=1)
# body up axis (unity +Y of root) from quaternion
q = root["q"]
x, y, z, w = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
up = np.stack([2*(x*y - w*z), 1 - 2*(x*x + z*z), 2*(y*z + w*x)], axis=1)
tilt = np.degrees(np.arccos(np.clip(np.sum(up * n, axis=1), -1, 1)))
fu = [d[g_]["fuel"] for g_ in gs if not np.isnan(d[g_]["fuel"][0])]
for i in range(0, len(t), step):
    print(f"t={t[i]:6.2f} alt={r[i]-600:8.1f} vr={vr[i]:8.2f} vt={vt[i]:6.2f} |ang|={np.linalg.norm(ang[i]):6.2f} a_along={a_along[i]:7.3f} k={-a_along[i]/max(sp[i],1e-6):7.4f} tilt={tilt[i]:5.1f} fuel={fu[0][i] if i < len(fu[0]) else -1:7.2f} integ={root['integ'][i]:.2f}")
