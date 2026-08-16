# R.O.B.I.E. Dissertation Evidence Bank
Living document. Last updated 16 Aug 2026.
Every entry: what we have, where it goes, how to frame it, and the committed
artefact that proves it. Adapt the quoted "framing" lines into academic prose
when drafting. Add new entries as real-hardware results arrive (Weeks 5-6).

---

## 1. Simulation-first digital-twin methodology
- Evidence: Gaussian plume simulator (plume_sim) + sensor/EMA model + full
  state-machine clone (gas_climber) running headless in CI-style batches.
- Chapter: Methodology.
- Framing: "Before committing to hardware, the detection behaviour of the
  gas-seeking controller was characterised against a parametric plume model,
  allowing sensor dynamics and control parameters to be studied in isolation
  from mechanical risk."
- Figure idea: block diagram of the digital twin (plume -> raw sensor -> EMA
  -> state machine -> odometry loop).
- Artefact: src/robie_gas (plume_sim.py, gas_climber.py).

## 2. Gas source-seeking algorithm: design iterations v1-v3
- Evidence: state machine PATROL->DRIVE->TURN->HOME->LOCALISED; naive
  gradient climb (v1) failed on noise/local maxima; v3 adds home-and-cast
  angular probing, best-position memory, fail-count termination.
- Chapter: Methods / Implementation.
- Framing: present as iterative design: state the failure mode of each
  version, then the mechanism that fixes it. Examiners reward documented
  iteration more than a perfect first attempt.
- Figure idea: state-transition diagram drawn straight from the STATES.
- Artefact: gas_climber.py, git history (commit messages tell the story).

## 3. Automated ROC evaluation harness (180-run factorial design)
- Evidence: 6 thresholds x 5 noise levels x leak present/absent x 3 repeats;
  offline parser computes TP/FP/FN/TN and plots the ROC curve.
- Chapter: Results + Verification & Validation.
- Framing: "Detection performance was evaluated as a binary classifier over
  a factorial parameter sweep, yielding receiver-operating-characteristic
  curves that expose the sensitivity/specificity trade-off of the detection
  threshold."
- Figure idea: the ROC PNG (roc_curve_final.png), annotated per threshold.
- Artefact: roc_harness.py, parse_roc.py, logs/roc/run_*.csv.

## 4. HEADLINE FINDING: patrol speed vs sensor integration time
- Evidence: TPR collapses between threshold 50 (0.33) and 100 (0.0) at
  0.15 m/s: the EMA-smoothed reading cannot climb to the threshold before
  the robot drives out of the plume.
- Chapter: Results/Discussion - this is your standout systems-engineering
  insight.
- Framing: "The ROC analysis reveals a hard physical constraint: due to the
  slow response of MOX-type sensors (modelled as a first-order EMA filter),
  the UGV cannot reliably trigger detection above a threshold of ~50-75 ADC
  counts while patrolling at 0.15 m/s. Higher thresholds (lower false-alarm
  rates) require either reduced patrol speed or faster sensor exchange."
- Figure idea: EMA step-response sketch showing raw vs smoothed reading
  crossing 50 but never 100 during a plume transit.
- Artefact: ROC summary table (threshold 50 vs 100 rows).

## 5. Simulation-driven hardware change: active sampling pump
- Evidence: Finding 4 implies the fix is airflow, not code; a 5 V micro
  diaphragm pump specified to reduce the sensor time constant.
- Chapter: Discussion / hardware design rationale; also Future Work.
- Framing: "Simulation identified sensor transport delay as the dominant
  bottleneck; an active sampling pump was therefore specified. A before/after
  step-response test will fit a new time constant, which is fed back into the
  simulator to predict the shifted ROC curve - closing the sim-to-real loop."
- Figure idea (later): paired ROC curves, pump off vs pump on.
- Artefact: parts list addition; bench experiment planned (Week 2).

## 6. Layered control and safety architecture
- Evidence: brain (Pi: nav/gas), spine (ESP32 firmware), nervous system
  (safety_node), muscles (mecanum_driver + motor_arbiter); custom messages
  as interface contracts; /motor_targets only non-zero when /motor_enable.
- Chapter: System Architecture; map directly onto your SysML BDD/IBD blocks.
- Framing: "Safety is enforced by construction: a dedicated interlock node
  and a final arbiter gate sit between any command source and the actuators,
  so no software path can drive the motors without an explicit enable."
- Figure idea: ROS node/topic graph - use the actual `ros2 topic list`
  output as the authoritative edge list.
