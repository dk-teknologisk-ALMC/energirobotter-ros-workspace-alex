# arm_commissioning

Commissioning and test tools (Wattson). All measurements are stored as CSV and PNG in
`~/humanoid_ws/test_results/<date>/<...>/`.

## Tools

**`calibration_tool_node`**
Find `angle_software_min`, `angle_software_max`, and `default_position`
per servo. See [docs/calibration_tool.md](docs/calibration_tool.md).

**`step_response_node`** *(WIP)*
Measure rise time, overshoot, and settling time per servo. See
[docs/step_response.md](docs/step_response.md).

**`repeatability_node`** *(WIP)*
Measure positional spread over `N` repeated cycles between two poses.
See [docs/repeatability.md](docs/repeatability.md).

**`power_monitor_node`** *(WIP)*
Log and live-display current draw per servo. See
[docs/power_monitor.md](docs/power_monitor.md).

**`launcher_gui`**
Tkinter control panel that starts the full robot stack from a single
window. See [docs/launcher_gui.md](docs/launcher_gui.md).

## Common prerequisites

Before any tool is started:

1. The servo stack is running:
   `ros2 launch energirobotter_bringup servos.launch.py`
2. ESP32 Serial Forwarding is active (see the workspace-root
   [README](../../README.md)).
3. No other `/joint_states` publisher is running. Close
   `slider_control`, `animation_player`, teleop, and similar nodes.
   Verify with `ros2 topic info /joint_states`.
4. `feedback_enabled: true` is set in the servo config for every servo
   to be measured. Required by all tools except `calibration_tool_node`.

## Build and source

```bash
cd ~/humanoid_ws
colcon build --packages-select arm_commissioning \
  --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
source install/setup.bash
```

## Output convention

All test tools write to
`~/humanoid_ws/test_results/<YYYY-MM-DD>/<scope>/<YYYY-MM-DD_HHMMSS>_*.{csv,png}`,
where `<scope>` is either a servo name (step_response, repeatability) or
a scenario name (power_monitor).

- CSV files have one row per sample and column headers on the first line.
- PNG files contain the metrics embedded in the plot.
- Timestamps in filenames ensure that repeated runs do not overwrite
  each other.

See the individual tool documents for the column format of each CSV.
