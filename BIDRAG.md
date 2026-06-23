# Mine bidrag til repo'et

Denne fil giver et hurtigt overblik over hvad **jeg (Alex)** har tilføjet
eller ændret oven på den oprindelige `main`-baseline. Bruges til at finde
relevante filer hurtigt under eksamen.

Branch: `alex/min-opgave` (29 commits oven på `main`).

---

## 1. Helt ny pakke: `arm_commissioning`

Min største enkeltbidrag. En ny ROS 2-pakke under
`pkgs_commissioning/arm_commissioning/` med fem værktøjer til
idriftsættelse og test af én robot-arm:

- **`calibration_tool_node`** — interaktivt tastatur-værktøj til at finde
  `angle_software_min`, `angle_software_max` og `default_position` pr.
  servo. Skriver direkte til JSON-config og laver `.bak.<timestamp>`.
- **`step_response_node`** *(WIP)* — måler rise time, overshoot,
  settling time pr. servo. CSV + PNG output.
- **`repeatability_node`** *(WIP)* — måler positions-spredning over `N`
  cyklusser mellem to poses.
- **`power_monitor_node`** *(WIP)* — log og live-visning af strømforbrug
  pr. servo (`/servo_power`).
- **`launcher_gui`** — Tkinter control panel der starter hele stakken
  (ZED, servoer, animationer m.m.) fra ét vindue. Faste USB-porte,
  zenity ASKPASS, per-service log-faner, Animationer-fane med 18
  forindstillede CSV'er, Manuel slider-kontrol entry.

**Filer:**
- `pkgs_commissioning/arm_commissioning/arm_commissioning/*.py` (5 noder)
- `pkgs_commissioning/arm_commissioning/docs/*.md` (5 værktøjs-docs)
- `pkgs_commissioning/arm_commissioning/README.md`
- `pkgs_commissioning/arm_commissioning/package.xml`, `setup.py`,
  `setup.cfg`, `resource/`

**Vigtigste commits:**
- `3f05c39` — første version af pakken + calibration_tool
- `885aa06` — step_response + repeatability test noder
- `2ea1b48` — power_monitor + live viewer
- `f0c9af4` — launcher_gui (Tkinter)
- `7598498` — split docs i per-tool filer

---

## 2. Hardware setup-automation

Nye filer under `scripts/setup/` der dækker opsætning af en frisk
Jetson Orin Nano og kloning af ESP32-firmware.

- `scripts/setup/setup-orin-nano.sh` — idempotent post-flash script
  (ROS 2 install, dialout, rosdep, colcon build, by-path verifikation).
- `scripts/setup/clone-esp32.sh` — `esptool`-wrapper til read / write /
  verify af ESP32-firmware.
- `scripts/setup/HARDWARE_SETUP.md` — komplet trin-for-trin procedure
  fra JetPack-flash til fuld bringup.

**Commit:** `1c641a6`

---

## 3. Ændringer i eksisterende kode

### `pkgs_control/servo_control/`

- `wattson_servo_manager_node.py` — flere ændringer:
  - Skiftet til `/dev/serial/by-path/` så USB-port-tildeling er stabil
    (commit `9a1c988`).
  - Per-servo `voltage` / `current` / `power` telemetry på
    `/servo_power` topic (commit `2ea1b48`).
  - Fjernet `_publish_feedback` / `_publish_power` fra control-loop som
    regressions-fix for bus-throughput (commit `9e5e4da`).
  - Animation loop-flag + ret syntaks-corruption (commit `29ca1a5`).
- `src/servo_control.py` — mindre justeringer ifm. ovenstående.
- `src/driver_servos.py` — mindre justeringer.

### `pkgs_control/animation_player/`

- `animation_player_node.py` + `src/csv_reader.py` — fjernet uendelig
  loop-fejl (Bug 9 i REPORT_NOTES) og 30–60 s respons-lag i animationer
  (Bug 7).

### `pkgs_teleoperation/teleoperation/src/vuer_app.py`

- Wired Quest 3 teleop-flow (USB-C + `adb reverse`).

### `pkgs_control/elrik_kdl_kinematics/`

- Mindre justeringer ifm. teleop.

### `energirobotter_bringup/launch/robot/servos.launch.py`

- Revert til 10 Hz control_frequency (commit `d1ca285`).

### Servo configs (`wattson_description/servo_configs/`)

- L+R shoulder_pitch, shoulder_roll, arm_yaw `default_position`
  justeret.
