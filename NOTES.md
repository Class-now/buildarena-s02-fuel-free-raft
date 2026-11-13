# NOTES — BuildArena S02 Autopilot (engineering log)

Deadline: 2026-11-14 03:00 JST. FINAL.json only after 2026-11-14 01:30. Started 2026-11-11 23:36.

## How to run (learned)
- `cd control && PYTHONIOENCODING=utf-8 uv run python -m besiege_cli run --bsg <bsg> --controller <py> --sandbox "LONE ORB" --controller-timeout N --post-completion-hold N --experiment <name>`
  - Do NOT set PYTHONUTF8=1 (breaks tasklist decoding). PYTHONIOENCODING=utf-8 is required (cp932 console).
  - Run dirs: `datacache/control_experiments/<experiment>/runs/<ts>-<id>/` (telemetry.csv 25 Hz, all blocks).
  - Pre-controller hold is 3 s sim time by default; controller t0 ~ 3.1 s.
- Key/slider commands expire after ~1.0 s: resend every tick (send_sliders + send_channels each frame).
- Sliders: Booster `fthrust` 0..2 (default 1). Reaction wheel `speed` 0..2 (default .5), `damper` 0..2.
- GUIDs in the saved .bsg are preserved at runtime. Block order in block table = bsg order.
- machine_integrity reads 0.167 at first sample then 1.0; drops when blocks are destroyed.
- Analysis helpers: `agent_control/tools/tele.py`, `an_thrust.py`, `an_fuel.py` (run with `uv run python`).

## Physics measured (probe rig: start block + big tank + 1 booster + 3 RW, mass ~7)
- Gravity: min(22, mu/r^2) confirmed (apex decel matches).
- Atmospheric drag: linear, a = -k(alt) * v, k(alt) ~= 0.092 * (1 - alt/450), zero above alt ~450-500 (r ~1050-1100).
  Residual with engine off < 0.5 units/s^2 for alt 0..400. (Need to verify exactly zero above r=1100.)
- Booster: fuel flow = fthrust units/s (2.0/s at max) independent of speed.
- Booster thrust depends on speed: T(f,v) ~= T1*f*max(0.15, 1-(v/(46.6 f))^2). At f=2: 60.3 - 0.0068 v^2 (accel for mass~7),
  zero-crossing ~93 units/s, floor ~15 % of static. At f=1: floor reached by v~63 (thrust accel 4.4).
  => always burn at f=2; efficient speed regime v < ~55. Static force per booster at f=2 ~ 415 (if rig mass is 7.0).
  TODO: is v the |v| or axial component (matters for retro burns)? Does it scale per booster (force) or per vehicle?
- Fuel is light: big barrel 100 units = 3.5 mass. Effective exhaust velocity ~5900 >> orbital speed 84, so dry mass dominates.
- Probe tilted over during burn (asymmetric RW placement, default RW auto-stabilisation too weak) -> need active attitude control.

## Run log
- probe1 (20261111-233830): 1 s burn only (key expiry discovered). Crash.
- probe2 (234240): 5 s f=2 burn, drag fit.
- probe3 (234636): burn-coast-burn; proved thrust is speed dependent, not altitude dependent. f=1 burn at v~70 gives only 4.4.
- probe4 (234928): f=1.5 burn + long f=2 burn to v=100; floor ~9 (15 %).

## 2026-11-12 00:40 — more physics / toolkit facts
- **Retro thrust is full**: thrust loss only applies to the velocity component ALONG the thrust axis (v_ax>0):
  F = F1*f*phi, phi = max(0.155, 1 - 0.00185*u - 9.36e-5*u^2), u = 2*v_ax/f ; phi = 1 for v_ax <= 0. F1 = 211.5 per unit f per booster (423 at f=2).
  Fuel flow = f units/s per booster always. => best energy/fuel at v_ax ~ 53; f=2 always best when v_ax>0; braking is cheap.
- Per-booster thrust scales with booster count (1, 2, 4 boosters consistent). Documented masses consistent (SB .25, RW .25, booster 1, big tank 5 full).
- Reaction wheel (RW): torque actuator. LeftKey -> body angular accel NEGATIVE about wheel axis (axis = block quat * (0,0,1)), RightKey positive.
  alpha ~ G*(speed-0.35) for speed>=0.45 (dead zone below ~0.35). v1 (14 mass): G=7.8 rad/s^2 per unit speed (pitch), ~30 (roll).
  damper slider: 0 = no auto-stabilisation (rates persist); 2 = strong rate damping. Idle wheel with damper>0 fights commanded rotation.
- **Sim runs at ~0.45x real time.** Plan wall-clock accordingly (600 s sim = 22 min).
- **Always run with `--reload-sandbox`** (EXTRA="--reload-sandbox" for tools/run.sh). Without it, a 2nd run of a machine that ended on the pad starts broken (integrity 12/17, dead boosters).
  After a failed/timeout run: `besiege_cli quit`, then rerun.
- **machine_integrity = (blocks still connected to the root cluster) / (total blocks)**. So a released payload lowers it by N_payload/N_total.
  To keep telemetry integrity >= 0.90 after separation: root must be on the vehicle and payload blocks <= 10 % of block count. (score_estimate reports last machine_integrity.)
- Grabber: detachKey releases only while held; it re-grabs instantly if payload still within 0.2 -> not a clean separator. Use Decoupler (ejects).
- Landing at 8 units/s vertical on the 4 boosters did not damage v1 (integrity stayed 1.0).
- hop1 (20261112-001248): climb/hover/land works; bug: landing feed-forward made it hover at h=1.8 until fuel ran out (fixed: ff scaled by sink ratio).
- No Ballast blocks anywhere (hard rule "ballast tricks" => DQ risk). Payload = structural 'satellite' blocks at default settings.

## Design direction (v1 = s02_orbiter_261112_000102: big tank, 4 boosters, 6 RW, grabber, 5-block payload ~3.2 mass, total ~14)
- Fuel is cheap in mass; boosters (1 each) + structure dominate. ~1 booster per 9 units of liftoff mass is enough.
- Ascent should climb at ~50 units/s with few boosters at f=2 (PWM / subset), build tangential speed with thrust pitched ~45 deg off velocity.
- Next: mass-measurement rig with decouplers (find heaviest legal payload blocks), then ascent/orbit guidance + offline sim.

