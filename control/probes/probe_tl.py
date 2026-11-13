"""Timeline probe. PROBE_TL = JSON list of [t0, t1, bsg_index, name, value]; name 'fthrust'/'speed'/'damper' are sliders, else key channels.
Resends every tick (commands expire after ~1 s)."""
import json, os
from controller_sdk import ControllerClient

TL = json.loads(os.environ["PROBE_TL"])
END = float(os.environ.get("PROBE_END", "30"))
SL = {"fthrust", "speed", "damper", "flow-speed", "mass"}

def main():
    client = ControllerClient.from_environment()
    client.arm()
    try:
        first = client.wait_until_running(timeout=60)
        client.load_block_table()
        guid = client._block_guids
        t0 = first.simulation_time
        while True:
            fr = client.next_sample(timeout=5.0)
            t = fr.simulation_time - t0
            if t > END:
                break
            sl, ch = [], []
            for a, b, idx, name, val in TL:
                if a <= t < b:
                    (sl if name in SL else ch).append((guid[int(idx)], name, float(val)))
            client.send_sliders(sl)
            client.send_channels(channels=ch)
    finally:
        client.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