- L+R wrist_pitch `dir` flippet (-1 → 1) for finger_guns-animation.
- Hand configs uddifferentieret pr. finger.

---

## 4. README + dokumentation

- `README.md` (rod) — udvidet med "Bringing up the robot for Slider
  Control" (DHCP-procedure, USB-port-mapping), "Playing pre-recorded
  animations", "Teleoperation with Quest 3 (wired)" (Scenario A og B).
- `pkgs_commissioning/arm_commissioning/README.md` + alle docs/
  i samme pakke (omskrevet til engelsk + WIP-markeringer for
  step_response, repeatability, power_monitor).
- `scripts/setup/HARDWARE_SETUP.md` (ny, omskrevet til engelsk).
- `Animation_Commands.md` (dansk cheat sheet til at starte
  animationer i SSH).
- `REPORT_NOTES.md` (privat arbejdslog — bugs, iterationer,
  beslutninger).

---

## 5. Hvor finder jeg hvad?

**Hele min nye kode**
`pkgs_commissioning/arm_commissioning/`

**GUI til at starte hele robotten**
`pkgs_commissioning/arm_commissioning/arm_commissioning/launcher_gui_node.py`

**Servo-kalibrering**
`pkgs_commissioning/arm_commissioning/arm_commissioning/calibration_tool_node.py`

**Servo configs (aktive)**
`wattson_description/servo_configs/*.json`

**Hardware setup-script (Jetson)**
`scripts/setup/setup-orin-nano.sh`

**ESP32 firmware-klon**
`scripts/setup/clone-esp32.sh`

**Hardware setup-guide**
`scripts/setup/HARDWARE_SETUP.md`

**Mit private arbejdslog**
`REPORT_NOTES.md`

**Animation cheat sheet**
`Animation_Commands.md`

**Arkitektur-overblik**
`ARKITEKTUR.md`

**Eksamens-oplæg**
`EKSAMEN_OPLAEG.md`

---

## 6. Komplet commit-historik (`main..alex/min-opgave`)

```
1c641a6  scripts/setup: setup-orin-nano.sh, clone-esp32.sh, HARDWARE_SETUP.md
9b5d083  launcher_gui: Manuel slider-kontrol entry under Demo
a938bd3  launcher_gui: loop kun animation_/mimic_ (Sekvenser-gruppen)
9e5e4da  servo_manager: fjern _publish_feedback/_publish_power fra control-loop
13c021a  launcher_gui: udled loop fra CSV-præfiks i stedet for hardkodet liste
d1ca285  drop power_monitor fra launcher_GUI; revert servos.launch til 10Hz
4358efb  REPORT_NOTES: Bug 8 (servo_manager corruption) + Bug 9 (csv_reader loop)
29ca1a5  wattson_servo_manager: ret syntaks-corruption + animation loop-flag
231d7ce  REPORT_NOTES: Bug 7 (animation respons-lag)
88a66e3  launcher_gui: fjern 30-60s respons-lag i animationer
1cfddd9  REPORT_NOTES: Bug 6 (gentagne password-prompts)
5ac6069  launcher_gui: drop gentagne password-prompts
be44bce  REPORT_NOTES: UX-iteration 2 (Animationer-fane)
ad72387  launcher_gui: Animationer-fane med 18 forindstillede animationer
b09cc38  launcher_gui: fix quoting i JETSON_SOURCES zed_wrapper-fallback
f69eb36  launcher_gui: source zed_wrapper_ws eksplicit på Jetson
8a7cb02  launcher_gui: fix power_monitor param-type og Jetson cwd
ed0e190  REPORT_NOTES: iterationer på launcher GUI (§6.9.1)
47c55ef  launcher_gui: zenity ASKPASS + per-service log-faner
1964712  launcher_gui: fix close-hang + stop-cmd for root-ejede services
0cb9521  REPORT_NOTES: §6.7 timer-race, §6.8 power monitor, §6.9 launcher GUI
c8cde61  launcher_gui: opdater checklist til faste USB-porte + auto Serial Forwarding
f0c9af4  arm_commissioning: tkinter demo launcher GUI
7598498  arm_commissioning: split docs into per-tool files under docs/
2ea1b48  power_monitor: per-servo voltage/current/power telemetry + live viewer
cb803f0  docs: wired Quest 3 teleop guide, report notes, animation commands
885aa06  arm_commissioning: add step_response and repeatability test nodes
9a1c988  servo_control: use /dev/serial/by-path/ for stable USB port assignment
3f05c39  Add arm_commissioning package with calibration tool
```
