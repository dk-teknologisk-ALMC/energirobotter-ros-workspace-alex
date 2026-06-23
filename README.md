# Energirobotter ROS Workspace

ROS 2 (Humble) packages for Energinet's humanoid robots Elrik and Wattson.

## Setup

### Dialout Group

Add your user to the dialout/tty group on Linux:
```
sudo usermod -a -G dialout your_user_name
```

Reboot your system.

### Repository

Clone this repository into a `workspace/src/` folder:

```
git clone --recursive https://github.com/dk-teknologisk-ALMC/energirobotter-ros-workspace-alex.git
```

Also clone other needed repos here:
```
git clone -b jazzy https://bitbucket.org/traclabs/trac_ik.git
```

Add an empty file called `COLCON_IGNORE` in the `src/trac_ik/trac_ik_kinematics_plugin/` folder, to not build the `MoveIt` plugin. 

> **Note on workspace path:** `xacro` breaks when the workspace path contains
> a space (e.g. `~/Desktop/Humanoid build/workspace`). If your workspace is
> in such a path, create a space-free symlink and use it for all commands:
> ```
> ln -sfn "$HOME/Desktop/Humanoid build/workspace" ~/humanoid_ws
> ```
> From here on, use `~/humanoid_ws/...` everywhere.


### Dependencies

In `worspace` root, source ROS and install ROS dependencies with rosdep:
```
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
```

