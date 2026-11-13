"""One-off patch: controller prestart handshake, idle thrusters hold both keys (disables their auto-stabilisation)."""
import ast

p = 'fsw/core.py'
s = open(p).read()
s = s.replace('''        self.client.arm()
        first = self.client.wait_until_running(timeout=120)''', '''        self.client.arm()
        ready = os.environ.get("BUILDARENA_CONTROLLER_READY")
        if ready:
            # prestart mode: tell the runner we are ready before physics starts
            from controller_sdk.protocol import atomic_write_json
            atomic_write_json(Path(ready), {"schema": "buildarena.controller_ready.v1",
                                            "run_id": os.environ["BUILDARENA_RUN_ID"]})
        first = self.client.wait_until_running(timeout=120)''')
s = s.replace('''        self.veh = Vehicle(self.client)''', '''        self.veh = Vehicle(self.client)
        self.veh.rcs_idle_both = bool(self.cfg.get("rcs_idle_both", False))''')
open(p, 'w').write(s)
ast.parse(s)

p = 'fsw/vehicle.py'
s = open(p).read()
s = s.replace('''                rec.append((self.idx[(b.guid, "LeftKey")], 1.0 if v > 0 else 0.0))
                rec.append((self.idx[(b.guid, "RightKey")], 1.0 if v < 0 else 0.0))''', '''                if v == 0 and getattr(self, "rcs_idle_both", False):
                    # both nozzles on: zero net force, and the block's own auto-stabilisation stays overridden
                    rec.append((self.idx[(b.guid, "LeftKey")], 1.0))
                    rec.append((self.idx[(b.guid, "RightKey")], 1.0))
                else:
                    rec.append((self.idx[(b.guid, "LeftKey")], 1.0 if v > 0 else 0.0))
                    rec.append((self.idx[(b.guid, "RightKey")], 1.0 if v < 0 else 0.0))''')
open(p, 'w').write(s)
ast.parse(s)

import json
c = json.load(open('config_v3.json'))
c["rcs_idle_both"] = True
json.dump(c, open('config_v3.json', 'w'), indent=1)
print("ok")
