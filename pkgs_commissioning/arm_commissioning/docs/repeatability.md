# repeatability_node

> **Status: Work in progress.** This tool is not finished. The motion
> sequence, logging, and plotting work end-to-end, but the metrics and
> feedback path have not been validated against a known reference.
> Results should be treated as indicative only.

Measures the positional spread of a single servo by cycling it `N`
times between two poses. Captures the combined effect of backlash,
mechanical play, and the servo controller's positional noise. Output is
CSV and PNG.

## Prerequisites

See the [package README](../README.md). In addition:

- The servo must have `feedback_enabled: true` in its JSON config.
- Pose A and pose B must be mechanically safe — the joint will move
  back and forth `cycles` × 2 times.

## Run

The example below measures repeatability on the left shoulder pitch
joint between 0° and 20°. Replace `joint_name` with the joint to
characterise, and adjust the poses and cycle count as needed.

```bash
ros2 run arm_commissioning repeatability_node --ros-args \
    -p joint_name:=joint_left_shoulder_pitch \
    -p pose_a_deg:=0.0 \
    -p pose_b_deg:=20.0 \
    -p cycles:=10 \
    -p hold_s:=1.5
```

See [calibration_tool.md](calibration_tool.md#available-joints) for the
full list of joint names per config file.

## Parameters

**`joint_name`** (required)
Joint name from `/joint_states`.

**`pose_a_deg`** (default: `0.0`)
Pose A in logical angle, delta from `default_position`.

**`pose_b_deg`** (default: `20.0`)
Pose B.

**`cycles`** (default: `10`)
Number of back-and-forth cycles.

**`hold_s`** (default: `1.5`)
Hold time per pose. Must exceed the servo's settling time.

**`publish_rate`** (default: `50.0`)
Frequency in Hz at which the command is re-published.

**`output_dir`** (default: `~/humanoid_ws/test_results`)
Root output directory.

## Output

`<output_dir>/<YYYY-MM-DD>/<joint>/<stamp>_repeat.csv` with the final
position per cycle per pose.

`<...>_repeat.png` containing:

- Scatter plot of measurements per pose
- Standard deviation and min/max shown as horizontal lines
- Inset text box with the aggregate statistics

## Computed metrics

**`n_cycles`**
Number of completed cycles.

**`pose_a_mean_deg` / `pose_b_mean_deg`**
Actual mean position per pose.

**`pose_a_std_deg` / `pose_b_std_deg`**
Standard deviation per pose.

**`pose_a_max_dev_deg` / `pose_b_max_dev_deg`**
Maximum deviation from the mean per pose.

## Interpretation

- **Std < 0.1°**: at the limit of the ST3215.
- **Std 0.1–0.5°**: typical for a 3D-printed joint with moderate backlash.
- **Std > 1°**: mechanical issue, e.g. loose gearing or slipping coupling.
- **Large mean difference between pose A and pose B**: a constant load
  (gravity, spring) pulls the joint consistently towards one side.

## Suggested test batch

Run pose pairs covering the joint's working range to document
repeatability across the full motion interval.

```bash
# Small motion
ros2 run arm_commissioning repeatability_node --ros-args \
    -p joint_name:=joint_left_shoulder_pitch \
    -p pose_a_deg:=0 -p pose_b_deg:=5 -p cycles:=10

# Medium
ros2 run arm_commissioning repeatability_node --ros-args \
    -p joint_name:=joint_left_shoulder_pitch \
    -p pose_a_deg:=0 -p pose_b_deg:=20 -p cycles:=10

# Large
ros2 run arm_commissioning repeatability_node --ros-args \
    -p joint_name:=joint_left_shoulder_pitch \
    -p pose_a_deg:=-30 -p pose_b_deg:=30 -p cycles:=10
```
