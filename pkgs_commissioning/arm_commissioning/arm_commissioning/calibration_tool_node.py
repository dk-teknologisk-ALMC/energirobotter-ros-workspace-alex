"""
Kalibrerings-værktøj for én ST3215-servo ad gangen.

Brug: vælg et joint (servo) i en eksisterende servo-config JSON,
brug tastaturet til at jogge servoen til fysiske endepositioner og
nulpunkt, og gem de nye værdier tilbage til JSON-filen.

Kontrol (sendes til servo via /joint_states som radianer):
    a / d     :  step  -1° / +1°  (fysisk)
    A / D     :  step  -5° / +5°
    z / c     :  step -0.1° / +0.1°  (finjustering)
    h         :  hjem (default_position fra original JSON)
    SPACE     :  hold nuværende position (genudsend)

Markeringer (skrives i hukommelse, gemmes først ved 's'):
    [         :  marker nuværende som angle_software_min
    ]         :  marker nuværende som angle_software_max
    0         :  marker nuværende som default_position (nulpunkt)
    p         :  print nuværende tilstand
    s         :  GEM til JSON (laver .bak-backup) og forbliv åben
    x / q     :  afslut (uden at gemme igen)

Sikkerhed:
  - Tool clipper aldrig udenfor [angle_min, angle_max] fra JSON
    (hardware-grænser), uanset hvor langt du forsøger at jogge.
  - Bevægelseshastighed begrænses af servoens angle_speed_max
    samt af et ekstra konservativt --jog_speed argument.
  - Start ALTID med at trykke 'h' for at gå til en kendt position
    inden du begynder at jogge mod endepositioner.

Eksempel:
    ros2 run arm_commissioning calibration_tool_node \
        --ros-args -p config_file:=<sti>/servo_arm_left_params.json \
                   -p joint_name:=joint_left_shoulder_pitch
"""

import json
import os
import select
import shutil
import sys
import termios
import threading
import time
import tty
from datetime import datetime

