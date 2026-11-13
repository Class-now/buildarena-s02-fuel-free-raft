import sys, numpy as np
sys.path.insert(0, "agent_control/tools")
from tele import *
d = load(sys.argv[1] + "/telemetry.csv")
gs = list(d); root = d[gs[0]]; t = root["t"]
def rot(q, v):
    x, y, z, w = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    u = np.stack([x, y, z], axis=1)
    return v + 2 * np.cross(u, np.cross(u, v) + w[:, None] * v)
qc = root["q"].copy(); qc[:, :3] *= -1
bav = rot(qc, root["av"])
t0, t1 = float(sys.argv[2]), float(sys.argv[3])
for i in range(len(t)):
    if t0 <= t[i] <= t1:
        print(f"{t[i]:6.2f} {bav[i,0]:7.3f} {bav[i,1]:7.3f} {bav[i,2]:7.3f}")
