import sys, numpy as np
sys.path.insert(0, "agent_control/tools")
from tele import *
d = load(sys.argv[1] + "/telemetry.csv")
t0, t1, step = float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
gs = list(d)
root = d[gs[0]]
t = root["t"]; av = root["av"]
q = root["q"]; x, y, z, w = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
up = np.stack([2*(x*y - w*z), 1 - 2*(x*x + z*z), 2*(y*z + w*x)], axis=1)
r, vr, vt = radial(root)
for i in range(len(t)):
    if t0 <= t[i] <= t1 and i % step == 0:
        print(f"t={t[i]:6.2f} alt={r[i]-600:6.1f} av=({av[i,0]:7.3f},{av[i,1]:7.3f},{av[i,2]:7.3f}) up=({up[i,0]:6.3f},{up[i,1]:6.3f},{up[i,2]:6.3f})")
