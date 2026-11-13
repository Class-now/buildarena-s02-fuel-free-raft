"""S02 flight controller entry point (run by besiege_cli). MISSION env selects the profile."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fsw.core import Flight  # noqa: E402


def main():
    default_cfg = json.loads((HERE / "mission.json").read_text())["config"]
    cfg = json.loads((HERE / os.environ.get("CONFIG", default_cfg)).read_text())
    for k, v in json.loads(os.environ.get("CFG_OVERRIDE", "{}")).items():
        cfg[k] = v
    mission = os.environ.get("MISSION", "orbit")
    fl = Flight(cfg)
    try:
        fl.start()
        if mission == "hop":
            from fsw.mission_hop import run
        elif mission == "ground":
            from fsw.mission_ground import run
        elif mission == "fly":
            from fsw.mission_fly import run
        elif mission == "rcs":
            from fsw.mission_rcs import run
        elif mission == "massrig":
            from fsw.mission_massrig import run
        else:
            from fsw.mission_orbit import run
        run(fl)
    finally:
        fl.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
