# Energirobotter Bringup

Bringup package for Energirobotter, with launch files for each mode or
feature (slider control, teleoperation, face following, ...). `launch/` is
split into files meant to run on the robot itself (Jetson) and files meant
to run on a development laptop on the same subnet.

Install dependencies once:

```
rosdep install --from-paths src -y --ignore-src
```

## Slider Control

Creates a panel with one slider per joint for manual testing.

### Launch file

On a computer with display:

```
ros2 launch energirobotter_bringup slider_control.launch.py description_package:=wattson_description
```

### Setup robot

1. Turn on the robot.
2. SSH into the robot from a terminal on the PC:
   ```
   ssh elrik@192.168.1.105
   ```
3. Start `servos.launch.py` on the robot. The servos are powered as soon as
   this launch is running:
   ```
   cd energinet/
   shumble
   sw
   ros2 launch energirobotter_bringup servos.launch.py
   ```

### Enable Servo Serial Forwarding

Newer ESP32 firmware (2026-05-27 and later) enables serial forwarding
automatically at boot. On older firmware:

1. Connect to the `ESP32_DEV` Wi-Fi network (password `12345678`).
2. Open `http://192.168.4.1` in a browser.
3. Click **Start Serial Forwarding** before any node sends commands.
4. Leave **Stop Serial Forwarding** ready as an e-stop.

## Teleoperation Vuer

[Vuer](https://docs.vuer.ai/en/latest/) bridges a Quest 3 VR headset to the
robot. The headset can be connected wired (USB-C) or wireless (via
[ngrok](https://ngrok.com/)). The camera can only be served to the headset
over a secure connection, so `ngrok` is also required for the camera stream
in the wireless case.

### Setup robot

1. Turn on the robot.
2. SSH into the robot:
   ```
   ssh elrik@192.168.1.105
   ```
3. For `ngrok`, export your
   [authtoken](https://dashboard.ngrok.com/get-started/your-authtoken):
   ```
   export NGROK_AUTHTOKEN=$YOUR_AUTHTOKEN
   ```
4. Start the camera:
   ```
   ros2 launch energirobotter_bringup camera.launch.py camera_model:=zed2i rotate:=270
   ```

5. Start teleoperation on the robot. `camera_source` may be `ros`,
   `server`, or `ngrok`; omit if no camera. Set `rviz:=true` only if a
   display is connected.
   ```
   cd energinet/
   shumble
   sw
   ros2 launch energirobotter_bringup teleoperation_vuer.launch.py \
       camera_source:=ros stereo_enabled:=false ik_enabled:=true rviz:=false
   ```
   You can also run `teleoperation_vuer.launch.py` from a PC on the same
   subnet. If not on the robot, set `camera_enabled:=false`.

### Setup visualisation

If no display is connected to the robot, start RViz on the laptop:

```
rviz2 -d src/energirobotter-ros-workspace-alex/energirobotter_bringup/config/rviz/teleoperation.rviz
```

### Setup VR headset

1. Turn on the headset.

#### Wireless

2. In the headset's browser, open the `ngrok` URL printed by
   `teleoperation_vuer.launch.py`.

#### Wired

You must run `teleoperation_vuer.launch.py` (step 5 under *Setup robot*)
on the computer the headset is connected to, in order to access its
localhost address.

2. Plug the USB cable into the headset and the computer, then put the
   headset on.
3. Accept the USB connection in the headset. If you miss the prompt, it is
   under notifications. If `USB-C Port Disabled, water and debris` appears,
   restart the headset and try again; if that fails, use the other end of
   the cable.
4. Enable reverse port forwarding from the PC:
   ```
   adb reverse tcp:8012 tcp:8012
   ```
5. In the headset's browser, open the `localhost` URL printed by
   `teleoperation_vuer.launch.py`.

### Calibrate and launch

1. Plug in the ESP32 servo boxes in this order (camera must have run at
   least once first): left arm + head → right arm → hands.
2. In the headset, press **passthrough**.
3. Calibrate the view by holding the Meta button on the right controller.
4. Verify tracking in RViz.
5. Start `servos.launch.py` on the robot. The robot mirrors hand tracking
   immediately, so ensure tracking is stable first:
   ```
   cd energinet/
   shumble
   sw
   ros2 launch energirobotter_bringup servos.launch.py
   ```
6. When done, stop `servos.launch.py` before removing the headset.

## Teleoperation Unity (Deprecated)

Replaced by the Vuer pipeline above. Kept here only for reference; the
launch file `teleoperation_zeromq.launch.py` still exists but is no longer
maintained.

Typical invocation on the Jetson (with the Unity VR Interface app running
on the PC):

```
ros2 launch energirobotter_bringup teleoperation_zeromq.launch.py \
    ik_enabled:=true camera_enabled:=true ip_target:="192.168.1.102"
```

## Face Following (Deprecated)

Superseded by the standalone `pkgs_vision/face_following` package, but the
bringup launch file still works:

```
source install/setup.bash
ros2 launch energirobotter_bringup vision.launch.py use_compressed:=true
```

Without a camera, use the mock publisher:

```
ros2 launch energirobotter_bringup vision.launch.py use_mock_camera:=true
```

The first `face_detection` run pulls additional `ultralytics` packages and
requires a node restart afterwards.
