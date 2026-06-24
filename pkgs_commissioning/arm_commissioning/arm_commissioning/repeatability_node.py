"""Repeterbarheds-måling for én ST3215-servo.

Alternerer mellem pose_a og pose_b i N cyklusser, logger faktisk
position ved hver hold-fases afslutning, og skriver CSV + histogram-PNG
med std / max-deviation pr. pose.

Eksempel:
    ros2 run arm_commissioning repeatability_node --ros-args \\
        -p joint_name:=joint_left_shoulder_pitch \\
        -p pose_a_deg:=0.0 -p pose_b_deg:=20.0 -p cycles:=10
"""

import csv
import os
from datetime import datetime

import numpy as np

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class RepeatabilityNode(Node):
    def __init__(self):
        super().__init__("repeatability_node")

        # Parameters
        self.declare_parameter("joint_name", "")
        self.declare_parameter("pose_a_deg", 0.0)
        self.declare_parameter("pose_b_deg", 20.0)
        self.declare_parameter("cycles", 10)
        self.declare_parameter("hold_s", 1.5)
        self.declare_parameter("publish_rate", 50.0)
        self.declare_parameter(
            "output_dir", os.path.expanduser("~/humanoid_ws/test_results")
        )

        self.joint_name = self.get_parameter("joint_name").value
        self.pose_a = float(self.get_parameter("pose_a_deg").value)
        self.pose_b = float(self.get_parameter("pose_b_deg").value)
        self.cycles = int(self.get_parameter("cycles").value)
        self.hold_s = float(self.get_parameter("hold_s").value)
        self.publish_rate = float(self.get_parameter("publish_rate").value)
        self.output_dir = str(self.get_parameter("output_dir").value)

        if not self.joint_name:
            self.get_logger().error("joint_name skal angives med -p joint_name:=...")
            raise SystemExit(2)

        # Output dir
        date_dir = datetime.now().strftime("%Y-%m-%d")
        self.run_dir = os.path.join(self.output_dir, date_dir, self.joint_name)
        os.makedirs(self.run_dir, exist_ok=True)
        self.run_stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

        # ROS I/O
        self.pub_cmd = self.create_publisher(JointState, "/joint_states", 10)
        self.sub_fb = self.create_subscription(
            JointState, "/joint_states_feedback", self._on_feedback, 50
        )
        self.timer = self.create_timer(1.0 / self.publish_rate, self._tick)

        # Scheduler-state
        self.t_start = self.get_clock().now()
        self.cycle = 0
        # phase 0 = mod A og hold; phase 1 = mod B og hold
        self.phase = 0
        self.phase_start_s = 0.0
        self.last_feedback_deg = None

        self.measurements_a = []
        self.measurements_b = []
        self.finished = False

        total_s = self.cycles * 2 * self.hold_s
        self.get_logger().info(
            f"repeatability_node klar — joint='{self.joint_name}', "
            f"A={self.pose_a}°, B={self.pose_b}°, cycles={self.cycles}, "
            f"hold={self.hold_s}s. Estimeret varighed: {total_s:.1f}s. "
            f"Output i {self.run_dir}/"
        )

    # ---------------------- ROS callbacks ----------------------

    def _elapsed_s(self):
        return (self.get_clock().now() - self.t_start).nanoseconds * 1e-9

    def _target(self):
        return self.pose_a if self.phase == 0 else self.pose_b

    def _tick(self):
        if self.finished:
            return

        now = self._elapsed_s()
        if now - self.phase_start_s >= self.hold_s:
            if self.last_feedback_deg is not None:
                if self.phase == 0:
                    self.measurements_a.append(self.last_feedback_deg)
                else:
                    self.measurements_b.append(self.last_feedback_deg)

            # advance
            if self.phase == 0:
                self.phase = 1
            else:
                self.phase = 0
                self.cycle += 1
                if self.cycle >= self.cycles:
                    self._finalise()
                    return

            self.phase_start_s = now

        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = [self.joint_name]
        msg.position = [float(np.deg2rad(self._target()))]
        self.pub_cmd.publish(msg)

    def _on_feedback(self, msg: JointState):
        if self.finished or self.joint_name not in msg.name:
            return
        idx = msg.name.index(self.joint_name)
        self.last_feedback_deg = float(np.rad2deg(msg.position[idx]))

    # ---------------------- finalise ---------------------------

    def _finalise(self):
        self.finished = True
        n_a = len(self.measurements_a)
        n_b = len(self.measurements_b)
        if n_a == 0 or n_b == 0:
            self.get_logger().error(
                "Ingen feedback registreret i den ene eller begge poser. "
                "Verificér at /joint_states_feedback publiceres."
            )
            rclpy.shutdown()
            return

        csv_path = os.path.join(self.run_dir, f"{self.run_stamp}_repeat.csv")
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["cycle", "final_at_A_deg", "final_at_B_deg"])
            for i in range(max(n_a, n_b)):
                a = self.measurements_a[i] if i < n_a else ""
                b = self.measurements_b[i] if i < n_b else ""
                w.writerow([i + 1, a, b])
        self.get_logger().info(f"CSV gemt: {csv_path}")

        stats = self._stats()
        self._print_stats(stats)

        png_path = os.path.join(self.run_dir, f"{self.run_stamp}_repeat.png")
        self._plot(stats, png_path)
        self.get_logger().info(f"Plot gemt: {png_path}")

        rclpy.shutdown()

    def _stats(self):
        def s(arr, target):
            arr = np.asarray(arr, dtype=float)
            return {
                "n": int(arr.size),
                "target_deg": float(target),
                "mean_deg": float(np.mean(arr)),
                "std_deg": float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
                "max_dev_deg": float(np.max(np.abs(arr - target))),
                "range_deg": float(np.max(arr) - np.min(arr)),
                "values": arr.tolist(),
            }

        return {
            "A": s(self.measurements_a, self.pose_a),
            "B": s(self.measurements_b, self.pose_b),
        }

    def _print_stats(self, stats):
        self.get_logger().info("=== Repeterbarhed ===")
        for key in ("A", "B"):
            s = stats[key]
            self.get_logger().info(
                f"  Pose {key} (target {s['target_deg']:.3f}°, n={s['n']}): "
                f"mean={s['mean_deg']:.3f}°, std={s['std_deg']:.4f}°, "
                f"max_dev={s['max_dev_deg']:.4f}°, range={s['range_deg']:.4f}°"
            )

    # ---------------------- plotting ---------------------------

    def _plot(self, stats, path):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        for ax, key, color in zip(axes, ("A", "B"), ("tab:blue", "tab:orange")):
            s = stats[key]
            vals = np.array(s["values"])
            bins = max(5, min(15, s["n"]))
            ax.hist(vals, bins=bins, color=color, alpha=0.7, edgecolor="black")
            ax.axvline(
                s["target_deg"],
                color="red",
                linestyle="--",
                linewidth=1.5,
                label=f"target {s['target_deg']:.2f}°",
            )
            ax.axvline(
                s["mean_deg"],
                color="black",
                linestyle=":",
                linewidth=1.5,
                label=f"mean {s['mean_deg']:.3f}°",
            )
            ax.set_title(
                f"Pose {key} — std={s['std_deg']:.4f}°, "
                f"max_dev={s['max_dev_deg']:.4f}°"
            )
            ax.set_xlabel("Faktisk vinkel [°]")
            ax.set_ylabel("Antal")
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)

        fig.suptitle(
            f"Repeterbarhed — {self.joint_name} (n={stats['A']['n']} cyklusser)"
        )
        fig.tight_layout()
        fig.savefig(path, dpi=120)
        plt.close(fig)


def main(args=None):
    rclpy.init(args=args)
    try:
        node = RepeatabilityNode()
    except SystemExit:
        rclpy.shutdown()
        return
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
