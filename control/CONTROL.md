# CONTROL.md — S02 "Deliver. Separate. Return." flight software

One command reproduces the mission: `uv run python agent_control/reproduce.py` (from the workspace root).
`reproduce.py` reads `mission.json` (which configuration file is the final design, prestart mode), loads
`machine.bsg` in the `LONE ORB` sandbox, and runs `controller.py` with `MISSION=orbit`. No human input.

## Vehicle (machine.bsg, built only with the BuildArena MCP tools)
Single reusable, **fuel-free** launcher ("raft"), root = Starting Block (tracked block of the recovery vehicle):
- four arms of eight Wooden Poles each in a cross (16.5 long), four rings of Braces between the arms for in-plane
  stiffness;
- 124 Steering Thrusters (RCS, no fuel) on the lateral faces of the arm poles, nozzles along the body ±Y axis: main
  propulsion (forward nozzles push the vehicle to body +Y, the opposite nozzles to −Y);
- four tangential Steering Thrusters on the arm tips: roll-rate damping;
- twelve Flying Blocks (lift fans, no fuel) on the arm tops: extra lift in the dense low atmosphere only (they fade out
  by about 180 altitude);
- hub block with four Reaction Steering Blocks (two opposed pairs): pitch/yaw attitude control; on top of it a vertical
  Wooden Pole ("mast") held by four king-post Braces to the arm tops, so that the payload tower cannot rock;
- eight Single Wooden Blocks under the arms: landing legs (the thrusters never touch the ground, the vehicle rests still);
- one Booster with its own 1.0 fuel unit: fired once for ~0.1 s at minimum throttle (token burn of ~0.004 fuel units) so
  that the expended fuel is finite and non-zero; it gives no useful impulse;
- on top of the mast: **Decoupler + stack of 19 unpowered Fly Wheels = payload** (no propulsion, no propellant). The decoupler
  leaves with the payload. `declaration.json` lists every block of the payload and of the launcher with masses.
The payload is at most 10 % of the block count, so the telemetry `machine_integrity` (connected blocks / all blocks)
stays above 0.90 after the release.

## Telemetry inputs (per sample, 25 Hz, from `ControllerClient.next_sample`)
Root block position, rotation quaternion, velocity, angular velocity; fuel of the booster; `machine_integrity`;
positions of the payload blocks (revolution counting after separation). Derived in `fsw/nav.py`: radius r from the
planet centre (0,−600,0), local vertical n, altitude, radial speed vr, horizontal velocity vh/vt (referred to the centre
of mass), gravity min(22, μ/r²), drag coefficient, height h above the resting height on the pad, great-circle surface
distance and direction to the launch point (`pad_dist`, `pad_dir`), apsides of the osculating orbit.

## Control outputs (all re-sent every tick; commands expire after ~1 s)
- Steering Thrusters: `LeftKey` / `RightKey` (on/off). Thrust level by switching symmetric, torque-free groups of four
  ("quads", outermost first) with sigma-delta dithering (`Flight.lift_allocate`). Idle thrusters hold both keys in flight.
- Flying Blocks: `FlyKey` + `speed` slider (continuous), used only for the part of the demanded force that the thrusters
  cannot give.
- Reaction Steering Blocks: `speed` slider + `RightKey`, `damper` slider = 0 (own stabiliser off). Each axis is a
  *biased pair*: both wheels spin, the torque is proportional to the speed difference (no dead zone).
- Tip thrusters: bang-bang roll-rate damping with dead band (`roll_cmd`).
- Booster: `fthrust` slider + `ThrustKey` (token burn only). Decoupler: `ExplodeKey` (payload release).

## Attitude control (`fsw/attitude.py`)
Thrust-axis pointing: error vector between body +Y and the commanded direction → rate command (kp, limited to
`att_rate_max`) → torque = kd·(rate_cmd − rate) + `att_damp_ff`·rate_cmd + ki·∫error. The feed-forward term cancels the
rotational damping that the Steering Thrusters' built-in stabiliser adds (measured ≈ 4 1/s). Wheel gains
(rad/s² per unit speed difference) are switched from `wheel_gain_loaded` to `wheel_gain_empty` at payload release.
Engines are inhibited while the pointing error exceeds 25°.
**Thruster assist** (`att_assist`): the big raft is too heavy for the four wheels alone (the thrusters' built-in
stabiliser damps every rotation). When the rate error of the pointing loop exceeds a threshold, outer lift thrusters of
two opposite arms are used, bang-bang with hysteresis:
- payload attached (`assist_n` = 10 thrusters per arm, thresholds `assist_on`/`assist_off`, only above 300 altitude and
  only while the lift engines are idle, i.e. for the turn between engine cut-off and apoapsis and before the release):
  the two arms fire in opposite directions = pure torque;
- empty vehicle (`assist_n_empty` = 4 thrusters per arm, thresholds `assist_on_empty`/`assist_off_empty`): pure couple
  when the engines are idle, **differential thrust** when they are on (the tip thrusters of one arm forced on, those of
  the opposite arm switched off). Only four thrusters are used because large couples over-stress the long arms of the
  light empty vehicle.
During the fly-back (after the first alignment) and the landing the commanded axis is slew-rate limited
(`cruise_slew_deg`, `cmd_slew_deg` = 7°/s) so that the pointing error stays small and the engines are never inhibited
while the tilt reverses; while the descent thrust is still small (`a_up` < `tilt_aup_ref`) the tilt is limited to
`tilt_low_deg`.