## 2026-11-12 01:30 — status
- Block masses measured with decoupler rig (constant retro thrust, m = F/a): Fly Wheel 1.31, Big Barrel 1.25, Half Pipe 1.2,
  Steering Block 1.11, Large Wheel Unpowered 1.1, Metal Ball 1.09, Wheel Unpowered 1.08, Log 1.0, Corner Wooden Block 0.71,
  Metal Jaw 0.70, Bomb Holder 0.65, Decoupler 0.34. Nothing is much heavier than ~1.3 -> payload mass ~ 1.3 x block count.
- Decoupler: fires with ExplodeKey; payload leaves with ~8 units/s relative speed (1.65-mass payload vs 10-mass vehicle).
  integrity drops by (released blocks)/(total) at release (13-block v1b: 1.0 -> 0.846).
- HEDGE decision: keep telemetry machine_integrity >= 0.90 after release => payload blocks (incl. decoupler) <= 10 % of total block
  count, root (Starting Block) on the vehicle. Payload = decoupler + stack of Fly Wheels. Vehicle padded only with functional blocks.
- Attitude control: **biased wheel pairs** (two wheels with opposite axes on each body axis, both RightKey, torque = G*(s+ - s-)):
  smooth, no dead zone; 15 deg step settles in ~1.2 s with no overshoot, hover error 0.00 deg. Single wheel fallback has dead band.
- Boosters have a **ground-effect cushion** (hover at h~0.7 with ~80 % weight): landing uses an integrator on vertical-speed error.
- Game sometimes stalls telemetry for >30 s: controller waits (up to 10 min) instead of aborting.
- Flight software: agent_control/controller.py (MISSION=hop|massrig|orbit, CONFIG=..., CFG_OVERRIDE=json), fsw/{core,vehicle,nav,attitude,guidance,mission_*}.py.
  Offline: agent_control/sim/{model,opt_ascent,closed_loop}.py. Open-loop optimum for v1b (12.4 mass, 2 boosters) ~21.2 fuel to r=1180 circular;
  closed-loop law (PWM hold of axial speed 50, pitch 0->50 deg over alt 40..420, cut at apoapsis 1250, circularise) ~22.6 in sim.
- v1b = s02_orbiter_261112_010803 (13 blocks: SB, big tank, 4 boosters, 6 RW, decoupler + 1 flywheel).
- hop3/hop4: hop-hover-land OK (pad error 0.0-1.4, touchdown < 0.6 units/s).
- **orbit1 (20261112-0121xx)**: first attempt reached orbit 1236 x 1284 at t=20.6 s using 21.6 fuel; payload released at t=23.6.

## 2026-11-12 02:30 — FIRST COMPLETE MISSION + fuel-free propulsion discovery
- **orbit1 (datacache/control_experiments/orbit1/runs/20261112-012342-7b6b7425)**: v1b (s02_orbiter_261112_010803), MISSION=orbit.
  Orbit 1236x1284 at t=20.6 s (21.6 fuel), payload (decoupler+1 flywheel, 1.65) released t=23.6 -> 1258 x ~1790 orbit,
  deorbit over pad at t=107, touchdown t=129 pad error 0.75, payload 3.08 revs at t=416. Fuel used 37.2 of 104.
  score_estimate: gate PASS (3.19 revs), landing d=0.7 (A=0.9996), last machine_integrity 0.846 (payload 2 of 13 blocks).
  This is the booster-based fallback design (not yet re-run from reproduce.py).
- More masses: Steering Thruster (RCS) 0.10, Drag Block 0.39, Brace 0.41, Bouncy Pad 0.39, Wooden Pole 0.63,
  Single Wooden Block 0.48, Double Wooden Block 0.64, Wheel Unpowered 1.1.
