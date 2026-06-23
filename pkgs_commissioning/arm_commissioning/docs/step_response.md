# step_response_node

> **Status: Work in progress.** This tool is not finished. The data
> capture and plotting work end-to-end, but the metrics, tolerances,
> and feedback path have not been validated against a known reference.
> Results should be treated as indicative only.

Characterises the step response of a single ST3215 servo. Measures the
standard control-theory metrics (rise time, overshoot, settling time,
steady-state error) and writes them as CSV and PNG.

## Prerequisites

See the [package README](../README.md). In addition:

- The servo must have `feedback_enabled: true` in its JSON config.
  Without feedback the node receives no samples.
- The servo must be free to move `step_size_deg` from its current
  position without hitting anything.

## Run

The example below records a 10° step on the left shoulder pitch joint.
Replace `joint_name` with the joint to characterise, and adjust
`step_size_deg` and `duration_s` as needed.

```bash
ros2 run arm_commissioning step_response_node --ros-args \
    -p joint_name:=joint_left_shoulder_pitch \
    -p step_size_deg:=10.0 \
    -p duration_s:=3.0
```

See [calibration_tool.md](calibration_tool.md#available-joints) for the
full list of joint names per config file.

## Parameters

**`joint_name`** (required)
Joint name from `/joint_states`.

**`step_size_deg`** (default: `10.0`)
Step size in logical angle, i.e. delta from `default_position`.

**`baseline_s`** (default: `0.5`)
Hold time at 0° before the step is issued.

**`duration_s`** (default: `3.0`)
Total run time.

**`publish_rate`** (default: `50.0`)
Frequency in Hz at which the command is re-published.

**`settling_tol_pct`** (default: `10.0`)
Tolerance for settling time, as a percentage of the step amplitude.

**`output_dir`** (default: `~/humanoid_ws/test_results`)
Root output directory.

## Output

`<output_dir>/<YYYY-MM-DD>/<joint>/<stamp>_step.csv` with columns:

```
t_s, cmd_deg, actual_deg
```

`<...>_step.png` containing:

- Commanded vs. actual angle (normalised to delta from baseline)
- Step instant marked
- Inset text box with the computed metrics

## Computed metrics

**`rise_time_s`**
Time from 10 % to 90 % of the step amplitude. Indicates how sharp the
response is.

**`overshoot_pct`**
`(peak − target) / step × 100`. Indicates whether the PID is too
aggressive.

**`settling_time_s`**
Time before `|error|` stays within the tolerance band. Indicates how
long until the system is on target.

**`steady_state_error_deg`**
Final error after settling. Indicates static error (P gain too low).

**`baseline_phys_deg`**
Actual starting angle before the step. Context.

**`target_delta_deg`**
Commanded step. Context.

## Interpretation

- **Short rise time, no overshoot, small steady-state error**: good tuning.
- **Large overshoot and long settling**: P gain too high, D gain too low.
- **Large steady-state error without overshoot**: P gain too low. The
  ST3215 internal PID is not user-configurable, so this is a hardware
  limit.
- **No samples recorded**: `feedback_enabled` is false, or
  `wattson_servo_manager` is not publishing `/joint_states_feedback`.

## Suggested test batch

Run three steps per servo (small / medium / large) to verify that the
response scales sensibly:

```bash
for STEP in 5 10 20; do
  ros2 run arm_commissioning step_response_node --ros-args \
    -p joint_name:=joint_left_shoulder_pitch \
    -p step_size_deg:=$STEP \
    -p duration_s:=3.0
  sleep 2
done
```
