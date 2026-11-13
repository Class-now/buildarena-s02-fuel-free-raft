import sys, numpy as np
sys.path.insert(0, "agent_control/tools")
from tele import *
d = load(sys.argv[1] + "/telemetry.csv")
gs = list(d)
root = d[gs[0]]
tank = d[gs[1]]
r, vr, vt = radial(root)
t = root["t"]
acc = np.gradient(vr, t)
print("guids", len(gs))
for i in range(0, len(t), max(1, len(t)//70)):
    print(f"t={t[i]:6.2f} alt={r[i]-600:8.2f} vr={vr[i]:8.2f} vt={vt[i]:6.2f} a={acc[i]:7.2f} fuel={tank['fuel'][i]:7.2f} integ={root['integ'][i]:.3f} y={root['pos'][i,1]:.2f}")
for g in gs:
    print(g, "fuel0", d[g]["fuel"][0], "fuelEnd", d[g]["fuel"][-1], "pos0", d[g]["pos"][0])