## Mission phases and transitions (`fsw/mission_orbit.py`)
1. **PRE** (1 s): hold; abort if `machine_integrity` < 0.999. Rest height is recorded.
2. **ASCENT** (`fsw/guidance.py`, closed loop on measured r, vr, vt):
   - CLIMB: vertical, then pitch programme (0 → `beta_max` between `h1` and `h2`); proportional hold of the climb speed
     (`v_ax` + `v_gain_alt`·(alt − `v_alt0`)); token booster burn above 30 altitude; stall guard (lands if the climb stops).
   - BOOST/COAST: when the predicted coast apoapsis reaches `ra1` the engines stop; the vehicle turns prograde and coasts.
   - CIRC: the burn is centred on the apoapsis (starts half a burn time before it, also when the apoapsis overshoots the
     target by up to `circ_ap_margin`). Thrust along the velocity-to-go vector (target: circular speed at the current
     radius, zero radial speed, gravity loss of the remaining burn compensated); when the remainder is small the axis
     stays near prograde. Once the circular speed is reached no prograde speed is ever added: only a remaining sink
     rate (> `vr_ok`) is corrected with nearly radial thrust.
   - ORBIT when periapsis ≥ `rp_ok`, or velocity-to-go ≈ 0 / fast enough and not sinking with periapsis ≥ `rp_min`
     (last resort after `circ_timeout`: periapsis ≥ `rp_floor`). Target orbit radius ≈ 1280–1340 (gate is r = 1100).
3. **RELEASE**: point prograde; when the pointing error < 8° and the rate is small (or after 8 s) fire the Decoupler for
   0.6 s. The payload leaves prograde (raises its orbit). Revolutions of the payload are counted from this instant
   (angle of the payload centroid around the planet centre, unwrapped; minimum radius of any payload block is tracked).
   0.8 s later the launcher backs away with its reverse nozzles (`backoff_acc`, attitude still prograde) so that its
   arms cannot touch the slowly departing payload when it turns.
4. **RETURN** (`post_release_wait` after release, still in orbit): powered fly-back. `Flight.landing_cmd` with the
   `cruise` parameter set: horizontal velocity command towards the pad (`lat_kp`·distance, limited to `lat_vmax`),
   altitude hold at the cruise altitude with the centrifugal term (g − vt²/r), tilt limit 60°. The vehicle first turns
   (engines inhibited, no fall because it is still in orbit), then brakes, descends to the cruise altitude and flies back.
   **The cruise altitude is 480…500 (r ≈ 1100): above the atmosphere but at least 100 below the payload's orbit**, because
   the launch pad lies in the orbit plane and the payload passes over it again one period later (a vehicle hovering at
   the release altitude would be in its path). Exit when `pad_dist` < 15 and vt < 6.
5. **DROP / landing**: same law with landing parameters: descent-rate profile −min(`v_desc_max`, √(2·`a_brake`·(h −
   `h_flare`) + `v_touch`²)), PI on vertical speed, lateral PD on the pad offset (`lat_kp`, `lat_kd`), tilt limit 20°;
   holds at h ≈ 5 until `pad_dist` ≤ `pad_tol` and the horizontal speed < `commit_vt`, then commits to the touchdown
   (only broken off if the offset exceeds `pad_tol_abort`; after `gate_timeout` the tolerance is widened so that it never
   hovers for ever). After the release the pointing loop gain is raised (`att_kp_empty`) for the lighter vehicle.
   Touchdown = h < `h_cut` (or standing still below h = 1 for 1.5 s) → everything off.
6. **LANDED**: 3 s after touchdown every key is released (no thrust at all, vehicle at rest on its legs). The controller
   waits until the payload has completed `revs_required` (3.08) revolutions since separation and the vehicle has been
   down ≥ 15 s, then ends ("MISSION COMPLETE"). `reproduce.py` keeps the simulation running a few seconds longer.

## Key thresholds / tuned parameters
All numeric values are in the configuration file named in `mission.json` (`config_v3j.json` for the final machine): masses, thruster and
fan force model (`rcs_force`, `fan_force`, `fan_ceiling`, `fan_vmax`), wheel gains, attitude gains (`att_kp` 1.5,
`att_kd` 3.0, `att_ki` 2.5, `att_damp_ff` 4.0, `att_rate_max` / `att_rate_max_empty`, assist block), ascent block (`h1` 250, `h2` 520, `beta_max` 30°, `v_ax` 35, `ra1` =
`rc_target` 1320, `rp_ok` 1270, `rp_min` 1215, `circ_ap_margin` 80), landing block (`a_brake`, `v_touch`, `h_gate` 8, `pad_tol` 2.5, `lat_kp` 0.25,
`lat_kd` 0.7, `vz_kp` 1.5, `vz_ki` 2), fly-back block (`cruise`), `revs_required` 3.08, `t_max` 1500 s (simulation time).

## Robustness
Every phase transition depends on measured state (apsides, pointing error, distance, speed), not on elapsed time; the
loop tolerates telemetry stalls; time-outs exist only as safety nets. Margins: payload orbit ≈ 150–200 above the gate radius,
return flown above the atmosphere and below the payload's orbit, descent speed-limited, landing commit hysteresis,
gate time-out, stall guard.

## Completion criteria
Payload ≥ 3.08 revolutions in one continuous post-separation segment with minimum radius > 1100 (checked on every payload
block), payload still in free orbit; launcher at rest on the pad (all keys released) with `machine_integrity` ≥ 0.90.

## Files
`controller.py` (entry), `fsw/` (core, nav, attitude, guidance, vehicle, missions), `config_*.json`, `mission.json`,
`reproduce.py`, `machine.bsg` (+ `machines/` earlier versions), `declaration.json`, `tools/` (analysis scripts),
`sim/` (offline ascent model), `probes/` (early characterisation controllers).