Python modules not included in [rosdistro](https://github.com/ros/rosdistro/blob/master/rosdep/python.yaml) can be installed from root of workspace with:
```
pip install -r src/energirobotter-ros-workspace-alex/requirements.txt
```

#### System packages

A handful of system packages are needed by the GUI tools and the
laptop-as-DHCP bringup procedure, but are not pulled in by `rosdep`:

```
sudo apt install -y \
    python3-tk \
    python3-matplotlib \
    zenity \
    dnsmasq
```

- `python3-tk` — `arm_commissioning/launcher_gui` (Tkinter control panel)
- `python3-matplotlib` — `arm_commissioning` test nodes (step response, repeatability, power monitor)
- `zenity` — `launcher_gui` sudo-ASKPASS prompt for root-owned services
- `dnsmasq` — standalone DHCP server for the Jetson when no router is available (see *Bringing up the robot for Slider Control* below)

#### ZED SDK

##### Ubuntu 22.04
Download and install [CUDA 12.6](https://developer.nvidia.com/cuda-downloads).

Download and install [ZED SDK v4.2](https://www.stereolabs.com/en-dk/developers/release) for CUDA 12. When prompted if the ZED SDK installer shall install CUDA, say no. 

##### Jetson Orin Nano (Jetpack 6.0)
Download and install [ZED SDK v4.2](https://www.stereolabs.com/en-dk/developers/release) for NVIDIA Jetson (ZED SDK for JetPack 6.0 GA (L4T 36.3)) 

#### ZED ROS 2 Wrapper

Follow the instructions on building the package in the [zed_ros2_wrapper](https://github.com/stereolabs/zed-ros2-wrapper?tab=readme-ov-file) repo. Name the `ros2_ws` folder something more appropriate, like `zed_wrapper_ws`. Also do the optional command of sourcing the workspace in `.bashrc`.

Replace the `zed2i.yaml` and `zedm.yaml` files in `~/zed_wrapper_ws/src/zed-ros2-wrapper/zed_wrapper/config/` with the versions provided in `energirobotter_bringup/config/zed_camera/` from this repository.

The `ZED_SDK` may have upgraded Numpy to 2.x, but ROS was built against Numpy 1.x, so it should be downgraded by running: `pip3 install "numpy<2" --force-reinstall`

### AI model
Download face detection model [yolov8n-face.pt](https://github.com/akanametov/yolov8-face/releases/download/v0.0.0/yolov8n-face.pt) from the [yolo-face repository](https://github.com/akanametov/yolo-face/tree/v0.0.0). Move the model into the `src/energirobotter-ros-workspace-alex/pkgs_vision/face_detection/models/` directory.


### Build

Build `workspace` with:
```
colcon build --symlink-install --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
```

The explicit `-DPython3_EXECUTABLE=/usr/bin/python3` flag avoids CMake
picking up a Conda Python by accident; safe to drop if you never use Conda.

## Usage

The most useful entry points for a new operator:

- [`energirobotter_bringup/README.md`](energirobotter_bringup/README.md) — launch files for each robot mode (servos, camera, slider control, animation playback, teleoperation).
- [`pkgs_commissioning/arm_commissioning/README.md`](pkgs_commissioning/arm_commissioning/README.md) — calibration and test tools (`calibration_tool_node`, `step_response_node`, `repeatability_node`, `power_monitor_node`) and the `launcher_gui` Tkinter control panel that starts the whole stack with one click.
- [`scripts/setup/HARDWARE_SETUP.md`](scripts/setup/HARDWARE_SETUP.md) — procedure for setting up a fresh Jetson Orin Nano + ESP32 modules from scratch (only needed when replacing hardware).

The sections below describe the full laptop-side bringup procedure in detail, including the USB port mapping for the three ESP32 servo-bus boxes.

## Bringing up the robot for Slider Control (laptop-as-DHCP setup)

This is the step-by-step procedure for starting the robot from the laptop when no
RUT router is available — the laptop runs `dnsmasq` as a stand-in DHCP server
for the Jetson. The end goal of this section is to have the **manual slider GUI**
running so you can drive individual joints by hand.

**Prerequisites**

- Laptop NIC `enp0s31f6` is configured with both `192.168.123.150/24` and
  `192.168.1.150/24` (set up once, persists across reboots).
- Jetson is pinned to `192.168.1.105` (hostname `elrik-jetson`). Two
  Jetson MACs are reserved — only one robot is ever powered on at a time:
    - `48:b0:2d:eb:e3:58` — original (Energinet) robot Jetson
    - `ac:3a:e2:12:39:5f` — bench Jetson (Wattson, JP6.0 SD-card image)
- Workspace is reachable at a **path without spaces**. The actual workspace
  lives at `~/Desktop/Humanoid build/workspace`, but the space in
  "`Humanoid build`" breaks `xacro` when launch files pass the URDF path
  unquoted. One-time fix:
  ```bash
  ln -sfn "$HOME/Desktop/Humanoid build/workspace" ~/humanoid_ws
  cd ~/humanoid_ws
  rm -rf build install log         # purge install paths that have the space baked in
  conda deactivate
  source /opt/ros/humble/setup.bash
  colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=/usr/bin/python3
  ```
  From here on, always use `~/humanoid_ws/...` in commands.
- The ZED camera USB cable is connected to the Jetson. Servo boxes may be
  plugged in at any time — see the port layout diagram further down.

### Terminal 1 — Laptop: start the DHCP server (must stay open)

Open a new terminal on the **laptop**:

```bash
sudo rm -f /var/lib/misc/dnsmasq.leases
sudo dnsmasq --no-daemon --port=0 --interface=enp0s31f6 --bind-interfaces --dhcp-authoritative \
  --dhcp-range=192.168.1.100,192.168.1.200,255.255.255.0,1h \
  --dhcp-host=48:b0:2d:eb:e3:58,ac:3a:e2:12:39:5f,192.168.1.105,elrik-jetson \
  --log-dhcp
```

The `rm` clears any stale leases so the reservation is honored; `--dhcp-authoritative` forces NAK on requests that don't match the reservation. Both Jetson MACs share one `--dhcp-host` entry because dnsmasq rejects multiple entries with the same IP. Leave this terminal running. Now power on the Jetson. If it does not pick up an
IP within ~30 s, unplug and replug the Ethernet cable on the Jetson side to
force a fresh DHCP request. Watch the `--log-dhcp` output for a `DHCPACK` to
`192.168.1.105`.

### Terminal 2 — Laptop: SSH into the Jetson and start the camera

Open a **new terminal** on the laptop:

```bash
ssh elrik@192.168.1.105
# (enter password)
cd energinet/
shumble          # alias: sources /opt/ros/humble/setup.bash
sw               # alias: sources install/setup.bash
ros2 launch energirobotter_bringup camera.launch.py camera_model:=zed2i rotate:=270
```

Wait until the camera node prints `Camera ready` (or equivalent) before
continuing.

Now physically plug in the three ESP32 servo boxes. The plug-in order
does not matter — each box is bound to a specific physical USB port on
the Jetson via `/dev/serial/by-path/`. Each coloured box must go into
its assigned port:

```
Jetson USB block (4 ports, viewed from the back):

  +--------------------+--------------------+
  |  YELLOW (port 2.3) |  BLACK (ZED camera)|
  |  right arm + head  |                    |
  +--------------------+--------------------+
  |  WHITE  (port 2.1) |  RED   (port 2.2)  |
  |  hands             |  left arm          |
  +--------------------+--------------------+
```

The mapping is defined in
`pkgs_control/servo_control/servo_control/wattson_servo_manager_node.py`:

**Red (port 2.2)**
`/dev/serial/by-path/platform-3610000.usb-usb-0:2.2:1.0-port0` —
drives the left arm.

**Yellow (port 2.3)**
`/dev/serial/by-path/platform-3610000.usb-usb-0:2.3:1.0-port0` —
drives the right arm and head.

**White (port 2.1)**
`/dev/serial/by-path/platform-3610000.usb-usb-0:2.1:1.0-port0` —
drives both hands.

Verify all three symlinks are present before continuing:

```bash
ls -l /dev/serial/by-path/
```

All three `platform-3610000.usb-usb-0:2.{1,2,3}:1.0-port0` entries must
be present. The `ttyUSBN` numbers they point to are irrelevant and may
change between replugs; the launch files resolve the path through the
stable `by-path` symlink.

### Terminal 3 — Laptop: SSH again and start the servo stack

Open another **new terminal** on the laptop:

```bash
ssh elrik@192.168.1.105
cd energinet/
shumble
sw
ros2 launch energirobotter_bringup servos.launch.py
```

**Warning:** as soon as this launch is running the servos are powered and will
move to their `default_position`. Keep hands clear.

### Terminal 5 — Laptop: launch the manual slider GUI

Open the final **new terminal** on the laptop:

```bash
conda deactivate
source /opt/ros/humble/setup.bash
source ~/humanoid_ws/install/setup.bash
ros2 launch energirobotter_bringup slider_control.launch.py description_package:=wattson_description
```

A Qt window appears with one slider per joint. Move a slider → the
corresponding servo moves on the robot.

### Recap of what is running where

| Terminal | Machine | Purpose                                |
|----------|---------|----------------------------------------|
| 1        | Laptop  | `dnsmasq` DHCP for the Jetson          |
| 2        | Jetson (via SSH) | `camera.launch.py`            |
| 3        | Jetson (via SSH) | `servos.launch.py`            |
| 4        | Phone   | ESP32 Serial Forwarding dialog (e-stop) |
| 5        | Laptop  | `slider_control.launch.py` (GUI)        |

### Shutdown order

1. Close the slider GUI (Terminal 5).
2. Ctrl-C `servos.launch.py` (Terminal 3) — joints go limp.
4. Ctrl-C `camera.launch.py` (Terminal 2).
5. Ctrl-C `dnsmasq` (Terminal 1).
6. Power off the Jetson.

## Playing pre-recorded animations / gestures

The `animation_player` package replays keyframed joint trajectories from CSV
files. It does exactly the same thing as the slider GUI (publishes
`sensor_msgs/JointState` on `/joint_states` and `/joint_states_hands`), but
driven from a file instead of a human. The servo stack on the Jetson
(`servos.launch.py`) is what actually moves the hardware — without it, the
animations are pure simulation.

### Prerequisites

- Terminals 1–3 from the bringup section above are running (DHCP, camera,
  `servos.launch.py`).
- **No other `/joint_states` publisher is active** — close the slider GUI
  before starting an animation, otherwise the two publishers will fight.

### Run an animation

Open a new terminal on the **laptop**:

```bash
conda deactivate
source /opt/ros/humble/setup.bash
source ~/humanoid_ws/install/setup.bash

ros2 run animation_player animation_player_node --ros-args \
  -p csv_file_path:=/home/teleoperation/humanoid_ws/install/energirobotter_bringup/share/energirobotter_bringup/animations/gesture_wave.csv
```

To play a different animation, swap the filename at the end of the path.
The node does not print progress while it runs. When the last frame has
been played the node sits idle holding the final pose. Use Ctrl-C to
stop.

Available CSV files (in `energirobotter_bringup/animations/`):

**Gestures**
`gesture_wave.csv`, `gesture_yes.csv`, `gesture_no.csv`,
`gesture_shrug.csv`.

**Poses (single frame)**
`pose_peace.csv`, `pose_rocknroll.csv`, `pose_handshake.csv`,
`pose_kungfu.csv`.

**Animations**
`animation_headbang.csv`, `animation_fingerguns.csv`, `idle1.csv`.

**Mimic**
`mimic_alexander.csv`, `mimic_optimus.csv`.

**Test / recordings**
`test_servos.csv`, `recording_*_test.csv`.

**Note:** `gesture_yes.csv` / `gesture_no.csv` use the head joints — they
require the `elrik_description` robot (head servos via the yellow ESP32 box).
The arm-only `wattson_description` will simply ignore those columns.

### How the CSV files are structured

Each animation is a plain CSV with a header row plus one row per keyframe:

```
frame,torso,joint_right_shoulder_pitch,joint_right_shoulder_roll,...,joint_head_yaw,joint_head_pitch
1,0.0,0.28,-0.0,...,-0.0,-0.0
2,0.0,1.09,-0.0,...,-0.0,-0.0
...
```

- **Column 1 (`frame`)** is a label only — copied into `header.frame_id`, not
  used for timing.
- **Remaining columns** are joint values **in degrees** (the player converts
  to radians internally with `np.deg2rad`).
- Columns whose name starts with `joint_` are published on `/joint_states`
  (arms + head). Columns starting with `hand_` are split out onto
  `/joint_states_hands` (finger servos).
- Playback rate is fixed by the node's `fps` parameter (default **24 Hz**) —
  one row = one frame, regardless of how big the joint deltas are. So if you
  want a slow motion, add more interpolated rows; for fast, fewer.
- A **single-row CSV** (like `pose_peace.csv`) is just a static pose: the
  player publishes that one frame and then holds it.

### How the existing CSVs appear to have been authored

There is **no recorder node in this repo** — the CSVs were produced by hand
or by ad-hoc scripts that don't live in version control. Best guesses based
on the file contents:

- **`pose_*.csv`** — a single row each → hand-written (or a slider pose copied
  out by hand). Use one of these as a template for new static poses.
- **`gesture_*.csv`, `animation_*.csv`** — smoothly growing values between
  keyframes (e.g. `0.28, 1.09, 2.38, 4.12, …`) → hand-keyframed, probably
  linearly interpolated with a small throw-away Python script.
- **`mimic_alexander.csv`, `mimic_optimus.csv`** — named after people →
  almost certainly captured from the **teleoperation stack**
  (`teleoperation_vuer_node` / `teleoperation_zeromq_node` publish exactly to
  `/joint_states` and `/joint_states_hands`, which matches the CSV layout
  one-to-one). Someone subscribed to those two topics during a headset/ZeroMQ
  teleop session and dumped them to a CSV.
- **`recording_*_test.csv`** — shorter header (no `hand_*` columns) →
  recorded back when only the arm stack existed. Same idea as the mimic
  files, just narrower.

### Making your own

Easiest paths in practice:

1. **New static pose** — copy `pose_handshake.csv`, keep the header, edit the
   numbers in row 1.
2. **New keyframed gesture** — copy `gesture_wave.csv`, keep the header,
   replace the rows with your own keyframes (in **degrees**, one per
   `1/fps` second).
3. **Capture live motion** — since the format is just `degrees(joint_states)`
   per frame, you can write a small Python node that subscribes to
   `/joint_states` (and `/joint_states_hands`), converts to degrees, and
   appends a CSV row at e.g. 24 Hz. Drive the robot via slider GUI or
   teleoperation while it records.

Drop the new file into `energirobotter_bringup/animations/`, rebuild with
`colcon build --packages-select energirobotter_bringup --symlink-install`
from `~/humanoid_ws`, and it shows up alongside the others.

## Teleoperation with Quest 3 (wired)

The Quest 3 headset is connected via **USB-C cable to the laptop** for both
scenarios. The browser inside the headset hits `http://localhost:8012`, and
`adb reverse` forwards that to the laptop's actual `localhost:8012` where
Vuer is running. No WiFi, no ngrok, no router needed.

We use `camera_source:=ros` everywhere — Vuer subscribes directly to the
ZED's compressed image topics over DDS. This avoids the `webrtc_server_camera`
node entirely (which depends on `pyzed` and is therefore Jetson-only).

### Prerequisites (all scenarios)

- Quest 3 is in **developer mode** (Settings → System → Developer →
  USB Connection Dialog enabled).
- USB-C **data** cable (the original Quest cable works) — pure power-only
  cables will not show up in `adb devices`.
- The laptop NIC and Jetson MAC pinning from the *Slider Control* section
  above is already configured (one-time setup).

### Scenario A — Camera only (passthrough preview, no robot motion)

Use this to confirm the ZED stream reaches the headset. No servos are
involved, so no risk of motion.

**Terminal A1 — Laptop: DHCP for the Jetson** *(skip if already running)*

```bash
sudo rm -f /var/lib/misc/dnsmasq.leases
sudo dnsmasq --no-daemon --port=0 --interface=enp0s31f6 --bind-interfaces --dhcp-authoritative \
  --dhcp-range=192.168.1.100,192.168.1.200,255.255.255.0,1h \
  --dhcp-host=48:b0:2d:eb:e3:58,ac:3a:e2:12:39:5f,192.168.1.105,elrik-jetson \
  --log-dhcp
```

Wait for a `DHCPACK` to `192.168.1.105`, then power on the Jetson if it
isn't already up.

**Terminal A2 — Jetson (via SSH): start the ZED camera**

```bash
ssh elrik@192.168.1.105
cd energinet/
shumble
sw
ros2 launch energirobotter_bringup camera.launch.py camera_model:=zed2i rotate:=270
```

Wait until the camera node settles (publishes images on
`/zed/zed_node/...`).

**Terminal A3 — Laptop: forward the Vuer port to the headset**

Plug the Quest 3 into the laptop via USB-C, accept the USB-debug prompt
inside the headset, then:

```bash
adb devices
adb reverse tcp:8012 tcp:8012
```

This forward is per-USB-session — re-run it every time you replug.

**Terminal A4 — Laptop: start Vuer**

```bash
conda deactivate
source /opt/ros/humble/setup.bash
source ~/humanoid_ws/install/setup.bash
ros2 launch energirobotter_bringup teleoperation_vuer.launch.py \
  camera_source:=ros \
  stereo_enabled:=false \
  ik_enabled:=false \
  rviz:=false
```

Wait for the line `Connect to URL in headset: http://localhost:8012`.

**On the Quest 3:** open the **Meta Quest Browser** and go to
`http://localhost:8012`. Put on the headset — you should see the ZED's
left-camera image as a quad in front of you.

**Shutdown:** Ctrl-C Terminal A4 (Vuer), Ctrl-C Terminal A2 (camera),
Ctrl-C Terminal A1 (dnsmasq), then `adb reverse --remove-all` on the laptop.

### Scenario B — Camera + teleoperation (robot mirrors your arms)

Adds IK from headset hand poses → `/joint_states` → servos. **The servos
will move as soon as you start tracking; keep clear.**

Before you start: **no other `/joint_states` publisher must be active** —
close the slider GUI, stop any `animation_player`.

**Terminal B1 — Laptop: DHCP for the Jetson** *(skip if already running)*

```bash
sudo rm -f /var/lib/misc/dnsmasq.leases
sudo dnsmasq --no-daemon --port=0 --interface=enp0s31f6 --bind-interfaces --dhcp-authoritative \
  --dhcp-range=192.168.1.100,192.168.1.200,255.255.255.0,1h \
  --dhcp-host=48:b0:2d:eb:e3:58,ac:3a:e2:12:39:5f,192.168.1.105,elrik-jetson \
  --log-dhcp
```

**Terminal B2 — Jetson (via SSH): start the ZED camera**

```bash
ssh elrik@192.168.1.105
cd energinet/
shumble
sw
ros2 launch energirobotter_bringup camera.launch.py camera_model:=zed2i rotate:=270
```

**Terminal B3 — Jetson (via SSH): start the servo stack**

**Warning:** as soon as this launch runs the servos are powered and move to
their `default_position`. Keep hands clear.

```bash
ssh elrik@192.168.1.105
cd energinet/
shumble
sw
ros2 launch energirobotter_bringup servos.launch.py
```

**Terminal B4 — Laptop: forward the Vuer port to the headset**

Plug the Quest 3 into the laptop via USB-C, accept the USB-debug prompt
inside the headset, then:

```bash
adb devices
adb reverse tcp:8012 tcp:8012
```

**Terminal B5 — Laptop: start Vuer with IK**

```bash
conda deactivate
source /opt/ros/humble/setup.bash
source ~/humanoid_ws/install/setup.bash
ros2 launch energirobotter_bringup teleoperation_vuer.launch.py \
  camera_source:=ros \
  stereo_enabled:=false \
  ik_enabled:=true \
  rviz:=false
```

**On the Quest 3:** open the browser to `http://localhost:8012` and grant
hand-tracking permission when asked. Once your hands are tracked, the
robot's arms start mirroring them through the IK solver.

**Recap of what is running where**

| Terminal | Machine | Purpose                                |
|----------|---------|----------------------------------------|
| 1        | Laptop  | `dnsmasq` DHCP for the Jetson          |
| 2        | Jetson (SSH) | `camera.launch.py` (with `rotate:=270`) |
| 3        | Jetson (SSH) | `servos.launch.py`               |
| T1       | Laptop  | `adb reverse tcp:8012 tcp:8012`        |
| T2       | Laptop  | `teleoperation_vuer.launch.py` (`ik_enabled:=true`) |

**Shutdown order**

1. Take off the headset / stop hand tracking — robot freezes at last commanded pose.
2. Ctrl-C `teleoperation_vuer.launch.py` (T2) — IK stops publishing.
3. `adb reverse --remove-all` (T1 or anywhere).
4. (Optional) run `idle1.csv` via `animation_player` to bring the robot to a
   safe rest pose before killing `servos.launch.py`. See the animations
   section above.
5. Continue with the normal bringup shutdown order (servos → camera → dnsmasq).

### Troubleshooting

- **Low framerate / laggy image in headset** — expected with
  `camera_source:=ros`. This path takes the JPEG-compressed ZED frames
  off the DDS topic and pushes them into Vuer's per-client image queue,
  which re-encodes and ships them over the websocket as individual
  frames. It typically lands around 10–15 fps and is noticeably behind
  real time. The `webrtc_server_camera` path (using `pyzed` + H.264 on
  the Jetson) is significantly faster, but only runs on the Jetson and
  the signalling/peer-connection setup with the headset over USB is
  fragile. For full-rate stereo video the WebRTC server must run on the
  Jetson with the headset on the same LAN.
- **"Connect call failed (127.0.0.1, 8080)" or 500 on `/offer`** — you ran
  with `camera_source:=ngrok` or `:=server` by accident. Both require the
  `webrtc_server_camera` node, which depends on `pyzed` and only runs on
  the Jetson. Use `camera_source:=ros`.
- **White/black square in headset** — Vuer isn't receiving frames. Verify
  the topic exists on the laptop:
  ```bash
  ros2 topic hz /zed/zed_node/left/image_rect_color/compressed/rotated/compressed
  ```
  If nothing comes through, the Jetson camera launch isn't running with
  `rotate:=270`, or DDS discovery between laptop and Jetson is broken.
- **"adb: no devices"** — re-plug the cable, then accept the USB-debug
  prompt that appears inside the headset.
- **Page doesn't load in headset** — check Vuer is actually on 8012
  (`ss -ltn | grep 8012` on the laptop) and that `adb reverse --list` shows
  the forward.