- Artefact: robie_msgs, robie_nav, robie_safety, robie_hardware packages.

## 7. Fail-safe interlock, proven by unit tests
- Evidence: motors default DISABLED; E-stop overrides all; RF-loss and
  bumper faults cut power; 6 logic tests pass; firmware ALSO hard-cuts on
  E-stop independently of the Pi (defence in depth).
- Chapter: V&V + Safety case section.
- Framing: "The interlock was verified by property-based unit tests
  asserting that no combination of inputs can enable the motors while the
  E-stop is asserted; the same property is enforced a second time in
  firmware, providing two independent safety layers."
- Table idea: test name -> property asserted -> pass/fail.
- Artefact: test_safety_logic.py, firmware src/main.cpp interlock line.

## 8. Mecanum inverse kinematics with ratio-preserving clamp
- Evidence: closed-form IK; saturation scales all four wheels equally so
  commanded heading is preserved under limits; sign patterns unit-tested.
- Chapter: Implementation.
- Framing: short equations block + "clamping preserves the direction of the
  resultant velocity vector"; note sign convention to be confirmed on bench.
- Artefact: mecanum_driver.py, test_mecanum.py.

## 9. Serial protocol contract and the micro-ROS decision
- Evidence: line-based 115200-baud protocol (M/S down, T/H up) mirrored in
  firmware and bridge codec with shared unit tests; micro-ROS consciously
  deferred.
- Chapter: Architecture decisions + Future Work.
- Framing: "A deterministic, human-readable serial protocol was chosen for
  v1 to maximise debuggability and minimise integration risk on the project
  timeline; micro-ROS remains a defined upgrade path once the safety case is
  closed." (Trade-off justification = marks.)
- Artefact: serial_protocol.py, firmware main.cpp header comment.

## 10. V&V lesson: debug the rig before trusting its verdicts
- Evidence: (a) 60 s hard-kill truncated climbs, so a broken harness scored
  a good algorithm as failing; (b) parser graded the FIRST LOCALISED line
  (a startup glitch at x=30,y=69) instead of the closest, hiding real
  successes.
- Chapter: V&V chapter or testing appendix.
- Framing: "Two independent harness defects initially produced false
  negative verdicts; the harness was therefore validated against known-good
  manual runs before batch results were trusted. Test infrastructure is
  itself a system under test."
- Artefact: git history of roc_harness.py / parse_roc.py fixes.

## 11. Operations finding: DDS transport degradation under batch load
- Evidence: 180 SIGKILLed nodes left 636 zombie SHM ports in /dev/shm;
  discovery failed cluster-wide; fixed by wiping ports and pinning a
  UDP-only FastDDS profile via config-as-code (setup_env.sh).
- Chapter: Appendix (environment) or V&V lessons.
- Framing: "Stress testing exposed a middleware failure mode: forcibly
  terminated nodes leaked shared-memory segments, degrading discovery. The
  mitigation - a UDP-only transport profile deployed by script - is checked
  into the repository, making the environment reproducible."
- Artefact: scripts/setup_env.sh, scripts/fastrtps_udp_only.xml.

## 12. Project management: procurement as critical path
- Evidence: parts form + email submitted Day 1; software workstreams
  deliberately parallelised against procurement lead time; weekly plan to
  26 Oct with two weeks of writing buffer.
- Chapter: Project Management chapter.
- Framing: risk-register style: risk = component lead time; mitigation =
  simulation-first development and hardware-independent software layers.
- Artefact: this plan; email timestamps.

---

## Figures still to produce
1. State-machine diagram (from gas_climber STATES).
2. ROS node/topic graph (from live `ros2 topic list` + `ros2 graph`).
3. EMA step-response sketch (Finding 4).
4. Pump off/on paired ROC curves (after Week 2 bench test).
5. Real-hardware ROC (Week 6) beside the simulated ROC.

## 13. Silent-failure watchdog (fail-safe on telemetry loss)
- Evidence: safety_node forces motors off if no /hw/rf_alive heartbeat for
  2.0 s; demonstrated in SITL by killing mock_bridge: log shows
  "HEARTBEAT TIMEOUT -> Cutting power" and /motor_enable flips to false
  with no human intervention.
- Chapter: V&V / safety case.
- Framing: "The interlock treats absence of telemetry as a fault: a
  watchdog timeout converts silent co-processor failure into a safe stop,
  closing the classic 'last known good value' hazard."
- Artefact: robie_safety/safety_node.py (watchdog), robie_hardware/mock_bridge.py (SITL demo).
