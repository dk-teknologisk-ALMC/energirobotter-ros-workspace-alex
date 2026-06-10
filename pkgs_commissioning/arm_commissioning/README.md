# arm_commissioning

Idriftsættelses- og test-værktøjer for **én humanoid-arm** (Wattson, 7 DOF
med Waveshare ST3215 servoer). Bygget med rapport-dokumentation for øje:
alle målinger gemmes som CSV + PNG i
`~/humanoid_ws/test_results/<dato>/<...>/` så de kan klippes direkte ind
i eksamensrapporten.

## Værktøjer

| Status | Værktøj | Formål | Detaljer |
|--------|---------|--------|----------|
| ✅ | `calibration_tool_node` | Find `angle_software_min/max` + `default_position` pr. servo | [docs/calibration_tool.md](docs/calibration_tool.md) |
| ✅ | `step_response_node` | Mål rise time / overshoot / settling time pr. servo | [docs/step_response.md](docs/step_response.md) |
| ✅ | `repeatability_node` | Mål positionsspredning over N gentagne kørsler | [docs/repeatability.md](docs/repeatability.md) |
| ✅ | `power_monitor_node` | Logg + live-vis strømforbrug pr. servo | [docs/power_monitor.md](docs/power_monitor.md) |

## Fælles forudsætninger

Inden et hvilket som helst værktøj startes:

1. Servo-stack kører: `ros2 launch energirobotter_bringup servos.launch.py`
2. ESP32 Serial Forwarding er aktiveret (se workspace-rod
   [README](../../README.md))
3. **INGEN andre `/joint_states`-publishere kører** (luk `slider_control`,
   `animation_player`, teleop m.fl.) — tjek med
   `ros2 topic info /joint_states`
4. `feedback_enabled: true` i servo-config for de servoer du måler på
   (kræves af alt undtagen `calibration_tool_node`)

## Byg + source

```bash
cd ~/humanoid_ws
colcon build --packages-select arm_commissioning \
  --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
source install/setup.bash
```

## Output-konvention

Alle test-værktøjer skriver til
`~/humanoid_ws/test_results/<YYYY-MM-DD>/<scope>/<YYYY-MM-DD_HHMMSS>_*.{csv,png}`,
hvor `<scope>` er enten et servo-navn (step_response, repeatability) eller
et scenarie-navn (power_monitor). Det betyder:

- CSV'erne er rapport-klare — én række pr. sample, kolonne-headers på første linje
- PNG'erne har metrics indlejret i grafen, så de kan stå alene som figurer
- Tidsstempler i filnavne gør at gentagne kørsler ikke overskriver hinanden

Se de enkelte tool-dokumenter for kolonne-formatet i hver CSV.