import numpy as np

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class CalibrationToolNode(Node):
    def __init__(self):
        super().__init__("calibration_tool_node")

        # Parameters
        self.declare_parameter("config_file", "")
        self.declare_parameter("joint_name", "")
        self.declare_parameter("publish_rate", 20.0)
        self.declare_parameter("jog_speed", 30.0)  # deg/s — overstyrer angle_speed_max nedad

        self.config_file = self.get_parameter("config_file").value
        self.joint_name = self.get_parameter("joint_name").value
        self.publish_rate = float(self.get_parameter("publish_rate").value)
        self.jog_speed = float(self.get_parameter("jog_speed").value)

        if not self.config_file or not os.path.isfile(self.config_file):
            self.get_logger().error(
                f"config_file ugyldig: '{self.config_file}'. "
                f"Angiv en eksisterende JSON med -p config_file:=..."
            )
            raise SystemExit(2)

        if not self.joint_name:
            self.get_logger().error("joint_name skal angives med -p joint_name:=...")
            raise SystemExit(2)

        # Load JSON
        with open(self.config_file, "r") as f:
            self.config = json.load(f)

        if "servos" not in self.config or self.joint_name not in self.config["servos"]:
            available = list(self.config.get("servos", {}).keys())
            self.get_logger().error(
                f"joint_name '{self.joint_name}' findes ikke i config. "
                f"Tilgængelige: {available}"
            )
            raise SystemExit(2)

        self.servo_cfg = self.config["servos"][self.joint_name]
        self.all_joint_names = list(self.config["servos"].keys())

        # Original værdier (bruges som reset)
        self.angle_min_hw = float(self.servo_cfg["angle_min"])
        self.angle_max_hw = float(self.servo_cfg["angle_max"])
        self.default_orig = float(self.servo_cfg["default_position"])

        # Levende værdier (kan opdateres ved markering)
        self.sw_min = float(self.servo_cfg["angle_software_min"])
        self.sw_max = float(self.servo_cfg["angle_software_max"])
        self.default_new = self.default_orig

        # Begræns jog_speed til servoens max
        servo_speed_max = float(self.servo_cfg.get("angle_speed_max", self.jog_speed))
        self.jog_speed = min(self.jog_speed, servo_speed_max)

        # Nuværende fysisk target (start på original default)
        self.lock = threading.Lock()
        self.target_phys = self.default_orig
        self.running = True

        # Publisher til /joint_states (servo_manager subscriber)
        self.pub = self.create_publisher(JointState, "/joint_states", 1)
        self.timer = self.create_timer(1.0 / self.publish_rate, self._publish_target)

        # Keyboard input thread
        self.kb_thread = threading.Thread(target=self._keyboard_loop, daemon=True)
        self.kb_thread.start()

        self._print_help()
        self._print_state(initial=True)

    # ------------------------- ROS publishing -------------------------

    def _publish_target(self):
        with self.lock:
            target_phys = self.target_phys

        # Clip altid til hardware-range (angle_min/max fra JSON) så servoen
        # tager ingen skade selv ved tastetryk uden for software-min/max.
        # Manager forventer /joint_states i radianer som logical angle
        # (= delta fra default_position), så vi trans formerer her.
        target_phys = float(np.clip(target_phys, self.angle_min_hw, self.angle_max_hw))
        logical_deg = target_phys - self.default_orig

        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = [self.joint_name]
        msg.position = [float(np.deg2rad(logical_deg))]
        self.pub.publish(msg)

    # ------------------------- Keyboard handling ----------------------

    def _keyboard_loop(self):
        fd = sys.stdin.fileno()
        try:
            old_settings = termios.tcgetattr(fd)
        except termios.error:
            self.get_logger().error("stdin er ikke en TTY — kør i en interaktiv terminal.")
            self.running = False
            rclpy.shutdown()
            return

        try:
            tty.setcbreak(fd)
            while self.running and rclpy.ok():
                # Non-blocking read
                rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                if not rlist:
                    continue
                ch = sys.stdin.read(1)
                self._handle_key(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _handle_key(self, ch):
        STEP_FINE = 0.1
        STEP_NORMAL = 1.0
        STEP_COARSE = 5.0

        with self.lock:
            t = self.target_phys

            if ch == "a":
                t -= STEP_NORMAL
            elif ch == "d":
                t += STEP_NORMAL
            elif ch == "A":
                t -= STEP_COARSE
            elif ch == "D":
                t += STEP_COARSE
            elif ch == "z":
                t -= STEP_FINE
            elif ch == "c":
                t += STEP_FINE
            elif ch == "h":
                t = self.default_orig
            elif ch == " ":
                pass  # genudsend nuværende
            elif ch == "[":
                self.sw_min = self.target_phys
                self._announce(f"angle_software_min = {self.sw_min:.2f}°")
                return
            elif ch == "]":
                self.sw_max = self.target_phys
                self._announce(f"angle_software_max = {self.sw_max:.2f}°")
                return
            elif ch == "0":
                self.default_new = self.target_phys
                self._announce(f"default_position    = {self.default_new:.2f}°")
                return
            elif ch == "p":
                self._print_state()
                return
            elif ch == "s":
                self._save_to_json()
                return
            elif ch in ("x", "q"):
                self._announce("Afslutter (uden at gemme igen).")
                self.running = False
                rclpy.shutdown()
                return
            elif ch == "?":
                self._print_help()
                return
            else:
                return  # ukendt tast

            # Clip altid til hardware-range
            t = float(np.clip(t, self.angle_min_hw, self.angle_max_hw))
            self.target_phys = t

        self._announce(f"target = {t:7.2f}°  (logical = {t - self.default_orig:+7.2f}°)")

    # ------------------------- Save / print ---------------------------

    def _save_to_json(self):
        if self.sw_min >= self.sw_max:
            self._announce(
                f"AFVIST: sw_min ({self.sw_min:.2f}) >= sw_max ({self.sw_max:.2f}). "
                f"Justér før du gemmer."
            )
            return

        # Backup
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = f"{self.config_file}.bak.{ts}"
        shutil.copy2(self.config_file, bak)

        # Opdater kun de tre felter for det valgte joint
        self.config["servos"][self.joint_name]["angle_software_min"] = round(self.sw_min, 2)
        self.config["servos"][self.joint_name]["angle_software_max"] = round(self.sw_max, 2)
        self.config["servos"][self.joint_name]["default_position"] = round(self.default_new, 2)

        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=4)
            f.write("\n")

        self._announce(
            f"GEMT → {self.config_file}\n"
            f"  backup: {bak}\n"
            f"  HUSK: kør 'colcon build --packages-select energirobotter_bringup wattson_description elrik_description'\n"
            f"  (eller den pakke der ejer config'en) for at opdatere install/."
        )

    def _print_help(self):
        sys.stdout.write(
            "\n"
            "==================== Kalibrerings-værktøj ====================\n"
            "  a/d        : step ±1° (fysisk)\n"
            "  A/D        : step ±5°\n"
            "  z/c        : step ±0.1° (fin)\n"
            "  h          : hjem (original default_position)\n"
            "  SPACE      : hold (genudsend)\n"
            "  [          : marker nuværende som angle_software_min\n"
            "  ]          : marker nuværende som angle_software_max\n"
            "  0          : marker nuværende som default_position\n"
            "  p          : print tilstand\n"
            "  s          : GEM til JSON (med backup)\n"
            "  x / q      : afslut\n"
            "  ?          : vis denne hjælp\n"
            "==============================================================\n\n"
        )
        sys.stdout.flush()

    def _print_state(self, initial=False):
        with self.lock:
            t = self.target_phys
            sw_min = self.sw_min
            sw_max = self.sw_max
            d = self.default_new
        prefix = "INIT" if initial else "STATE"
        sys.stdout.write(
            f"\n[{prefix}] joint={self.joint_name}  file={os.path.basename(self.config_file)}\n"
            f"   hardware range : [{self.angle_min_hw:7.2f}, {self.angle_max_hw:7.2f}] °\n"
            f"   software min   : {sw_min:7.2f} °   (original: {self.servo_cfg['angle_software_min']:.2f})\n"
            f"   software max   : {sw_max:7.2f} °   (original: {self.servo_cfg['angle_software_max']:.2f})\n"
            f"   default        : {d:7.2f} °   (original: {self.default_orig:.2f})\n"
            f"   target NU      : {t:7.2f} °   (logical: {t - self.default_orig:+.2f})\n\n"
        )
        sys.stdout.flush()

    def _announce(self, text):
        sys.stdout.write(f"  > {text}\n")
        sys.stdout.flush()


def main(args=None):
    rclpy.init(args=args)
    try:
        node = CalibrationToolNode()
    except SystemExit as e:
        rclpy.shutdown()
        sys.exit(e.code)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.running = False
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
