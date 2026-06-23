# Hardware setup: new Jetson Orin Nano and ESP32 modules

End-to-end procedure to take a fresh Orin Nano and three new ESP32 modules
from out-of-the-box to running this workspace identically to the existing
system. The contents of this folder (`scripts/setup/`) automate everything
that can be automated; the remaining steps require a host PC, an
interactive download, or physical work.

## Prerequisites

- A **Jetson Orin Nano Developer Kit** (8 GB) with a blank SD card or eMMC.
- A **host PC running Ubuntu** with NVIDIA SDK Manager installed (for
  JetPack flashing).
- Three **new ESP32 modules** of the same type as the existing ones.
- A USB-A-to-micro-USB or USB-C cable depending on the ESP32 variant.
- Internet on the Jetson during setup.

Optional:

- One **existing, working ESP32** to clone the firmware from. This is a
  convenience; without it, flash the firmware using Waveshare's own
  flashing tool instead (see step 4).

## Step 1 — Flash JetPack 6.x on the Jetson

Run **NVIDIA SDK Manager** on the host PC and flash JetPack 6.x (Ubuntu
22.04 L4T 36.x). Follow the guided flow:

1. Put the Orin Nano in recovery mode (jumper on REC pin, then power).
2. Connect USB-C to the host PC.
3. Select target = Jetson Orin Nano, OS = Ubuntu 22.04.
4. Let SDK Manager flash the device.

When the Jetson boots for the first time, create the user (use `elrik` to
match the existing setup), set a password, and accept the OEM
configuration.

## Step 2 — Run the post-flash setup script

Log in to the Jetson, clone this repository, and run the setup script:

```bash
sudo apt-get update && sudo apt-get install -y git
mkdir -p ~/humanoid_ws/src && cd ~/humanoid_ws/src
git clone --branch alex/min-opgave \
    https://github.com/dk-teknologisk-ALMC/energirobotter-ros-workspace-alex.git
cd energirobotter-ros-workspace-alex
chmod +x scripts/setup/setup-orin-nano.sh
./scripts/setup/setup-orin-nano.sh
```

The script is idempotent and can be re-run without side effects.

It performs:

- ROS 2 Humble installation.
- Adding the user to the `dialout` group.
- `rosdep` initialisation and update.
- Cloning the workspace and `trac_ik`.
- Python dependencies from `requirements.txt`.
- Chrony for NTP time sync.
- `colcon build` of the workspace.
- Verification that the `/dev/serial/by-path/` entries match the paths
  hard-coded in the code.

## Step 3 — Manual post-script steps

The script prints these steps at the end. They are collected here for
reference.

### 3.1 Log out and back in

The `dialout` group change only takes effect after a new login.

### 3.2 Add shell aliases

Append to `~/.bashrc`:

```bash
alias shumble='source /opt/ros/humble/setup.bash'
alias sw='source ~/humanoid_ws/install/setup.bash'
```

### 3.3 Static IP on 192.168.1.105

Choose one strategy.

**A — Static IP via netplan** (Jetson manages its own address)

```bash
sudo tee /etc/netplan/99-elrik.yaml >/dev/null <<'EOF2'
network:
  version: 2
  ethernets:
    eth0:
      addresses: [192.168.1.105/24]
      routes:
        - to: default
          via: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 1.1.1.1]
EOF2
sudo chmod 600 /etc/netplan/99-elrik.yaml
sudo netplan apply
```

**B — DHCP reservation** (router or laptop DHCP manages the address)

Find the Jetson's MAC:

```bash
ip link show eth0 | awk '/ether/ {print $2}'
```

Reserve that MAC to 192.168.1.105 in the router, or add
`--dhcp-host=<MAC>,192.168.1.105,elrik-jetson` to the existing
`dnsmasq` configuration on the laptop.

### 3.4 Copy SSH key from the laptop

From the **laptop** (not the Jetson):

```bash
ssh-copy-id elrik@192.168.1.105
```

### 3.5 ZED SDK and ZED ROS 2 wrapper

Follow the **ZED SDK** and **ZED ROS 2 Wrapper** sections in the workspace
[README.md](../../README.md). This requires an interactive `.run` download
from Stereolabs that cannot be automated.

### 3.6 AI model

Download `yolov8n-face.pt` from
<https://github.com/akanametov/yolov8-face/releases/tag/v0.0.0> and place
it in `pkgs_vision/face_detection/models/`. See the **AI model** section
of the workspace README.

## Step 4 — Flash the ESP32 firmware

