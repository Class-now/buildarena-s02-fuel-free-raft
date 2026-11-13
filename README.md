# Fuel-free Raft: 25.23-mass inert payload to orbit, launcher lands back on the pad (machine file: s02_orbiter, lifespan s02_orbiter_261113_092827)

## Track

Build with Agents, **Autopilot** mode. One AI agent (with build-only sub-agents of the same model, see LLM / Agent Setup) designed, built, controlled, tested and iterated the whole mission. No human gave any instruction, hint or correction after Engineering Start.

## Mission Summary

A single, fully reusable launcher that burns (almost) no fuel lifts an inert stack of fly wheels to a near-circular orbit at r ≈ 1276–1341, releases it prograde, flies back above the atmosphere and lands on its legs on the launch point.

- **Payload:** one Decoupler (leaves with the payload) plus a stack of 19 unpowered Fly Wheels. 20 blocks, dry mass 25.23. No propulsion, propellant or thrust-producing block.
- **Launcher ("raft"):** 208 blocks, dry mass 60.36. A cross of four arms of eight Wooden Poles each, braced into rings. Thrust comes from 124 Steering Thrusters mounted flat on the arm poles (they need no fuel in Besiege) and, in the dense lower atmosphere only, 12 Flying Blocks. Attitude: four Reaction Steering Blocks on the hub, four tangential tip thrusters for roll damping. A vertical braced mast carries the payload. Eight Single Wooden Blocks are the landing legs.
- **Fuel:** one Booster with 1.0 fuel unit is fired once for about 0.1 s at minimum throttle (≈ 0.004 fuel units), so the expended fuel is finite and non-zero. It gives no useful impulse.
- No Automation, Surface or Parachute blocks. Everything except the payload comes home.

## Final Run

Final run `datacache/control_experiments/v3j_m10/runs/20261113-160516-7bfaca96`, flown by `control/reproduce.py` (one command, no manual input).

| Item | Value |
|---|---|
| Qualifying payload mass | 25.23 (20 blocks, inert) |
| Valid orbital revolutions | 3.08 after separation (controller count); the toolkit estimator finds 3.18 revolutions in one continuous segment. Payload still in free orbit at the end of the record |
| Minimum payload radius after separation | 1326.1 (gate: 1100) |
| Propellant expenditure | 0.004 of 1.0 fuel units (token burn of the single Booster) |
| Recovery completeness | 208 / 208 launcher blocks, intact, at rest on its legs (`machine_integrity` 0.912 = 208 of 228 blocks, the 20 payload blocks having left) |
| Recovered machines | 1 (single-stage launcher) |
| Landing error(s) | 1.1 m from the launch point, touchdown at about 1 m/s |
| Mission Time | orbit 1276 × 1341 at t = 39.9 s, separation at t = 40.9 s, launcher over the pad at t = 225.5 s, touchdown at t = 254.2 s, three revolutions complete at t ≈ 367 s (simulation time); record ends at 372.7 s with the launcher at rest for the last 110 s |

The same final code and machine passed five consecutive full missions (`v3j_m9` … `v3j_m13`): payload ≥ 3.08 revolutions after separation, minimum radius 1288–1328, landing 0.5–2.2 m from the pad, `machine_integrity` 0.912 each time. Numbers come from the controller's telemetry log and the toolkit's `tools/score_estimate.py` (unofficial estimate: gate passed, landing score 0.9994).

## Video

No video was recorded. The media gallery image shows the payload and launcher trajectories reconstructed from `trajectory.csv`.

## LLM / Agent Setup

