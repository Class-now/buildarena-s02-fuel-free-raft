"""Probe 2: throttle schedule with per-tick resend. PROBE_PLAN="dur:thr,dur:thr,..." (thr in slider units, 0 = off)."""
import json, os
from pathlib import Path
from controller_sdk import ControllerClient

PLAN = [tuple(float(x) for x in seg.split(":")) for seg in os.environ.get("PROBE_PLAN", "1:0,5:2,60:0").split(",")]

def main():
    client = ControllerClient.from_environment()
    client.arm()
    try:
        first = client.wait_until_running(timeout=60)
        client.load_block_table()
        thr_sl = [s for s in client.sliders if s.name == "fthrust"]
        thr_ch = [c for c in client.channels if c.name == "ThrustKey"]
        t0 = first.simulation_time
        total = sum(d for d, _ in PLAN)
        last = None
        while True:
            fr = client.next_sample(timeout=5.0)
            t = fr.simulation_time - t0
            if t > total:
                break
            acc = 0.0
            thr = 0.0
            for d, v in PLAN:
                if t < acc + d:
                    thr = v
                    break
                acc += d
            if thr != last:
                print(f"t={t:.2f} thr={thr}", flush=True)
                last = thr
            client.send_sliders([(s.block_guid, "fthrust", max(thr, 0.0)) for s in thr_sl])
            client.send_channels(channels=[(c.block_guid, "ThrustKey", 1.0 if thr > 0 else 0.0) for c in thr_ch])
    finally:
        client.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
