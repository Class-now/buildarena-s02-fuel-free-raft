import sys, numpy as np
sys.path.insert(0, "agent_control/tools")
from tele import *
d = load(sys.argv[1] + "/telemetry.csv")
t0, t1, step = float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
gs = list(d)
root = d[gs[0]]
t = root["t"]
fu = [d[g_]["fuel"] for g_ in gs if not np.isnan(d[g_]["fuel"][0])]
tot = sum(f[:len(t)] for f in fu)
rate = -np.gradient(tot, t)
for i in range(len(t)):
    if t0 <= t[i] <= t1 and i % step == 0:
        print(f"t={t[i]:6.2f} fuel_tot={tot[i]:8.3f} rate={rate[i]:6.3f} " + " ".join(f"{f[i]:.3f}" for f in fu))
