# launcher_gui

Tkinter control panel that starts and stops the robot's services from a
single window.

## Dependencies

```bash
sudo apt install python3-tk ssh-askpass-gnome
```

`pkexec` (polkit) ships with standard Ubuntu and is used to start the
DHCP server without storing a sudo password in the application.

## Launch

```bash
ros2 run arm_commissioning launcher_gui
```

## Operation

1. Complete the pre-flight checklist shown at the top of the window.
2. Power on the Jetson.
3. Start the camera service.
4. Connect the ESP32 boxes to the Jetson USB ports:
   - **Red** → port 2.2 (left arm)
   - **Yellow** → port 2.3 (right arm + head)
   - **White** → port 2.1 (hands)

   Order of insertion is irrelevant; ports are bound via
   `/dev/serial/by-path/`.
5. Connect the Quest 3 if teleoperation will be used.

Use **Start demo** to launch the full sequence
(DHCP → Camera → adb reverse → Vuer), or use the per-service **Start**
buttons.

## Services

| Section | Service                       | Action                                          |
|---------|-------------------------------|-------------------------------------------------|
| Network | DHCP server                   | `pkexec dnsmasq …`                              |
| Network | adb reverse                   | Forwards Quest's `localhost:8012` to laptop     |
| Robot   | Camera (Jetson)               | SSH to Jetson, runs `camera.launch.py`          |
| Robot   | Servos (Jetson)               | SSH to Jetson, runs `servos.launch.py`          |
| Demo    | Vuer teleop — camera only     | Vuer with `ik_enabled:=false`                   |
| Demo    | Vuer teleop — camera + IK     | Vuer with `ik_enabled:=true`                    |
| Demo    | Power monitor                 | `power_monitor_node` with live viewer           |
| Demo    | Animation: idle1.csv          | Plays `idle1` animation                         |

## Status indicators

A coloured dot to the left of each service shows its state:

- **Green** — running
- **Grey** — stopped
- **Red** — process exited with a non-zero status

## Shutdown

| Action            | Effect                                                                |
|-------------------|-----------------------------------------------------------------------|
| **Stop**          | Sends `SIGINT` to the service's process group                         |
| **Stop all**      | Sends `SIGINT` to all services; escalates to `SIGTERM` after 3 s      |
| Close window (X)  | Calls **Stop all** before exit                                        |

`SIGINT` is delivered to the local SSH client. Remote processes receive
it through the allocated TTY (`ssh -tt`). If a remote process remains
after shutdown, terminate it manually:

```bash
ssh elrik@192.168.1.105 pkill -f ros2
```

## Customisation

Service definitions and the demo sequence are declared at the top of
[`launcher_gui_node.py`](../arm_commissioning/launcher_gui_node.py):

```python
SERVICES = [
    {"key": "...", "label": "...", "command": "...", ...},
]

DEMO_SEQUENCE = [("dhcp", 1.0), ("jetson_camera", 6.0), ...]
```

Rebuild after editing:

```bash
colcon build --packages-select arm_commissioning --symlink-install
```

## Troubleshooting

**`_tkinter.TclError: no display name and no $DISPLAY`**
Running over SSH without X forwarding. Run on a machine with a display.

**`pkexec` fails / DHCP does not start**
Polkit rejected the password. Retry, or run `sudo dnsmasq …` directly in
a terminal.

**SSH to Jetson reports `Connection refused`**
Jetson not booted or no DHCP lease. Wait for `DHCPACK` in the DHCP log
before starting Jetson services.

**Vuer shows a blank screen**
Camera topic inactive. Verify the topic is publishing:

```bash
ros2 topic hz /zed/zed_node/left/image_rect_color/compressed/rotated/compressed
```

Expected rate is approximately 60 Hz.

**Quest shows "site can't be reached"**
`adb reverse` is not active. Verify `adb devices` lists the headset and
restart the adb-reverse service.

**Status dot turns red immediately on start**
The command failed. Read the log pane for the full error message.