- Model: Claude (`claude-fable-5-2`), effort `xhigh`. One main agent. It started eight sub-agents (Claude Code's general-purpose `Agent` tool, same model) only to execute long block-by-block construction jobs through the BuildArena MCP server ("extend arms to 8 poles", "rebuild tower with braced mast", …); the main agent wrote every design and all control code. The sub-agents' messages are part of `chat_transcript.md`.
- Runtime: Claude Code 2.1.322 in headless mode (`claude -p`), started by a small harness that freezes the pre-start materials, records every message, and resumes the agent with the fixed text "Continue the previous work." after an interruption.
- Tools: the BuildArena MCP server (building), `besiege_cli` (flight runs and telemetry), `tools/score_estimate.py`, shell and file tools inside the workspace. Web search and web fetch were disabled. No visual feedback (no screenshots or video) was used; the agent worked from telemetry only.
- No custom system prompt. Pre-start materials total 2,740 tokens (cl100k_base): `AGENTS.md` 2,618, initial instruction 117, resume text 5. They contain the mission rules, the scoring formula, the deadline and the working procedure, and no machine design, numbers or control code.
- Usage: 12 invocations; about 50 h wall clock from start to `FINAL.json`, of which about 26 h were the stop described in Notes (the agent was not running). The agent itself finished the design at about 26 h of active time and then waited for the `FINAL.json` window. 68 flight runs.
- API usage (including the restored section, see Notes): input 808, output 516,770, cache creation 2,033,304, cache read 196,007,298 tokens (`token_report.json`).

## Prompts and Workflow

The complete initial instruction and `AGENTS.md` are reproduced verbatim in the appendix of `chat_transcript.md`. The human side of the conversation consists of the initial instruction and eleven automatic "Continue the previous work." messages sent by the harness. The transcript without the appendix is 89,209 tokens.

The agent's own workflow: read the toolkit docs, measure masses, booster thrust, drag and fuel behaviour with probe machines, build the vehicle through MCP, write a phase-based flight software, fly, read the telemetry, fix one thing, fly again. It kept its own log in `NOTES.md` (in `control/`), kept a verified fallback snapshot at every step, and only replaced it after two passing runs with identical code.

## Control System

Closed loop on 25 Hz telemetry; every phase transition depends on measured state (apsides, pointing error, distance, speed), not on elapsed time. Full description in `control/CONTROL.md`, all constants in `control/config_v3j.json`.

- **State machine:** PRE → ASCENT (vertical climb, pitch programme, coast to apoapsis) → CIRC (burn centred on apoapsis along the velocity-to-go vector) → ORBIT → RELEASE (point prograde, fire the decoupler, back away) → RETURN (powered fly-back at altitude 480–500: above the atmosphere but at least 100 below the payload's orbit, because the pad lies in the orbit plane and the payload passes over it again) → DROP (descent-rate profile, PI on vertical speed, lateral PD on the pad offset, commit hysteresis) → LANDED (all keys released).
- **Actuators:** thrust level by switching torque-free groups of four Steering Thrusters with sigma-delta dithering; Flying Blocks for the part of the demand the thrusters cannot give; biased pairs of reaction wheels for pitch/yaw (no dead zone); bang-bang roll damping with the tip thrusters; differential thrust of opposite arms as a torque assist while the payload is attached.
- **Separation condition:** only in a verified orbit (periapsis above `rp_ok`, pointing error < 8°, rate settled), so the decoupler kick only raises the payload's orbit.
- **Pre-launch declaration:** `control/declaration.json` (every payload and launcher block with mass, fuel, launch-site target).

## Engineering Iteration

- First full mission with a conventional booster launcher (payload 1.65, 37 of 104 fuel units). Measuring blocks then showed that Steering Thrusters give about 9 force per nozzle with no fuel, independent of altitude and speed, and that Flying Blocks give fuel-free lift near the ground. The agent switched to a fuel-free "raft" and scaled it up step by step: payload 1.65 → 16.06 → 19.99 → 25.23, each step verified twice before it became the fallback.
- The central tower broke off at the hub joint under full thrust (the tower rocked as a rigid body inside the attitude loop): rebuilt as a vertical mast held by four king-post braces.
- Found from telemetry that a launcher hovering at the release altitude was hit by its own payload one orbit later (earlier "passes" had been near misses of 4–7 units): the fly-back now cruises at least 100 below the payload's orbit.
- An apoapsis overshoot made the circularisation run away to escape (prograde thrust kept on for a radial error): the burn is now centred on the real apoapsis and never adds prograde speed once the circular speed is reached.
- A 9-pole-arm version (29-mass payload) broke two arms during the turn of the empty vehicle with a large thrust couple: the agent stopped scaling at 8 poles and limits the couple assist to the loaded phase.
- Descent and cruise fixes (a dip to h = 22 during the fly-back, an oscillation of the light empty vehicle) before the final code, which then passed five runs in a row.

## Notes

Disclosures (all events are in `chat_transcript.md` and the harness log; times JST = UTC+9):

1. **Display incident (11/12 03:29–03:44).** The game's display settings switched to full screen on the PC owner's main monitor, and the game window was closed. The operator set the four display settings back to a 1280×720 window on the second monitor and ended the hung `besiege_cli` process. The agent restarted the game itself. No message was sent to the agent.
2. **Harness loss (11/12 03:53–05:04).** The harness process ended without a log line while the agent kept working. At 05:04 the operator stopped the orphaned agent process and the supervisor restarted the harness, which sent only "Continue the previous work." The harness record of 03:53–05:04 is missing; that section of `chat_transcript.md` was restored from Claude Code's own session log of the same session, and its token usage is added in `token_report.json`.
3. **Usage limit (11/12 07:27).** The model's usage limit was reached; the harness waited. The PC was then used for something else and rebooted, so the run resumed only on 11/13 09:10 (relaunched by the supervisor, resume text only). About 26 h without the agent running.
4. **Idle time-outs while waiting for the FINAL.json window (11/13 18:27–00:49).** After the final design was verified (17:42) the agent waited for the `FINAL.json` time window. The harness ends an invocation after 45 min without output and resumed it six times with "Continue the previous work."; two of these resumes failed with an API 403 (Cloudflare) error and were retried automatically.
5. **Audio check stall (11/13 21:41–23:16).** The PC was heavily loaded; the harness's audio check timed out and the harness ended the invocation, but the process tree hung. The operator finished the termination at 23:15 and the supervisor restarted the harness (resume text only). The agent was only waiting at that time.
6. **PC operation settings (no change to the agent, its workspace or the game).** To keep the single-threaded simulation fast while other programs ran, the operator pinned the game to logical CPUs 0–5 and moved other processes to CPUs 6–15, raised the game's process priority, kept the CPU boost on during the day, and, while the PC had only one monitor, moved the game window off-screen (not minimised). The simulation ran at 0.15–0.41× real time; the controller uses simulation time only.
7. **Earlier attempt.** A previous run of the same setup (s02-run2, effort not set) was stopped by the operator before its first mission because of harness problems; this run started from scratch with frozen materials and effort `xhigh`. No machine, number or code from earlier runs was given to this agent.
8. **Build history.** `machine.bsg` is the agent's saved version v3j. Its MCP build history is the first 352 operations of the lifespan `s02_orbiter_261113_092827` (the agent later continued that lifespan into a heavier v3k, which it rejected). `build_history.json` and `build_history_full.json` are cut at that point; the full histories of every lifespan of the run are in `extra_build_histories.zip`.
9. **Attachments.** `trajectory.csv` is 549 MB; it is attached as a 7-Zip (LZMA2) archive `trajectory.7z` (119.6 MB) split into 12 byte-volumes `trajectory.7z.001` … `.012` (≤ 9.9 MB each, the upload limit). Join them (`copy /b trajectory.7z.0* trajectory.7z` or `cat trajectory.7z.0* > trajectory.7z`) or open `.001` directly in 7-Zip. SHA-256: `trajectory.7z` 8157a3c862ce149389aa9ce3e6b0ca29646384c10246a2d51b85887b72130f12, `trajectory.csv` d987ebffba3dc55707a88e00470222f5afa9a4ccc096359ce6abf6d94fbbe154. The same archive is a release asset of the public repository. `control.zip` is the agent's `agent_control/` folder (with `NOTES.md`), and `token_report.json` the token counts.
