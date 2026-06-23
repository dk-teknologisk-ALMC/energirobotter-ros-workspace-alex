# power_monitor_node

> **Status: Work in progress.** This tool is not finished. The
> subscription, logging, and plotting work end-to-end, but the values
> and sign handling have not been validated against an external
> reference meter. Results should be treated as indicative only.

Live viewer and logger for the robot's power consumption (per-servo and
total). Produces CSV and PNG per scenario.

## What it measures

The ST3215 servos have a built-in shunt and report the following on the
bus:

**Voltage**
Register `PRESENT_VOLTAGE` (62). Resolution 0.1 V/unit.

**Current**
Registers `PRESENT_CURRENT_L/H` (69–70). Resolution 6.5 mA/unit,
bit 15 is the sign.

The servo-manager node exposes these values on the `/servo_power` topic
(see [Topic format](#topic-format)). This tool subscribes, computes
`P = V × I` per servo and total, and produces both live visualisation
and CSV/PNG output per scenario.

## Scope

The measurements cover the servo bus only. They do not include:

- Jetson Orin Nano (~10–15 W under teleop)
- ZED camera (~2–3 W additional)
- ESP32 and Wi-Fi
- 12 V to 5 V step-down conversion loss

For a full system power budget the node must be supplemented with an
external USB power meter at the main supply. Label the figures
accordingly (e.g. "servo bus power").

## Precision

The ST3215 current measurement has approximately 6.5 mA resolution and
the voltage measurement approximately 0.1 V. This is not
lab-instrument-grade precision, but is sufficient to distinguish idle
from active states (typically a 5×–10× difference) and to compare
iterations.

## Prerequisites

See the [package README](../README.md). In addition:

- All servos to be included in the measurement must have
  `feedback_enabled: true` in their JSON config.
- The live viewer (`live:=true`) requires X11. Run it on the laptop, not
  over SSH to the Jetson.
- Over SSH, use `live:=false` and copy the PNG afterwards.

## Run

### Live demo (with viewer)

```bash
ros2 run arm_commissioning power_monitor_node --ros-args \
    -p scenario:=idle \
    -p duration_s:=30.0 \
    -p live:=true
```

A matplotlib window opens with:

- Top: total W over the last `live_window_s` seconds (default 20 s).
- Bottom: per-servo bar chart, updated live.

### Headless (CSV and PNG only)

```bash
ros2 run arm_commissioning power_monitor_node --ros-args \
    -p scenario:=animation_idle1 \
    -p duration_s:=60.0 \
    -p live:=false
```

### Manual stop

`Ctrl-C` writes CSV and PNG with whatever has been collected so far. It
is not necessary to wait for `duration_s` to elapse.

## Parameters

**`scenario`** (default: `default`)
Output folder name. Use descriptive names such as `idle`,
`animation_wave`, or `teleop`.

**`duration_s`** (default: `30.0`)
Auto-stop time in seconds.

**`live`** (default: `true`)
Open the matplotlib live viewer.

**`live_window_s`** (default: `20.0`)
Width of the rolling window in the viewer.

**`output_dir`** (default: `~/humanoid_ws/test_results`)
Root output directory.

## Output

`<output_dir>/<YYYY-MM-DD>/<scenario>/<stamp>_power.csv` with columns:

```
t_s, V_<servo1>, V_<servo2>..., A_<servo1>..., W_<servo1>..., total_W
```

`<...>_power.png` containing:

- Top: total W over the full run, with an average line and a statistics
  box.
- Bottom: top 12 current consumers as a horizontal bar chart.

A summary is printed to the terminal:

```
=== Power summary (idle) ===
  duration        = 30.04 s (598 samples)
  mean W          =  6.81
  peak W          = 10.42
  min W           =  5.83
  std W           =  0.71
  top 5 (avg W per servo):
      1.42  joint_left_shoulder_pitch
      1.31  joint_left_shoulder_roll
      ...
```

## Suggested test scenarios

To produce a meaningful power budget table, run the same `duration_s`
for each scenario and compare.

**`idle`**
Robot holds the default pose, no commands are sent. Shows the static
holding current as the PID compensates against gravity.

**`holding_extended`**
Arm extended into a heavy pose, held. Shows the maximum static load.

**`animation_idle1`**
Run `idle1.csv` animation. Shows typical "alive" consumption.

**`animation_wave`**
Run an active animation. Shows higher dynamic consumption.

**`step_test`**
Run concurrently with `step_response_node`. Shows the transient peak
during fast motion.

**`teleop_calm`**
Quest 3 teleop, small movements. Realistic teleop budget.

**`teleop_active`**
Quest 3 teleop, large movements. Worst-case teleop.

### Example — idle vs. active

```bash
# Terminal 1: servo stack running
ros2 launch energirobotter_bringup servos.launch.py

# Terminal 2: idle baseline (30 s)
ros2 run arm_commissioning power_monitor_node --ros-args \
    -p scenario:=idle -p duration_s:=30.0 -p live:=false

# Terminal 3 (after idle finishes): start an animation
ros2 launch energirobotter_bringup animation.launch.py csv_file:=idle1

# Terminal 2: run the same measurement during the animation
ros2 run arm_commissioning power_monitor_node --ros-args \
    -p scenario:=animation_idle1 -p duration_s:=30.0 -p live:=false
```

The result is two PNGs and two CSVs that can be compared side by side.

## Topic format

`/servo_power` is a `sensor_msgs/msg/JointState` where the fields are
repurposed:

**`name[i]`**
Servo name.

**`position[i]`**
Voltage, in V.

**`velocity[i]`**
Current (signed), in A.

**`effort[i]`**
Power, in W.

## Troubleshooting

**No `/servo_power` samples received**
Check with `ros2 topic hz /servo_power`. Expected rate is ~10 Hz
(equal to `control_frequency` in the servo manager).

**All W values are zero**
`feedback_enabled` is `false` in the servo config, or the servos are
not responding (cable or USB port issue).

**Negative W on individual servos**
Physically correct under regenerative load (a servo braking a falling
arm). If all values are negative, the sign handling is likely inverted
for the current firmware version.

**Live viewer does not open**
Verify the command is running on the laptop (not over SSH) and that
`python3-tk` is installed (`sudo apt install python3-tk`).
