import sys, numpy as np
sys.path.insert(0, "agent_control/tools")
from tele import *
d = load(sys.argv[1] + "/telemetry.csv")
t0, t1, step = float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
idxs = [int(x) for x in sys.argv[5].split(",")]
gs = list(d)
root = d[gs[0]]
t = root["t"]; n = len(t)
def rot(q, v):
    x, y, z, w = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    u = np.stack([x, y, z], axis=1)
    return v + 2 * np.cross(u, np.cross(u, v) + w[:, None] * v)
def inv_rot(q, v):
    qc = q.copy(); qc[:, :3] *= -1
    return rot(qc, v)
bav = inv_rot(root["q"], root["av"])  # body rates in body frame
for i in range(n):
    if t0 <= t[i] <= t1 and i % step == 0:
        s = f"t={t[i]:6.2f} body_av=({bav[i,0]:7.3f},{bav[i,1]:7.3f},{bav[i,2]:7.3f})"
        for j in idxs:
            w = d[gs[j]]
            m = min(len(w["t"]), n)
            if i < m:
                rel = inv_rot(root["q"][i:i+1], (w["av"][i] - root["av"][i])[None, :])[0]
                s += f" | w{j} rel=({rel[0]:8.2f},{rel[1]:8.2f},{rel[2]:8.2f})"
        print(s)