- **Steering Thruster = fuel-free thrust ~8.1-9 force per nozzle at 0.10 mass**, independent of altitude (0..1050) and of speed
  (0..141 units/s), both nozzles (LeftKey thrusts the vehicle towards the block's local +Y, RightKey towards -Y).
  BUT the jet pushes on blocks in its path: thrusters stacked above each other lose ~35 %. Use a single flat layer with
  nozzle axes vertical (thrusters on the vertical side faces of horizontal poles need no twist) and nothing above/below them.
- **Flying Block** (FlyKey + slider speed 0..2): fuel-free lift, ~95 force at speed 2 near the ground (if its mass is ~0.5),
  but fading ~linearly to zero at ~250 altitude (and lower when climbing fast). Good as a fuel-free 'first stage'.
- => v3 concept: raft = cross of wooden poles at booster level, RCS thrusters on all lateral faces (T/W_rcs ~0.6 at ground,
  >1 above ~200 altitude), flying blocks on top for the first 200 altitude, RW pairs at arm ends, one token booster (finite eta),
  payload stack (decoupler + flywheels) on the Starting Block. Fuel use ~0 => efficiency score max; block count large => payload
  can be >10 blocks while keeping payload <= 10 % of blocks (integrity hedge).
- Improved booster guidance (CLIMB->BOOST->COAST->CIRC with velocity-to-go burn while descending) in fsw/guidance.py; offline 25.5 vs 26.3 fuel.
- Closed-loop deorbit stop (v^2/2d) implemented, not yet flown.

## 2026-11-12 04:05 — v3 fuel-free raft: lessons
- Current design: **v3b = s02_orbiter_261112_024418** (83 blocks): Starting Block hub with 4 arms of 3 Wooden Poles each (attached to
  the SB side faces, thrusters on pole lateral faces f0/f1/f5/f6 get vertical nozzles by default), 44 lift thrusters, 4 tangential
  tip thrusters (twisted 90 deg; roll control), 8 Flying Blocks on arm tops (x=2,3), Single Wooden Block on SB top carrying 4
  reaction wheels (pairs), decoupler + 3 Fly Wheels on top of it (payload = 4 blocks, 4.27), 1 Booster on E arm top (token burn),
  4 Braces between arm tips (ring). Config: agent_control/config_v3.json. Vehicle dry ~19.2 (flying block mass assumed 0.5).
- Failures on the way (do not repeat):
  * RW at arm tips -> control/structure oscillation (6 Hz) snapped an arm. Keep RWs on the rigid hub.
  * Thrusters have a built-in auto-stabilisation when no key is pressed: with tangential tip thrusters it shook the arms in-plane during
    the 3 s pre-controller hold until 2 arms broke. Fix: `--controller-prestart --pre-controller-hold 0` (controller writes the
    ready handshake, see Flight.start), idle thrusters hold BOTH keys (cfg rcs_idle_both), ring braces between arm tips.
  * Holding both keys leaks a small net force (~0.3 units/s^2 towards body +Y: up-jets partly blocked by fans): do not coast
    long in orbit with the launcher; release the payload right after insertion.
  * `taskkill /IM python.exe` also kills the MCP server process (it restarts but loses the active lifespan) -> never do that;
    stop runs with TaskStop + `besiege_cli quit`.
  * MCP save_machine can hang (30 min idle timeout) although the files are written; check file mtime instead of waiting.
- Sim speed with 83 blocks: ~0.235x real time.
- mu = 8,456,800 verified from payload coast (fit 8,457,215); no drag between r = 1258 and 1789.
- v3hop3: hover/attitude fine with braces (integrity 1.0); steady 9 deg tilt from the off-centre booster -> attitude integral (att_ki 2.5).
- v3orbit1 (20261112-034443): reached 1192 x 1234 orbit at t=35.8 s with 0.0015 fuel; release never happened (rate condition) -> fixed.
- New return for the fuel-free launcher: RELEASE (prograde, quick) -> BRAKE (reverse nozzles kill orbital speed) -> RETURN (powered
  fly-back at >=480 altitude with landing_cmd overrides cfg["cruise"]) -> DROP/LAND (a_brake 4, thrust never below a_up_min).

## 2026-11-12 04:25 — v3orbit2: first complete fuel-free mission (v3b, 83 blocks)
- Run `datacache/control_experiments/v3orbit2/runs/20261112-035700-ef6ed999` (MISSION=orbit CONFIG=config_v3.json, prestart).
  Orbit insertion t=35 (rp 1223 / ra 1254), release t=39.6, payload orbit after kick 1233 x ~1510 (decoupler kick +4 prograde),
  reverse-nozzle brake, fly-back, touchdown t=162.6 pad=0.82; payload 3.08 revs (post-separation) at t=375. Estimator: PASS,
  d=5.0, integrity 0.952, fuel used 0.004 (token burn).
- Problems seen: (1) after the brake the 114 deg slew to vertical took 6.5 s (free fall 588 -> 80 altitude);
  (2) on the ground the idle thrusters (both keys held) make the vehicle creep: pad 0.82 -> 4.9 in 210 s, speed 0.1-0.2;
  (3) lateral oscillation in the final hover.
- Slew analysis: rate plateau 0.28 rad/s = kd*rate_max/(kd+c) -> the vehicle has rotational damping c ~ 4.5 1/s (empty v3b,
  wheel gain 6.5): the reaction wheels act like rate servos (steady rate ~ 1.44 x speed difference). Fix: rate feed-forward
  alpha = kd (r_cmd - w) + c r_cmd with c = 0.69 x wheel gain (att_damp_ratio).
- Return redesign: after separation go straight to the fly-back law while still in orbit (turn first, then brake + hold
  altitude in one loop) -> no free fall during the turn (direct_return, default on).
- Fly Wheel is described in the catalogue as "unpowered metal flywheel" -> legal payload block.
- v3c built (lifespan s02_orbiter_261112_040910, 113 blocks): arms 4 poles, 60 lift thrusters, 4 tip thrusters, 8 braces,
  payload = decoupler + 9 Fly Wheels (10 blocks = 8.8 % of blocks, 12.13 mass). Config config_v3c.json.

## 2026-11-12 05:40 — legs, calibration, fallback v3d-lite, v3e in progress
- Ground rest: without legs the raft stands on the thruster nozzles and vibrates for ever (1.1-1.5 Hz, root speed 0.3 rms,
  creep 0.03/s) in EVERY idle mode. With legs (Single Wooden Block under the arms, thrusters 0.8 above ground) it is quiet:
  jitter 0.017 rms, drift 0.0002/s. -> legs are mandatory; after landing all keys are released (landed_release).
- Steering Thruster catalogue text: "by default automatically stabilizes the machine body" -> rate damping c ~ 4 1/s about
  pitch/yaw whatever the keys (in flight too). Attitude loop uses rate feed-forward att_damp_ff = 4.0, att_rate_max 0.5.
- CALIBRATION (thrust acceleration per active thruster above the fan ceiling): thruster force = 8.8, Flying Block mass = 1.0
  (not 0.5). True masses: v3b empty 24.7; v3d-lite empty 32.41 (+ payload 6.89 = 39.3). Configs use "effective" masses in
  8.3-force units (true x 0.943).
- Fan (8 Flying Blocks, slider 2): force ~ 1084 (1 - alt/195)(1 - v_climb/70) [true units], spin-up/down lag. Dead above ~195.
  => between alt ~150 and ~250 only the thrusters lift: stall if total mass too high. Offline model sim/rcs_ascent.py
  (effective-mass units): 60 thrusters stall above ~44-45 effective (v3d with 10 flywheels = 45 stalled in the hop).
  Rule used: true mass <= n_thrusters x 8.8 / 12.45.
- BUG fixed: tip (roll) thrusters had their command sign flipped by numeric noise in the nozzle axis (3 of 4 worked against
  the roll damper) -> steady roll 0.14 rad/s; with a body-fixed thrust misalignment (~2 deg) the vehicle circled the pad at
  3.3 and never descended (run v3dl_m1 stopped by hand after 1.5 payload revs; payload orbit was 1278 x 1313).
  Fixes: sign flip only for lift thrusters; lateral integral term near the pad (lat_ki 0.04); gate timeout (40 s -> tol 8).
- Other fixes: CIRC end-game keeps the axis near prograde when the velocity-to-go is small (was swinging 50 deg); velocity
  is referred to the centre of mass (com_y_loaded / com_y_empty); rest height re-referenced after settling; second touchdown
  criterion (standing still below h 1.0 for 1.5 s); v_desc_max 45 (powered descent instead of free fall).
- Machines (copies of MCP output in agent_control/machines/): v3b, v3c, v3d (8 legs, 10 flywheels: too heavy),
  v3d_lite (4 outer legs, 5 flywheels, 113 blocks, payload 6 blocks = 5.3 %, payload mass 6.89) = current fallback candidate,
  agent_control/machine.bsg = v3d_lite, mission.json -> config_v3dl.json, prestart.
- MCP: a session restart kills the active lifespan; reload costs ~22k tokens -> delegate bulk building to a subagent.
  Active lifespan s02_orbiter_261112_051320 (being extended to v3e: 5-pole arms, 76 lift thrusters, third brace ring,
  12 flywheels, 144 blocks, payload 13 blocks = 9.0 %, payload 16.06, true total ~54.2).
- Run v3dl_m2 (reproduce.py, experiment v3dl_m2) started 05:36.

## 2026-11-12 06:10 — FALLBACK #1: v3dl_m2 complete from reproduce.py
- Run `datacache/control_experiments/v3dl_m2/runs/20261112-053636-7607561e` (machine agent_control/machines/v3d_lite.bsg,
  config_v3dl.json as of 05:36 incl. lat_ki 0.04): orbit t=27.7, release 28.7, payload orbit ~1268 x 1310, touchdown t=198
  pad 3.71 (hovered 40 s at the gate: whirl driven by the lateral integrator -> integrator now OFF, lat_kp 0.45,
  gate timeout 20 s), MISSION COMPLETE t=335.6, payload 3.08 revs. Estimator: PASS, d=3.8 A=0.997, integrity 0.947,
  vehicle perfectly at rest (speed 0.000), fuel used 0.004. Payload mass 6.89.
- Roll damping with the sign fix works (|wy| ~ 0 in hover).
- Added: back-off with reverse nozzles after release (backoff_acc 6 for ~2.4 s) so the arms cannot hit the payload when
  turning; stall guard (ABORT -> land) in CLIMB; fan force model with speed fade in the controller.
- v3e built by subagent and saved (agent_control/machines/v3e.bsg/.json, 144 blocks, payload 13 blocks 16.06,
  vehicle dry 38.17). config_v3e.json (true masses, rcs_force 8.8). First mission: experiment v3e_m1.

## 2026-11-12 06:50 — v3e_m1 complete (payload 16.06); v3f built
- Run `datacache/control_experiments/v3e_m1/runs/20261112-061232-f9f0bda3` (reproduce.py, machines/v3e.bsg, config_v3e.json):
  orbit t=25.9 (1259 x 1313), release 27.0, back-off, fly-back, touchdown t=158.4 pad 1.76 (vr -1.3), MISSION COMPLETE
  t=352. Estimator PASS, d=1.8 A=0.999, integrity 0.910, at rest (0.007 rms), fuel used 0.0035. = current best single run.
- Thrust reality check: loaded v3e accelerates 17.8 with 76 thrusters at full thrust (=> ~12.7 force per thruster if the
  block-sum mass 54.2 is right) while partial (dithered) thrust gives ~9.1 per commanded thruster; v3b showed 8.9 at full.
  Not understood; consequence: no stall problem at all for v3e (climb speed 30-54 through the fan gap). Fans ~90 each at
  the ground, ~0 above alt ~130.
- After v3e_m1: landing commit hysteresis (no more up/down toggling at the gate), lat_kp 0.3 / lat_kd 1.0, CIRC dv_clamp 6.
- v3f (subagent build, machines/v3f.bsg/.json): 6-pole arms (92 lift thrusters), 4 brace rings, 8 legs, 15 flywheels,
  175 blocks, payload 16 blocks (9.1 %) = 19.99, vehicle dry 45.85. config_v3f.json. First mission: experiment v3f_m1.

## 2026-11-12 07:05 — v3f_m1 FAILED (tower broke off), cause found
- v3f_m1 (`datacache/control_experiments/v3f_m1/runs/20261112-064916-*`): at t=12 (alt 220, full thrust) the central tower
  (hub block + 4 reaction wheels + decoupler + 15 flywheels = 21 blocks) broke off at the Starting Block - hub joint.
- v3e_m1 telemetry: the whole tower (hub + payload) rocks +-8.6 deg as a rigid body about the hub joint (period ~6 s);
  the flywheel stack itself stays straight. The reaction wheels sit on that rocking hub -> flexible mode inside the
  attitude loop, wheels saturate, joint overloaded with 15 flywheels. v3e (12 flywheels) is marginal for the same reason.
- Fix being built (v3g, subagent): SB -> hub (wheels) -> vertical Wooden Pole "mast" -> decoupler -> flywheels, with four
  king-post Braces from the mast (z=3) to the arm tops at x=2 (inner fans moved from x=2 to x=4). 180 blocks, 15 flywheels.
- v3e verification run with current code: experiment v3e_m2 (started 07:05).

## 2026-11-13 09:20 — restart after a ~26 h outage (07:27 11/12 -> 09:12 11/13). Deadline 11/14 03:00, FINAL window from 01:30.
- v3e_m2 (`datacache/control_experiments/v3e_m2/runs/20261112-070516-*`, machines/v3e.bsg, config_v3e.json as of 07:05):
  MISSION COMPLETE t=326.6, payload 3.08 revs, rmin 1208.7; estimator PASS (3.18 revs), d=2.4 A=0.9985, integrity 0.910.
  => v3e has two complete passing runs from reproduce.py (v3e_m1, v3e_m2), payload 16.06. DE-FACTO FALLBACK = v3e_m2.
- After v3e_m2 (code/config changes not yet flown): att_kp_empty 2.5 (set at release), lat_kp 0.25, lat_kd 0.7.
- v3g built and archived (machines/v3g.bsg/.json, 180 blocks): hub + mast (Wooden Pole) braced by 4 king-post braces to the
  arm tops at x=2, inner fans moved to x=4, decoupler + 15 flywheels on the mast (payload 16 blocks = 8.9 %, 19.99),
  vehicle dry 48.12. config_v3g.json. The MCP lifespan is gone again (restart) - not needed unless the machine changes.
- 09:20: experiment v3g_m1 started (reproduce.py; mission.json -> config_v3g.json; machine.bsg = v3g).
- PLAN: if v3g_m1 passes -> second v3g run with unchanged code -> promote v3g. If it fails -> re-select v3e
  (cp machines/v3e.bsg machine.bsg; mission.json -> config_v3e.json; make_declaration) and run it twice.
  Then finish deliverables (CONTROL.md vehicle section, declaration.json, FINAL.draft.json) and write FINAL.json after 01:30.

## 2026-11-13 10:00 — v3g/v3h results; COLLISION HAZARD found and fixed
- v3g_m1: climb stalled at alt 106 (stall guard -> landed with payload). 8 fans not enough for 68 mass at liftoff.
- v3h (machines/v3h.bsg/.json, lifespan s02_orbiter_261113_092827): v3g + 4 fans at x=5 (12 fans), booster moved to E x=7,
  184 blocks, payload 19.99, vehicle 52.12. v3h_m1: tower rigid (attitude error < 2.3 deg all the way), orbit 1249 x 1266 at
  t=50.8, but the climb nearly stalled (speed fell to 8 at alt 260-275), and at t=142 the vehicle was HIT BY ITS OWN PAYLOAD
  (closest approach 3.7; integrity 0.913 -> 0.576): the fly-back cruised at the release altitude, i.e. inside the payload's
  orbit, and the pad lies in the orbit plane, so the payload comes back through the hovering vehicle one period later.
  Earlier "passes" were near misses: v3e_m2 4.1 units, v3dl_m2 6.7 units, v3e_m1 88 units.
  FIX: fly-back cruise altitude clipped to 480..500 (r ~ 1100, >= 100 below the payload periapsis >= 1200).
- Thrust puzzle: in the game instance of 11/12 05:16-07:27 (v3dl, v3e, v3f flights) the loaded vehicles accelerated as if the
  payload weighed almost nothing (full-thrust 12.5 force/thruster equivalent); v3b (earlier instance) and v3g/v3h (today)
  show the normal ~9.0-9.4 per thruster (rising slowly with speed to 10.5). Not understood -> design for 9.0.
  Fans ~100-106 each at the ground (slider 2), fading with altitude (zero ~180) and climb speed.
- Next: fly v3e today (experiment v3e_m3) to see its real ascent margin with normal thrust + test the cruise fix.

## 2026-11-13 10:30 — v3e_m3 PASS with the collision fix (verification run 1 of 2 for v3e)
- v3e climbs strongly today as well (same as 11/12) -> the "light payload" effect is specific to the hub-mounted tower
  (overloaded hub joint; the raft does not feel the full tower inertia), not to a game session. v3h (braced mast) shows the
  honest ~9.0-9.4 force per thruster and nearly stalled.
- v3e_m3 (`datacache/control_experiments/v3e_m3/runs/20261113-100134-dac689bc`, reproduce.py, machines/v3e.bsg,
  config_v3e.json with cruise 480..500, att_kp_empty 2.5, lat_kp 0.25/lat_kd 0.7, commit hysteresis): orbit t=32.2,
  release 33.2, fly-back at h=500, touchdown t=142.2 pad 0.88 vr -0.8 (no hovering at the gate), MISSION COMPLETE t=337.3,
  payload 3.08 revs, rmin 1203.9. Estimator: PASS 3.21 revs, d=1.0 A=0.9995, integrity 0.910. FINAL.draft.json written
  (tools/make_final.py <run_dir> "<summary>" [--final]).
- 10:30 v3e_m4 started (identical code/config) = verification run 2.
- v3i built (machines/v3i.bsg/.json, lifespan s02_orbiter_261113_092827, 204 blocks): v3h + 7th pole per arm (108 lift
  thrusters), payload 19.99, vehicle 56.24; config_v3i.json. Candidate to test after v3e is locked.

## 2026-11-13 10:50 — VERIFIED FALLBACK = v3e (payload 16.06), runs v3e_m3 + v3e_m4 (identical final code)
- v3e_m4 (`datacache/control_experiments/v3e_m4/runs/20261113-103028-05ba73b8`): orbit t=32.8, release 33.9, touchdown
  t=144.8 pad 0.76, MISSION COMPLETE t=351, payload 3.08 revs, rmin 1222. Estimator PASS 3.19 revs, d=0.8 A=0.9996,
  integrity 0.910; closest payload pass 400 units (vehicle already low).
- Snapshot of the verified deliverables: backup/v3e_verified/agent_control (+ FINAL.draft.json pointing at v3e_m3).
  To restore: copy backup/v3e_verified/agent_control over agent_control (machine.bsg = v3e, mission.json -> config_v3e.json,
  declaration.json for v3e).
- If nothing better is verified: at 01:30 on 11/14 run
  `uv run python agent_control/tools/make_final.py datacache/control_experiments/v3e_m4/runs/20261113-103028-05ba73b8 "<summary>" --final`
  (or copy FINAL.draft.json to FINAL.json).
- Next: test v3i (payload 19.99, braced mast, 7-pole arms) = experiment v3i_m1.

## 2026-11-13 11:15 — v3i_m1 PASS (payload 19.99); verification run 2 (v3i_m2) started
- v3i = braced mast + 7-pole arms (108 lift thrusters, 12 fans, 204 blocks, payload 16 blocks = 7.8 %, 19.99; vehicle 56.24).
- v3i_m1 (`datacache/control_experiments/v3i_m1/runs/20261113-105047-93a31678`, reproduce.py, machines/v3i.bsg,
  config_v3i.json): climb speed minimum 17 (alt 234-268), attitude error < 6 deg, orbit 1247 x 1267 at t=40.1, release
  45.8 (integrity 0.9216), fly-back at h=500, touchdown t=183.6 pad 1.35 vr -2.1, MISSION COMPLETE t=348, payload 3.08 revs,
  rmin 1257.9. Estimator PASS 3.25 revs, d=1.4 A=0.9992, integrity 0.922, at rest; payload passes 170 above the vehicle.
- If v3i_m2 also passes: promote v3i (machine.bsg = v3i, mission.json -> config_v3i.json, declaration regenerated 11:15),
  make FINAL.draft.json from it, snapshot to backup/v3i_verified.

## 2026-11-13 11:40 — VERIFIED BEST = v3i (payload 19.99), runs v3i_m1 + v3i_m2 (identical code/config)
- v3i_m2 (`datacache/control_experiments/v3i_m2/runs/20261113-111510-62588730`): orbit t=40.1 (1248 x 1267), release 45.9,
  touchdown t=177.5 pad 1.15 vr -1.9, MISSION COMPLETE t=350.7, payload 3.08 revs, rmin 1259. Estimator PASS 3.32 revs,
  d=1.2 A=0.9994, integrity 0.922, at rest, payload passes 172 above the cruising vehicle.
- PROMOTED: agent_control/machine.bsg = machines/v3i.bsg, mission.json -> config_v3i.json, declaration.json (payload 19.99,
  vehicle 56.24, 204 blocks), FINAL.draft.json -> v3i_m2. Snapshot: backup/v3i_verified/ (agent_control + FINAL.draft.json).
  Older verified fallback: backup/v3e_verified/ (payload 16.06).
- At 01:30 on 11/14 (if nothing better is verified): `cp FINAL.draft.json FINAL.json` (draft must match agent_control state;
  if agent_control was changed by later experiments, first restore backup/v3i_verified/agent_control).

## 2026-11-13 12:05 — v3j (payload 25.23) first pass; tuned rerun started
- v3j (machines/v3j.bsg/.json, lifespan s02_orbiter_261113_092827, 228 blocks): v3i + 8th pole per arm (124 lift
  thrusters) + 4 flywheels (19): payload 20 blocks (8.8 %) = 25.23, vehicle 60.36. config_v3j.json.
- New code (off unless config att_assist): thruster-couple attitude assist while the lift engines are idle (outer
  thrusters of opposite arms fire in opposite directions; bang-bang on the rate error) - needed because the wheels alone
  turn the loaded v3j at only ~0.1 rad/s. Also softer flare for v3j (a_brake 1.8, h_flare 2.5).
- v3j_m1 (`datacache/control_experiments/v3j_m1/runs/20261113-114353-*`, assist_n 6, ra1 1290): climb min speed 14,
  coast turn 7.8 deg/s -> CIRC started late (already sinking) -> orbit 1200 x 1295 at t=56.8, release 57.8 (integrity
  0.9123), touchdown t=192.6 pad 1.25 vr -1.1, MISSION COMPLETE t=356.8, payload 3.08 revs, rmin 1197.8 (margin only 98).
- Tuning for v3j_m2 (12:05): assist_n 10, ra1/ra_target/rc_target 1320, rp_ok 1270, rp_min 1215, circ_beta_lim_radial 1.0
  (fine mode may tilt further when a real radial error is left). Needs two identical passes to replace v3i.
- Verified best remains v3i (backup/v3i_verified, FINAL.draft.json -> v3i_m2).

## 2026-11-13 13:00 — VERIFIED BEST = v3j (payload 25.23), runs v3j_m2 + v3j_m3 (identical code/config)
- v3j_m2 (`datacache/control_experiments/v3j_m2/runs/20261113-120450-238d865a`): orbit 1252 x 1342 at t=50.7, release
  51.7, touchdown t=171.8 pad 0.46 vr -1.1, MISSION COMPLETE t=369.3, payload 3.08 revs, rmin 1250.9. Estimator PASS
  3.27 revs, d=0.5 A=0.9998, integrity 0.912, payload passes 197 above the vehicle.
- v3j_m3 (`.../v3j_m3/runs/20261113-123119-3fabd11a`): release t=55.8 (1236 x 1340), touchdown t=181.5 pad 1.73,
  MISSION COMPLETE t=370.4, rmin 1235.5. Estimator PASS 3.34 revs, d=1.8 A=0.9989, integrity 0.912, at rest.
- PROMOTED: agent_control/machine.bsg = machines/v3j.bsg, mission.json -> config_v3j.json, declaration.json (payload 25.23,
  vehicle 60.36, 228 blocks), FINAL.draft.json -> v3j_m2. Snapshot: backup/v3j_verified/. Older: v3i_verified, v3e_verified.
- At 01:30 on 11/14 (if nothing better is verified): make sure agent_control == backup/v3j_verified/agent_control, then
  `cp FINAL.draft.json FINAL.json`.
- Next: v3k (machines/v3k.bsg/.json, 251 blocks: 9-pole arms, 140 lift thrusters, 22 flywheels, payload 23 blocks = 9.2 %,
  29.16; vehicle 64.48; config_v3k.json) as a structural-margin probe / candidate (experiment v3k_m1).

## 2026-11-13 13:20 — v3k_m1 exposed a guidance hole (fixed); v3k_m2 started
- v3k_m1: ascent fine (min climb speed 14, coast turn 11.5 deg/s), but the apoapsis overshot the target a little, so CIRC
  started on the way down (sinking -11..-15); when the tangential speed was reached the old code kept thrusting PROGRADE at
  full thrust because a radial error > dv_fine was left -> ran away to escape. (Same hole existed in the verified v3i/v3j
  code, it just was not triggered: their sink rate at the end of the burn was 2-3 instead of 6-7.)
- FIX (tools/patch_circ2.py -> fsw/guidance.py): (1) burn centred on the real apoapsis when it overshoots the target by up
  to circ_ap_margin (v3j/v3k configs: 80); (2) once the tangential speed is reached never add prograde speed: only a
  remaining sink rate (> vr_ok) is corrected with nearly radial thrust; (3) extra exit "fast enough and not sinking";
  (4) circ_timeout 45 s with rp_floor 1150 as a last resort. Old configs without the new keys behave as before except (2),(3).
- v3j config also: att_rate_max 0.26 (faster loaded turn). => v3j must be re-verified with this code (2 runs) before it
  replaces backup/v3j_verified (old code, still a valid fallback: FINAL.draft.json -> v3j_m2).
- 13:20 v3k_m2 started (machines/v3k.bsg, config_v3k.json, new guidance).

## 2026-11-13 13:42 — v3k_m2: structural limit found; final code for v3j; v3j_m4 started
- v3k_m2 (new guidance): clean insertion 1277 x 1291 at t=31.5 (burn centred on apoapsis - 20 s earlier than before),
  release 32.7, but at t=39.0, during the 150 deg turn of the EMPTY vehicle with the thruster-couple assist (10 outer
  thrusters per arm, bang-bang), two opposite arms broke off (integrity 0.908 -> 0.490). It still landed on the pad on two
  arms. => the assist is now used only while the payload is attached (assist_loaded_only, default true); the empty vehicle
  turns on its wheels (v3j: att_rate_max_empty 0.17).
- Margin evidence for v3j from v3k: ascent thrust loads (liftoff with 140 thrusters, 29-mass payload) survived twice ->
  v3j (124 thrusters, 25.2) has >= ~15 % margin there; loaded assist turns survived on v3k twice.
- DECISION: final candidate = v3j with the final code (guidance fix, assist loaded-only, att_rate_max 0.26 / 0.17).
  Needs two passes: v3j_m4 (started 13:42), v3j_m5. No further scale-up (v3k arms are at the structural limit).
- Until then the verified fallback is backup/v3j_verified (old code, FINAL.draft.json -> v3j_m2).

## 2026-11-13 14:40 — v3j_m4 pass, v3j_m5 FAILED in the descent -> descent fix, v3j_m6 started
- v3j_m4 (final-code candidate): orbit 1275 x 1340 at t=39.8, touchdown t=163.4 pad 1.40, MISSION COMPLETE t=366.5,
  payload rmin 1325; estimator PASS, d=1.4, integrity 0.912.
- v3j_m5 (identical): same ascent, but in DROP the pointing error exceeded 25 deg -> engines inhibited -> fell, braked
  tilted, came down 87 from the pad resting tilted 38 deg on an arm (integrity still 0.912).
- Check of ALL earlier runs: DROP pointing errors were 21-29 deg every time (v3e 21, v3i 25-26, v3j 21-29) - the previous
  landings were partly luck. Cause: at the start of DROP the thrust is tiny (a_up_min 2) so a small lateral demand asks
  for the full 20 deg tilt and flips sign a second later; the weak wheels of the empty vehicle chase it.
- FIX (tools/patch_drop.py, config keys in config_v3j.json): tilt limit 3 deg while a_up < 8 (tilt_aup_ref/tilt_low_deg);
  slew-rate limit of the commanded axis in landing mode (cmd_slew_deg 7 per s, starts from the present attitude);
  tighter hand-over from cruise (cruise_exit_dist 10, cruise_exit_v 2).
- => all earlier "verified" snapshots share the weakness; the final must be re-verified with this code: v3j_m6 (14:40), m7.

## 2026-11-13 15:20 — v3j_m6 pass but fly-back dipped to h=22; cruise fix; v3j_m8 started
- v3j_m6 (descent fix): DROP pointing error max 1.8 deg (was 21-29), touchdown t=167.7 pad 3.34 (hovered at the gate with
  a steady ~3 offset until the 20 s time-out), MISSION COMPLETE t=357.6, payload rmin 1286.7, integrity 0.912.
  BUT during RETURN the altitude dipped to h=22 at t=96: with the assist now off for the empty vehicle its tilt reversal
  in the cruise takes >10 s on the wheels and the engines are inhibited above 25 deg error -> free fall from 500.
  (Earlier runs: RETURN min h 443-492.)
- FIX (tools/patch_cruise.py): after the first alignment in RETURN the commanded axis is slew-limited (cruise_slew_deg 7/s)
  so the engines stay on while the tilt changes; gentler cruise for v3j: lat_vmax 45, lat_amax 5, tilt 40 deg.
- v3j_m7 did not start (runner: "Controller did not publish its readiness handshake before the deadline") - the machine is
  heavily loaded by other sessions (CPU 74 %, shell commands take minutes). Just retry in that case.
- 15:20 v3j_m8 started (final-candidate code: guidance fix + assist loaded-only + descent fix + cruise fix).
  Need two identical passes (m8, m9) before promoting; check RETURN min h (> 400), DROP max err (< 10), pad < 5.

## 2026-11-13 15:45 — v3j_m8: cruise oscillation (empty vehicle control-starved); empty assist added; v3j_m9 started
- v3j_m8 (cruise slew limiter, lat_vmax 45, tilt 40): the vehicle flew back and forth through the pad (+-100, 20-30 speed)
  for 200 s with pointing errors 13-26 deg and altitude dips (inhibit above 25 deg). Stopped by hand.
- Cause: the empty v3j on its 4 wheels turns at only ~7.5 deg/s (thruster auto-stabilisation damping eats the wheel
  torque) -> it cannot even follow a 7 deg/s command. In m2-m4 the big bang-bang couples (10 thrusters) rescued it whenever
  the engines were inhibited - the same thing that broke v3k's arms.
- FIX (tools/patch_assist3.py): assist for the empty vehicle with only 4 outer thrusters per arm (assist_n_empty 4,
  thresholds 0.05/0.02): couples when the engines are idle, DIFFERENTIAL THRUST when they are on (one arm tip forced on,
  the opposite one off). Loaded behaviour unchanged (couples with 10 thrusters only when the engines are idle).
  Softer cruise: lat_kp 0.08, lat_kd 0.5, lat_vmax 30, lat_amax 2.5, tilt 25 deg, cruise_slew_deg 7. att_rate_max_empty 0.22.
- 15:45 v3j_m9 started. Acceptance: RETURN min h > 400, pointing errors in cruise/DROP < ~12 deg, pad < 5, integrity 0.912.
- Fallbacks if v3j cannot be made reliable in time: backup/v3j_verified (old code; passes ~3 of 4), backup/v3i_verified,
  backup/v3e_verified - all share the descent weakness, v3e least (strongest wheels relative to its size).

## 2026-11-13 16:05 — v3j_m9 PASS with the final code (run 1 of 2); v3j_m10 started 16:02
- v3j_m9 (`datacache/control_experiments/v3j_m9/runs/20261113-153834-bb91a350`): orbit 1275 x 1337 at t=38.4, release 39.4,
  fly-back: RETURN min h 499, pointing error <= 4.3 deg, over the pad t=272 (drifted 870 downrange, cruise 30), DROP max
  err small, touchdown t=300.6 pad 0.52 vr -1.0, MISSION COMPLETE t=357.2, payload 3.08 revs, rmin 1287.6.
  Estimator PASS 3.17 revs, d=0.5 A=0.9997, integrity 0.912, at rest the last 60 s, payload passes 231 above the vehicle.
- FINAL-CANDIDATE STATE = current agent_control (machine.bsg = machines/v3j.bsg, mission.json -> config_v3j.json,
  declaration.json for v3j: payload 25.23 / vehicle 60.36 / 228 blocks; CONTROL.md updated).
- If v3j_m10 passes: FINAL.draft.json from v3j_m9 (or m10), snapshot backup/v3j_final/, then no more code changes.

## 2026-11-13 16:32 — VERIFIED FINAL STATE = v3j with final code: runs v3j_m9 + v3j_m10 (identical code/config)
- v3j_m10 (`datacache/control_experiments/v3j_m10/runs/20261113-160516-7bfaca96`): orbit 1276 x 1341 at t=39.9, release
  40.9, RETURN min h 500 / max pointing error 4.8 deg, over the pad t=225.5, DROP max error 2.4 deg, touchdown t=254.2
  pad 1.12 vr -1.0, MISSION COMPLETE t=367.2, payload 3.08 revs, rmin 1326.1. Estimator: 3.18 revs PASS, d=1.13
  A=0.9994, integrity 0.912.
- PROMOTED: FINAL.draft.json -> v3j_m10; snapshot backup/v3j_final/ (agent_control + FINAL.draft.json). The older
  snapshots (v3j_verified, v3i_verified, v3e_verified) used code with the descent/cruise/guidance weaknesses.
- Payload 25.23 (Decoupler + 19 Fly Wheels), vehicle dry 60.36, 228 blocks, fuel used 0.004 of 1.0.
- AT 01:30 JST on 11/14: verify agent_control == backup/v3j_final/agent_control (diff -r), then
  `cp FINAL.draft.json FINAL.json`. Do not change code/config any more unless a new version is verified twice.
- Design is at its structural limit one step up (v3k arms broke with large couples) -> no further scale-up planned.
  Optional: one more confirmation run (v3j_m11) for reliability statistics; otherwise idle until the window.

## 2026-11-13 16:57 — v3j_m11 PASS (3rd consecutive pass with the final code)
- v3j_m11 (`datacache/control_experiments/v3j_m11/runs/20261113-163239-e92f2b1e`): orbit 1278 x 1340 at t=39.8, touchdown
  t=254.2 pad 0.92, MISSION COMPLETE t=367.8, rmin 1327.8; estimator PASS 3.18 revs, d=0.9, integrity 0.912; RETURN min h
  500, pointing errors < 5 deg. Very repeatable (m10 and m11 touch down within 0.1 s of each other).
- 16:57 started two more unattended confirmation runs (v3j_m12, v3j_m13); summary in /tmp/v3j_conf.log
  (= C:\Users\impwg\AppData\Local\Temp\v3j_conf.log). Afterwards: `besiege_cli quit`, then wait for 01:30 and write FINAL.json.

## 2026-11-13 17:43 — confirmation runs done: 5 consecutive passes with the final code (v3j_m9 .. v3j_m13); game quit
- v3j_m12 (`.../v3j_m12/runs/20261113-165658-6cdd869e`): touchdown t=253.8 pad 2.19, MISSION COMPLETE t=365.7, rmin 1320.7,
  estimator PASS 3.18 revs, d=2.2 A=0.9986, integrity 0.912.
- v3j_m13 (`.../v3j_m13/runs/20261113-1719*`): touchdown t=253.1 pad 0.90, MISSION COMPLETE t=366.9, rmin 1325.5,
  estimator PASS 3.18 revs, d=0.9 A=0.9995, integrity 0.912.
- In all five: RETURN min h 499-500, pointing errors < 5 deg, DROP errors < 3 deg, vehicle at rest > 100 s before the end.
- Nothing more to fly. FINAL.draft.json -> v3j_m10. Remaining step: at/after 01:30 JST on 11/14 `cp FINAL.draft.json FINAL.json`
  (after checking `diff -r -x .venv -x __pycache__ agent_control backup/v3j_final/agent_control` is empty).

## 2026-11-14 01:31 — FINAL
- Window open (after 01:30 JST). agent_control verified identical to backup/v3j_final; FINAL.draft.json identical to the
  snapshot; run directory v3j_m10 complete (telemetry.csv, trajectory.csv, summary.json).
- FINAL.json written = FINAL.draft.json: run_dir datacache/control_experiments/v3j_m10/runs/20261113-160516-7bfaca96,
  machine s02_orbiter (agent_control/machine.bsg = machines/v3j.bsg, history machines/v3j.json), control_dir agent_control.
- Final design v3j: fuel-free raft, 228 blocks, payload = Decoupler + 19 Fly Wheels (20 blocks, 25.23), vehicle dry 60.36,
  token fuel use 0.004 of 1.0. Five consecutive passing runs with the final code (v3j_m9 .. v3j_m13):
  payload >= 3.08 revolutions after separation, rmin 1288-1328, landing 0.5-2.2 from the pad, integrity 0.912, at rest.
