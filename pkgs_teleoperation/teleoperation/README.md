# Teleoperation

Teleoperation for the Elrik humanoid robot via Vuer.

The robot tracks the position of the operator's hands, with the grippers
held at a constant rotation pointing forward.

Tracking is relative to the head only on the z-axis, so the operator's
height or seated/standing posture does not matter — tracking stays the
same. It is not relative on the x/y-axis, since controlling arm position
by moving the head felt unnatural.

## Usage

1. Plug the headset into a computer with a USB-C cable. From the headset,
   allow Android debugging (or set always-allow).

2. Start the Vuer app and note the port.

3. Run
   [reverse port forwarding](https://medium.com/@lazerwalker/how-to-easily-test-your-webvr-and-webxr-projects-locally-on-your-oculus-quest-eec26a03b7ee)
   (example with port 8012):
   ```
   adb reverse tcp:8012 tcp:8012
   ```

4. In the headset's browser, open `http://localhost:8012`.
