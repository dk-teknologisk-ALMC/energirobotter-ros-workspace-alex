"""Step-respons-måling for én ST3215-servo.

Holder 0° i et baseline-vindue, kommanderer derefter et step på
step_size_deg og logger (t, cmd, actual) pr. feedback-meddelelse.
Skriver CSV + plot med rise time, overshoot, settling time og
steady-state error.

Eksempel:
    ros2 run arm_commissioning step_response_node --ros-args \\
        -p joint_name:=joint_left_shoulder_pitch \\
        -p step_size_deg:=10.0 -p duration_s:=3.0
"""

import csv
import os
from datetime import datetime

import numpy as np

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class StepResponseNode(Node):
    def __init__(self):
        super().__init__("step_response_node")

        # Parameters
        self.declare_parameter("joint_name", "")
        self.declare_parameter("step_size_deg", 10.0)
        self.declare_parameter("baseline_s", 0.5)
        self.declare_parameter("duration_s", 3.0)
        self.declare_parameter("publish_rate", 50.0)
        # Settling-tolerance i procent af step-størrelse.
        self.declare_parameter("settling_tol_pct", 10.0)
        self.declare_parameter(
            "output_dir",
            os.path.expanduser("~/humanoid_ws/test_results"),
        )

        self.joint_name = self.get_parameter("joint_name").value
        self.step_size_deg = float(self.get_parameter("step_size_deg").value)
        self.baseline_s = float(self.get_parameter("baseline_s").value)
        self.duration_s = float(self.get_parameter("duration_s").value)
        self.publish_rate = float(self.get_parameter("publish_rate").value)
        self.settling_tol_pct = float(self.get_parameter("settling_tol_pct").value)
        self.output_dir = str(self.get_parameter("output_dir").value)

        if not self.joint_name:
            self.get_logger().error(
                "joint_name skal angives med -p joint_name:=..."
            )
            raise SystemExit(2)

        date_dir = datetime.now().strftime("%Y-%m-%d")
        self.run_dir = os.path.join(self.output_dir, date_dir, self.joint_name)
        os.makedirs(self.run_dir, exist_ok=True)
        self.run_stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

        # ROS I/O
        self.pub_cmd = self.create_publisher(JointState, "/joint_states", 10)
        self.sub_fb = self.create_subscription(
            JointState, "/joint_states_feedback", self._on_feedback, 50
        )
        self.timer = self.create_timer(
            1.0 / self.publish_rate, self._publish_command
        )

        # State
        self.t_start = self.get_clock().now()
        self.samples = []  # list of (t_s, cmd_deg, actual_deg)
        self.finished = False

        self.get_logger().info(
            f"step_response_node klar — joint='{self.joint_name}', "
            f"step={self.step_size_deg}°, baseline={self.baseline_s}s, "
            f"total={self.duration_s}s. Output i {self.run_dir}/"
        )

    # ---------------------- ROS callbacks ----------------------

    def _elapsed_s(self):
        dt = self.get_clock().now() - self.t_start
        return dt.nanoseconds * 1e-9

    def _current_command_deg(self):
        if self._elapsed_s() < self.baseline_s:
            return 0.0
        return self.step_size_deg

    def _publish_command(self):
        if self.finished:
            return

        if self._elapsed_s() >= self.duration_s:
            self._finalise()
            return

        cmd_deg = self._current_command_deg()
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = [self.joint_name]
        msg.position = [float(np.deg2rad(cmd_deg))]
        self.pub_cmd.publish(msg)

    def _on_feedback(self, msg: JointState):
        if self.finished:
            return
        if self.joint_name not in msg.name:
            return
        idx = msg.name.index(self.joint_name)
        actual_deg = float(np.rad2deg(msg.position[idx]))
        cmd_deg = self._current_command_deg()
        self.samples.append((self._elapsed_s(), cmd_deg, actual_deg))

    # ---------------------- finalise ---------------------------

    def _finalise(self):
        self.finished = True

        if not self.samples:
            self.get_logger().error(
                "Ingen feedback-samples modtaget. Er servo_manager kørende, "
                "og publicerer den /joint_states_feedback?"
            )
            rclpy.shutdown()
            return

        # Write CSV
        csv_path = os.path.join(
            self.run_dir, f"{self.run_stamp}_step.csv"
        )
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t_s", "cmd_deg", "actual_deg"])
            w.writerows(self.samples)
        self.get_logger().info(f"CSV gemt: {csv_path}")

        # Compute response metrics on the post-step region
        t = np.array([s[0] for s in self.samples])
        cmd = np.array([s[1] for s in self.samples])
        act = np.array([s[2] for s in self.samples])
        metrics = self._compute_metrics(t, cmd, act)

        # Plot
        png_path = os.path.join(
            self.run_dir, f"{self.run_stamp}_step.png"
        )
        self._plot(t, cmd, act, metrics, png_path)
        self.get_logger().info(f"Plot gemt: {png_path}")

        # Print summary
        self._print_metrics(metrics)

        rclpy.shutdown()

    # ---------------------- analysis ---------------------------

    def _compute_metrics(self, t, cmd, act):
        # cmd er logisk delta fra default_position; act er fysisk vinkel.
        # Normaliser act ved at trække baseline-gennemsnittet fra, så
        # begge størrelser er delta fra baseline og sammenlignelige.
        post = t >= self.baseline_s
        if not np.any(post):
            return {}

        pre = t < self.baseline_s
        a0_phys = float(np.mean(act[pre])) if np.any(pre) else float(act[post][0])

        tp = t[post] - self.baseline_s  # tid relativt til step-tidspunkt
        ap = act[post] - a0_phys  # normaliseret actual (delta fra baseline)
        target = self.step_size_deg
        a0 = 0.0

        delta = target - a0
        if abs(delta) < 1e-6:
            return {"note": "step_size = 0 — kan ikke beregne respons-mål"}

        thresh_10 = a0 + 0.1 * delta
        thresh_90 = a0 + 0.9 * delta
        t_10 = self._first_crossing(tp, ap, thresh_10, delta)
        t_90 = self._first_crossing(tp, ap, thresh_90, delta)
        rise_time = (t_90 - t_10) if (t_10 is not None and t_90 is not None) else None

        if delta > 0:
            peak = float(np.max(ap))
            overshoot_pct = max(0.0, (peak - target) / abs(delta) * 100.0)
        else:
            peak = float(np.min(ap))
            overshoot_pct = max(0.0, (target - peak) / abs(delta) * 100.0)

        # Settling: første tidspunkt hvor |actual - target| <= tol og forbliver der.
        tol = (self.settling_tol_pct / 100.0) * abs(delta)
        within = np.abs(ap - target) <= tol
        settling_time = None
        for i in range(len(tp)):
            if within[i] and np.all(within[i:]):
                settling_time = float(tp[i])
                break

        steady_state_error = float(ap[-1] - target)

        return {
            "baseline_phys_deg": a0_phys,
            "target_delta_deg": float(target),
            "rise_time_s": rise_time,
            "overshoot_pct": float(overshoot_pct),
            "settling_time_s": settling_time,
            "steady_state_error_deg": steady_state_error,
            "n_samples": int(len(self.samples)),
        }

    @staticmethod
    def _first_crossing(t, y, level, delta):
        if delta > 0:
            mask = y >= level
        else:
            mask = y <= level
        idxs = np.where(mask)[0]
        if len(idxs) == 0:
            return None
        return float(t[idxs[0]])

    def _print_metrics(self, m):
        if not m:
            return
        self.get_logger().info("=== Step-respons resultat ===")
        for k, v in m.items():
            if isinstance(v, float):
                self.get_logger().info(f"  {k:24s} = {v:.4f}")
            else:
                self.get_logger().info(f"  {k:24s} = {v}")

    # ---------------------- plotting ---------------------------

    def _plot(self, t, cmd, act, metrics, path):
        # Lazy import så matplotlib ikke loades hvis vi afslutter tidligt.
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Normalisér actual til delta fra baseline (direkte sammenligneligt
        # med kommandoen, som er logisk vinkel).
        baseline_phys = float(metrics.get("baseline_phys_deg", 0.0))
        act_norm = act - baseline_phys

        fig, ax = plt.subplots(figsize=(11, 5.5))
        ax.plot(t, cmd, label="Kommando (logisk Δ)", color="tab:blue", linewidth=1.5)
        ax.plot(t, act_norm, label=f"Faktisk (Δ fra {baseline_phys:.1f}°)", color="tab:orange", linewidth=1.5)
        ax.axvline(
            self.baseline_s,
            color="gray",
            linestyle="--",
            alpha=0.6,
            label="Step-tidspunkt",
        )

        ax.set_xlabel("Tid [s]")
        ax.set_ylabel("Vinkel-delta [°]")
        ax.set_title(f"Step-respons — {self.joint_name}")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left")

        if metrics:
            label_map = {
                "rise_time_s":            "Stigningstid (10→90%)",
                "overshoot_pct":          "Oversving",
                "settling_time_s":        f"Indstillingstid (±{self.settling_tol_pct:.0f}%)",
                "steady_state_error_deg": "Slutfejl",
                "baseline_phys_deg":      "Start-vinkel",
                "target_delta_deg":       "Mål-bevægelse",
                "n_samples":              "Antal samples",
            }
            unit_map = {
                "rise_time_s":            "s",
                "overshoot_pct":          "%",
                "settling_time_s":        "s",
                "steady_state_error_deg": "°",
                "baseline_phys_deg":      "°",
                "target_delta_deg":       "°",
                "n_samples":              "",
            }
            txt_lines = []
            for k in ("rise_time_s", "overshoot_pct", "settling_time_s",
                      "steady_state_error_deg", "start-vinkel-spacer",
                      "baseline_phys_deg", "target_delta_deg", "n_samples"):
                if k == "start-vinkel-spacer":
                    txt_lines.append("")
                    continue
                v = metrics.get(k)
                if v is None:
                    val_s = "—"
                elif isinstance(v, float):
                    val_s = f"{v:.2f}"
                else:
                    val_s = str(v)
                unit = unit_map.get(k, "")
                txt_lines.append(f"{label_map[k]:<24s} {val_s:>7s} {unit}")
            if txt_lines:
                ax.text(
                    0.98,
                    0.02,
                    "\n".join(txt_lines),
                    transform=ax.transAxes,
                    fontsize=9,
                    family="monospace",
                    ha="right",
                    va="bottom",
                    bbox=dict(
                        boxstyle="round,pad=0.5",
                        facecolor="white",
                        alpha=0.95,
                        edgecolor="lightgray",
                    ),
                )

        fig.tight_layout()
        fig.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)


def main(args=None):
    rclpy.init(args=args)
    try:
        node = StepResponseNode()
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
