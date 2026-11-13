"""Measure sim-time vs wall-time with different polling settings."""
import os, time
from controller_sdk import ControllerClient
POLL = float(os.environ.get("POLL", "0.05"))
END = float(os.environ.get("PROBE_END", "12"))
def main():
    client = ControllerClient.from_environment(poll_interval=POLL)
    client.arm()
    try:
        first = client.wait_until_running(timeout=120)
        client.load_block_table()
        t0 = first.simulation_time; w0 = time.time(); n = 0; last = t0
        integ0 = first.machine.machine_integrity
        while True:
            fr = client.next_sample(timeout=5.0)
            n += 1
            if os.environ.get("SEND", "1") == "1":
                client.send_indexes([])
            if fr.simulation_time - t0 > END:
                break
        w = time.time() - w0
        print(f"sim {fr.simulation_time - t0:.2f}s wall {w:.2f}s ratio {(fr.simulation_time - t0)/w:.3f} frames {n} integ0={integ0} integ={fr.machine.machine_integrity}", flush=True)
    finally:
        client.close()
if __name__ == "__main__":
    raise SystemExit(main())
