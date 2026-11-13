"""One-command reproduction of the final S02 mission (launch -> orbit -> payload release -> return -> landing).

    uv run python agent_control/reproduce.py            (from the workspace root)

Loads agent_control/machine.bsg, enters the LONE ORB sandbox (re-loaded for a clean scene), starts the simulation and
runs agent_control/controller.py until the payload has completed more than three revolutions and the launcher has been
at rest on the pad. No human input is needed. Outputs go to datacache/control_experiments/<experiment>/runs/<run>/
(telemetry.csv is the trajectory; it is also copied to trajectory.csv in the same folder).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", default="s02_final")
    ap.add_argument("--bsg", default=str(HERE / "machine.bsg"))
    ap.add_argument("--controller-timeout", type=float, default=10800.0, help="wall-clock seconds")
    ap.add_argument("--hold", type=float, default=5.0, help="simulation seconds to keep running after the controller ends")
    args = ap.parse_args()

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"      # the toolkit prints non-ASCII characters; legacy consoles cannot encode them
    env.pop("PYTHONUTF8", None)             # (PYTHONUTF8=1 breaks the toolkit's process listing on some locales)
    env["MISSION"] = "orbit"
    sel = json.loads((HERE / "mission.json").read_text())       # which configuration / run mode is the final design
    env.setdefault("CONFIG", sel["config"])
    cmd = ["uv", "run", "python", "-m", "besiege_cli", "run",
           "--bsg", args.bsg,
           "--controller", str(HERE / "controller.py"),
           "--sandbox", "LONE ORB",
           "--reload-sandbox",
           "--telemetry-hz", "25",
           "--controller-timeout", str(args.controller_timeout),
           "--post-completion-hold", str(args.hold),
           "--experiment", args.experiment]
    if sel.get("prestart", False):
        # the controller must hold the fuel-free thrusters from the very first physics frame
        cmd += ["--controller-prestart", "--pre-controller-hold", "0"]
    print("running:", " ".join(cmd), flush=True)
    rc = subprocess.call(cmd, cwd=str(ROOT / "control"), env=env)
    runs = sorted((ROOT / "datacache" / "control_experiments" / args.experiment / "runs").glob("*/"))
    if runs:
        run = runs[-1]
        tele = run / "telemetry.csv"
        if tele.exists():
            shutil.copyfile(tele, run / "trajectory.csv")
        print(f"run directory: {run}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
