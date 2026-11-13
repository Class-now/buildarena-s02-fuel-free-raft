import sys, numpy as np
sys.path.insert(0, "agent_control/tools")
from tele import *
d = load(sys.argv[1] + "/telemetry.csv")
t0, t1 = float(sys.argv[2]), float(sys.argv[3])
gs = list(d)
root = d[gs[0]]
r, vr, vt = radial(root)
t = root["t"]
acc = np.gradient(vr, t)
fu = {g: d[g]["fuel"] for g in gs if not np.isnan(d[g]["fuel"][0])}
for i in range(len(t)):
    if t0 <= t[i] <= t1:
        print(f"t={t[i]:6.2f} alt={r[i]-600:8.2f} vr={vr[i]:8.2f} vt={vt[i]:6.2f} a={acc[i]:7.2f} fuel=" + " ".join(f"{fu[g][i]:7.3f}" for g in fu if i < len(fu[g])))
