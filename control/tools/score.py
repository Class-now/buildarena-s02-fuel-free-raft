"""Run tools/score_estimate.py for a run directory, deriving payload / vehicle guid sets from the prepared bsg.
usage: score.py <run_dir> [payload_bsg_indices comma separated]  (default: decoupler(s) and everything above)"""
import sys, glob, subprocess, json, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fsw.vehicle import parse_bsg, ID_DECOUPLER
run = sys.argv[1]
bsg = glob.glob(os.path.join(run, "*_prepared.bsg"))[0]
blocks = parse_bsg(bsg)
if len(sys.argv) > 2:
    pidx = {int(x) for x in sys.argv[2].split(",")}
else:
    dec = [b for b in blocks if b.type_id == ID_DECOUPLER][0]
    pidx = {b.index for b in blocks if b.pos[1] >= dec.pos[1] - 0.01 and abs(b.pos[0]) < 3 and abs(b.pos[2]) < 3}
pay = [b.guid for b in blocks if b.index in pidx]
veh = [b.guid for b in blocks if b.index not in pidx]
root = blocks[0]
cmd = [sys.executable, os.path.join(os.path.dirname(__file__), "..", "..", "tools", "score_estimate.py"), os.path.join(run, "telemetry.csv"),
       "--payload-guids", ",".join(pay), "--recovery-guids", root.guid, "--target", "0,0,0"] + sys.argv[3:]
print("payload idx", sorted(pidx), "vehicle blocks", len(veh))
subprocess.run(cmd)
