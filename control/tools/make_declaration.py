"""Build agent_control/declaration.json (pre-launch declaration) from machine.bsg and the measured mass table.
usage: python agent_control/tools/make_declaration.py [bsg]"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from fsw.vehicle import parse_bsg

# dry mass per block type id (documented by the toolkit, or measured in-game with the decoupler mass rig, +-0.03)
MASS = {0: ("Starting Block", 0.25), 99: ("Fuel Barrel Big", 1.5), 92: ("Fuel Barrel", 0.25), 90: ("Booster", 1.0),
        101: ("Reaction Steering Block", 0.25), 4: ("Decoupler", 0.34), 88: ("Fly Wheel", 1.31), 63: ("Log", 1.0),
        1: ("Double Wooden Block", 0.5), 94: ("Grid Fin", 0.3), 96: ("Fuel Line", 0.2),
        41: ("Wooden Pole", 0.63), 15: ("Single Wooden Block", 0.48), 91: ("Steering Thruster", 0.10), 7: ("Brace", 0.41),
        14: ("Flying Block", 1.0)}   # Flying Block: from whole-vehicle thrust/acceleration calibration in flight (+-0.1)
FUEL = {99: 100.0, 92: 10.0, 90: 1.0}          # initial fuel units
FUEL_DENSITY = {99: 0.035, 92: 0.025, 90: 0.0}   # mass per fuel unit

def main():
    bsg = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "machine.bsg")
    extra = json.load(open(os.path.join(HERE, "mass_extra.json"))) if os.path.exists(os.path.join(HERE, "mass_extra.json")) else {}
    for k, v in extra.items():
        MASS[int(k)] = tuple(v)
    blocks = parse_bsg(bsg)
    dec = [b for b in blocks if b.type_id == 4]
    pay_idx = set()
    if dec:
        d = dec[0]
        pay_idx = {b.index for b in blocks if b.pos[1] >= d.pos[1] - 0.01 and abs(b.pos[0]) < 3 and abs(b.pos[2]) < 3}
    def row(b):
        name, m = MASS.get(b.type_id, (f"type {b.type_id}", None))
        return dict(bsg_index=b.index, guid=b.guid, block=name, dry_mass=m, initial_fuel=FUEL.get(b.type_id, 0.0))
    pay = [row(b) for b in blocks if b.index in pay_idx]
    veh = [row(b) for b in blocks if b.index not in pay_idx]
    unknown = [r for r in pay + veh if r["dry_mass"] is None]
    root = blocks[0]
    out = {
        "schema": "s02.declaration.v1",
        "machine_bsg": os.path.basename(bsg),
        "mass_source": "block masses documented by the toolkit or measured in-game (constant-thrust decoupler rig); fuel mass not included in dry mass",
        "payload": {
            "description": "Unpowered payload: separation decoupler plus a stack of unpowered Fly Wheels (no propulsion, no propellant).",
            "tracked_block_guid": pay[-1]["guid"] if pay else None,
            "blocks": pay,
            "initial_dry_mass": round(sum(r["dry_mass"] or 0 for r in pay), 3),
            "initial_fuel": 0.0,
        },
        "recovery_vehicles": [{
            "name": "launcher (single reusable stage, fuel-free RCS/fan propulsion; one Booster used only for a token burn)",
            "tracked_block_guid": root.guid,
            "tracked_block": "Starting Block (bsg index 0)",
            "blocks": veh,
            "initial_dry_mass": round(sum(r["dry_mass"] or 0 for r in veh), 3),
            "initial_fuel": round(sum(r["initial_fuel"] for r in veh), 3),
        }],
        "stage_boundaries": [{
            "between": ["launcher", "payload"],
            "mechanism": "Decoupler (ExplodeKey) on top of the launcher's central hub block; the decoupler leaves with the payload",
            "decoupler_guid": dec[0].guid if dec else None,
        }],
        "expended_stages": [],
        "launch_site_target": [0.0, 0.0, 0.0],
        "totals": {"blocks": len(blocks), "payload_blocks": len(pay), "vehicle_blocks": len(veh)},
    }
    if unknown:
        out["warning_unknown_mass_types"] = sorted({r["block"] for r in unknown})
    path = os.path.join(HERE, "..", "declaration.json")
    json.dump(out, open(path, "w"), indent=1)
    print("wrote", path, "payload mass", out["payload"]["initial_dry_mass"], "vehicle dry", out["recovery_vehicles"][0]["initial_dry_mass"],
          "fuel", out["recovery_vehicles"][0]["initial_fuel"], "blocks", out["totals"], "unknown", out.get("warning_unknown_mass_types"))

if __name__ == "__main__":
    main()
