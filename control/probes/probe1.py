"""Probe 1: vertical burn then coast; learn thrust, fuel burn, gravity, drag, slider ranges."""
import json, os, sys, time, math
from pathlib import Path
from controller_sdk import ControllerClient, targets_by_guid

BURN = float(os.environ.get("PROBE_BURN", "6"))
COAST = float(os.environ.get("PROBE_COAST", "40"))
THR = float(os.environ.get("PROBE_THR", "1.0"))

def main():
    client = ControllerClient.from_environment()
    run_dir = Path(os.environ["BUILDARENA_RUN_DIR"])
    log = open(run_dir / "probe_log.jsonl", "w")
    client.arm()
    try:
        first = client.wait_until_running(timeout=60)
        chans = client.load_block_table()
        info = {
            "channels": [(c.index, c.block_guid, c.name, c.keys, c.local_index) for c in client.channels],
            "sliders": [(s.index, s.block_guid, s.name, s.minimum, s.maximum, s.default, s.initial_value, s.local_index) for s in client.sliders],
            "guids": client._block_guids,
            "env": {k: v for k, v in os.environ.items() if k.startswith("BUILDARENA")},
        }
        (run_dir / "probe_info.json").write_text(json.dumps(info, indent=1, default=str))
        print(json.dumps(info, indent=1, default=str), flush=True)
        thr_sl = [s for s in client.sliders if s.name == "fthrust"]
        thr_ch = [c for c in client.channels if c.name == "ThrustKey"]
        t0 = first.simulation_time
        client.send_sliders([(s.block_guid, "fthrust", s.minimum + THR * (s.maximum - s.minimum)) for s in thr_sl])
        burning = None
        while True:
            fr = client.next_sample(timeout=5.0)
            t = fr.simulation_time - t0
            tg = targets_by_guid(fr, block_guids=client._block_guids)
            log.write(json.dumps({"t": fr.simulation_time, "m": fr.machine.as_dict(), "tg": tg}) + "\n")
            want = 1.0 <= t < 1.0 + BURN
            if want != burning:
                burning = want
                client.send_channels(channels=[(c.block_guid, "ThrustKey", 1.0 if want else 0.0) for c in thr_ch])
                print(f"t={t:.2f} burn={want}", flush=True)
            if t > 1.0 + BURN + COAST:
                break
    finally:
        log.close()
        client.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