There are two ways to flash the bridge firmware onto a new ESP32:

### 4a — Clone an existing module (recommended if available)

With a known-good ESP32 connected to `/dev/ttyUSB0` on the laptop:

```bash
cd ~/humanoid_ws/src/energirobotter-ros-workspace-alex/scripts/setup
chmod +x clone-esp32.sh
./clone-esp32.sh read /dev/ttyUSB0
```

This produces `esp32_firmware_clone.bin` in the current directory.

For each new ESP32, connect it one at a time and run:

```bash
./clone-esp32.sh write /dev/ttyUSB0
./clone-esp32.sh verify /dev/ttyUSB0
```

Power-cycle the new ESP32 and verify that it boots normally (LED pattern
matches the old module).

### 4b — Use the Waveshare flashing tool

If no existing ESP32 is available to clone from, flash the firmware using
Waveshare's own flashing utility. See the Waveshare wiki for the
bridge-board product for the firmware binary and the step-by-step
instructions.

## Step 5 — Physical labelling

Three servo-bus bridge modules, one per group:

**Left arm — Red cable**
One ESP32, ST3215 servos, servo IDs 1–7.

**Right arm and head — Yellow cable**
One ESP32, ST3215 servos, servo IDs 11–17 (arm) and 8, 9 (head).

**Both hands — White cable**
One ESP32, SC09 servos, servo IDs 20–29 (10 fingers total).

Label each ESP32 with coloured tape or a clip-on label matching the
above. On the Jetson's physical USB block: Red goes in port 2.2, Yellow
in 2.3, White in 2.1.

### Finger servo IDs

Both hands share the white bus, so each SC09 needs a unique ID. This is
why the range is 20–29 rather than two times 1–5.

**Left hand**
`hand_left_pinky` = 20, `hand_left_ring` = 21, `hand_left_middle` = 22,
`hand_left_index` = 23, `hand_left_thumb` = 24.

**Right hand**
`hand_right_thumb` = 25, `hand_right_index` = 26,
`hand_right_middle` = 27, `hand_right_ring` = 28, `hand_right_pinky` = 29.

The authoritative ID assignment lives in
`wattson_description/servo_configs/servo_hand_{left,right}_params.json`.
The older `elrik_description/` and `energirobotter_bringup/config/`
JSON files with IDs 0–5 and `thumb_x` are from the Elrik robot and are
not in use on Wattson.

### Commissioning new SC09 servos

Factory ID is 1. Use `scripts/setup_servo_sc.py` in the workspace root,
one servo at a time on the white bus, and run `set-id <N>` with the ID
from the table above.

## Step 6 — Final verification

On the Jetson:

```bash
shumble
sw
ros2 launch energirobotter_bringup servos.launch.py
```

Confirm that all joints reach their `default_position` without errors and
that the manager node does not log "could not open port". If it does,
check:

1. Are the ESP32 modules plugged into the correct coloured USB ports?
2. `ls /dev/serial/by-path/` — are all three
   `platform-3610000.usb-...:2.{1,2,3}:1.0-port0` paths present?
3. Is the user in the `dialout` group? (`groups | grep dialout`)
4. Is the ESP32 firmware clone flashed correctly?
   (`./clone-esp32.sh verify <port>`)

## Troubleshooting

**`/dev/serial/by-path/` paths do not have the `platform-3610000.usb-...` prefix**

Uncommon on the Orin Nano dev kit, but can happen if NVIDIA changes the
USB controller mapping in a new JetPack version.

1. Find the correct path: `ls -l /dev/serial/by-path/`.
2. Update the `port_path=` strings in
   `pkgs_control/servo_control/servo_control/wattson_servo_manager_node.py`
   around lines 95, 107, 120.
3. Rebuild: `cd ~/humanoid_ws && colcon build --packages-select servo_control`.

**`colcon build` fails on a package that requires the ZED SDK**

Expected if the ZED SDK is not installed. Add a `COLCON_IGNORE` file in
the ZED package folder to skip it, or install the ZED SDK first (see
step 3.5).

**A cloned ESP32 does not boot**

1. Verify that the two ESP32 modules have the same flash size
   (`./clone-esp32.sh` rejects the operation if they do not).
2. Verify that they are the same chip revision
   (`esptool.py --port /dev/ttyUSB0 chip_id`).
3. If the chips differ (for example ESP32 vs. ESP32-S3), a bit-for-bit
   clone is not possible. The firmware source must be rebuilt for the
   new chip.

---

**Last updated:** 21 June 2026.
