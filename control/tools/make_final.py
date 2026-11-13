"""Write FINAL.draft.json (or FINAL.json with --final) for a run directory.
usage: python agent_control/tools/make_final.py <run_dir> "<summary paragraph>" [--final]
The estimate is produced by tools/score_estimate.py --json with the payload / launcher guid sets of the prepared bsg."""
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
from fsw.vehicle import parse_bsg, ID_DECOUPLER  # noqa: E402


def main():
    run = sys.argv[1]
    summary = sys.argv[2]
    final = "--final" in sys.argv[3:]
    bsg = glob.glob(os.path.join(run, "*_prepared.bsg"))[0]
    blocks = parse_bsg(bsg)
    dec = [b for b in blocks if b.type_id == ID_DECOUPLER][0]
    pidx = {b.index for b in blocks if b.pos[1] >= dec.pos[1] - 0.01 and abs(b.pos[0]) < 3 and abs(b.pos[2]) < 3}
    pay = [b.guid for b in blocks if b.index in pidx]
    traj = os.path.join(run, "trajectory.csv")
    if not os.path.exists(traj):
        traj = os.path.join(run, "telemetry.csv")
    cmd = [sys.executable, os.path.join(ROOT, "tools", "score_estimate.py"), traj, "--payload-guids", ",".join(pay),
           "--recovery-guids", blocks[0].guid, "--target", "0,0,0", "--json"]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    try:
        est = json.loads(out[out.index("{"):])
    except Exception:
        est = {"raw": out[-2000:]}
    decl = json.load(open(os.path.join(HERE, "..", "declaration.json")))
    est["declared"] = {"payload_dry_mass": decl["payload"]["initial_dry_mass"],
                       "vehicle_dry_mass": decl["recovery_vehicles"][0]["initial_dry_mass"],
                       "initial_fuel": decl["recovery_vehicles"][0]["initial_fuel"],
                       "blocks": decl["totals"]}
    rel = os.path.relpath(os.path.abspath(run), ROOT).replace("\\", "/")
    doc = {"run_dir": rel, "machine_name": "s02_orbiter", "bsg": "agent_control/machine.bsg",
           "control_dir": "agent_control", "summary": summary, "estimated": est}
    path = os.path.join(ROOT, "FINAL.json" if final else "FINAL.draft.json")
    json.dump(doc, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("wrote", path)
    print(json.dumps(est)[:600])


if __name__ == "__main__":
    main()
