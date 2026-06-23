# calibration_tool_node

Interactive keyboard tool for setting `angle_software_min`,
`angle_software_max`, and `default_position` on a single servo. Values are
written back to the servo's JSON config; the previous file is preserved as
`.bak.<timestamp>`.

## Prerequisites

See the [package README](../README.md). No other publisher may be active
on `/joint_states`.

## Run

The example below calibrates the left shoulder pitch joint. Replace
`joint_name` with the joint being calibrated, and `config_file` with the
matching JSON config (left arm, right arm, head, or hand).

```bash
ros2 run arm_commissioning calibration_tool_node --ros-args \
  -p config_file:=$HOME/humanoid_ws/src/energirobotter-ros-workspace-alex/energirobotter_bringup/config/servos/servo_arm_left_params.json \
  -p joint_name:=joint_left_shoulder_pitch
```

The tool must be started with `ros2 run`, not `ros2 launch`. A real TTY
on stdin is required for keyboard input.

### Available joints

**`servo_arm_left_params.json`**
`joint_left_shoulder_pitch`, `joint_left_shoulder_roll`,
`joint_left_arm_yaw`, `joint_left_elbow_pitch`, `joint_left_forearm_yaw`,
`joint_left_wrist_pitch`, `joint_left_wrist_roll`

**`servo_arm_right_params.json`**
`joint_right_shoulder_pitch`, `joint_right_shoulder_roll`,
`joint_right_arm_yaw`, `joint_right_elbow_pitch`,
`joint_right_forearm_yaw`, `joint_right_wrist_pitch`,
`joint_right_wrist_roll`

**`servo_hand_left_params.json`**
`hand_left_pinky`, `hand_left_ring`, `hand_left_middle`,
`hand_left_index`, `hand_left_thumb`

**`servo_hand_right_params.json`**
`hand_right_pinky`, `hand_right_ring`, `hand_right_middle`,
`hand_right_index`, `hand_right_thumb`

**`servo_head_params.json`**
`joint_head_yaw`, `joint_head_pitch`

## Keys

| Key       | Action                                                     |
|-----------|------------------------------------------------------------|
| `a` / `d` | Step −1° / +1°                                             |
| `A` / `D` | Step −5° / +5°                                             |
| `z` / `c` | Step ±0.1° (fine adjustment)                               |
| `h`       | Home (return to the original `default_position`)           |
| SPACE     | Hold (re-publish the current position)                     |
| `[`       | Mark the current position as `angle_software_min`          |
| `]`       | Mark the current position as `angle_software_max`          |
| `0`       | Mark the current position as `default_position`            |
| `p`       | Print current state                                        |
| `s`       | Save to JSON (creates `.bak.<timestamp>`)                  |
| `x` / `q` | Exit                                                       |
| `?`       | Show help                                                  |

## Safety

- The tool never commands the servo outside `[angle_min, angle_max]`
  (hardware limits from the JSON), regardless of input.
- Always start with `h` to reach a known position before jogging towards
  a new limit.
- If the servo behaves unexpectedly (audible strain, jitter), press `h`
  or Ctrl-C immediately.

## Recommended procedure (per servo)

1. Press `h` to return to the original default position.
2. Jog towards one mechanical limit using `a` / `A`.
3. When mechanical resistance is reached, back off 1–2° with `d`.
4. Press `[` to mark the new `angle_software_min`.
5. Press `h`.
6. Jog towards the opposite limit with `d` / `D` and mark with `]`.
7. Move to the desired resting position and press `0`.
8. Press `p` to review the new values.
9. Press `s` to save.
10. Record in the calibration log: servo ID, new values, date, observer.

## Rebuild after save

The JSON file in `src/` is updated immediately. The rebuild must happen
on the machine that runs `servos.launch.py` (Jetson), because that
node loads the JSON from its own `install/` tree.

If calibration was performed on the laptop, copy the updated JSON to the
Jetson first:

```bash
scp src/energirobotter-ros-workspace-alex/wattson_description/servo_configs/<file>.json \
    elrik@192.168.1.105:humanoid_ws/src/energirobotter-ros-workspace-alex/wattson_description/servo_configs/
```

Then rebuild on the Jetson:

```bash
ssh elrik@192.168.1.105
cd ~/humanoid_ws
colcon build --packages-select energirobotter_bringup wattson_description elrik_description
source install/setup.bash
```

Restart `servos.launch.py` on the Jetson to load the new values.

## Limitations

The tool does not read live feedback from the servo; the physical angle
must be observed manually. Commands beyond the existing
`angle_software_min` / `angle_software_max` are clipped by
`wattson_servo_manager`. To extend the software limits, widen them in
the JSON first, rebuild, restart `servos.launch.py`, then calibrate.
