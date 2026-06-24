"""Live viewer + recorder for robotens strømforbrug.

Abonnerer på /servo_power (publiceret af wattson_servo_manager),
logger til CSV og kan vise en live matplotlib-graf med total effekt
over tid + per-servo bar chart.

Måler kun servo-bussen — Jetson, ZED, ESP32 og PSU-konverteringstab
er ikke inkluderet.

Eksempler:
    # Live viewer (matplotlib-vindue), idle, 30 sek
    ros2 run arm_commissioning power_monitor_node --ros-args \\
        -p scenario:=idle -p duration_s:=30.0 -p live:=true

    # Headless logging (SSH uden X11)
    ros2 run arm_commissioning power_monitor_node --ros-args \\
        -p scenario:=animation_idle1 -p duration_s:=60.0 -p live:=false
"""

import csv
import os
from collections import deque
from datetime import datetime

import numpy as np

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class PowerMonitorNode(Node):
    def __init__(self):
        super().__init__("power_monitor_node")

        # Parameters
        self.declare_parameter("scenario", "default")
        self.declare_parameter("duration_s", 30.0)
        self.declare_parameter("live", True)
        # Live-vinduet holder kun de seneste N sekunder.
        self.declare_parameter("live_window_s", 20.0)
        self.declare_parameter(
            "output_dir",
            os.path.expanduser("~/humanoid_ws/test_results"),
        )

        self.scenario = str(self.get_parameter("scenario").value)
        self.duration_s = float(self.get_parameter("duration_s").value)
        self.live = bool(self.get_parameter("live").value)
        self.live_window_s = float(self.get_parameter("live_window_s").value)
        self.output_dir = str(self.get_parameter("output_dir").value)

        date_dir = datetime.now().strftime("%Y-%m-%d")
        self.run_dir = os.path.join(self.output_dir, date_dir, self.scenario)
        os.makedirs(self.run_dir, exist_ok=True)
        self.run_stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

        # ROS I/O
        self.sub_power = self.create_subscription(
            JointState, "/servo_power", self._on_power, 50
        )

        # Recording state — store (t_s, name_list, V_list, A_list, W_list)
        self.t_start = self.get_clock().now()
        self.samples = []  # one row per /servo_power message
        self.servo_names = None  # stable order, set on first message
        self.finished = False

        # Watchdog — afslut præcist når duration_s nås.
        self.watchdog = self.create_timer(0.2, self._check_duration)

        # Live-viewer state
        self._fig = None
        self._anim = None
        self._live_buf = None

        self.get_logger().info(
            f"power_monitor_node klar — scenario='{self.scenario}', "
            f"duration={self.duration_s}s, live={self.live}. "
            f"Output i {self.run_dir}/"
        )

    # ---------------------- ROS callbacks ----------------------

    def _elapsed_s(self):
        dt = self.get_clock().now() - self.t_start
        return dt.nanoseconds * 1e-9

    def _on_power(self, msg: JointState):
        if self.finished:
            return

        # Stable order locked in on first message
        if self.servo_names is None:
            self.servo_names = list(msg.name)
            if self.live:
                self._init_live_viewer()

        # Re-align in case manager publishes in slightly different order
        name_to_idx = {n: i for i, n in enumerate(msg.name)}
        voltages = [float(msg.position[name_to_idx[n]]) if n in name_to_idx else np.nan
                    for n in self.servo_names]
        currents = [float(msg.velocity[name_to_idx[n]]) if n in name_to_idx else np.nan
                    for n in self.servo_names]
        powers = [float(msg.effort[name_to_idx[n]]) if n in name_to_idx else np.nan
                  for n in self.servo_names]

        t = self._elapsed_s()
        self.samples.append((t, voltages, currents, powers))

        if self.live and self._live_buf is not None:
            self._live_buf.append((t, voltages, currents, powers))

    def _check_duration(self):
        if self.finished:
            return
        if self._elapsed_s() >= self.duration_s:
            self._finalise()

    # ---------------------- finalise ---------------------------

    def _finalise(self):
        self.finished = True

        if not self.samples or self.servo_names is None:
            self.get_logger().error(
                "Ingen /servo_power samples modtaget. Er servo_manager "
                "kørende, og er feedback_enabled=True for servoerne?"
            )
            self._shutdown_anim()
            rclpy.shutdown()
            return

        # Write CSV: t_s, V_<servo1>, V_<servo2>..., A_<...>, W_<...>, total_W
        csv_path = os.path.join(self.run_dir, f"{self.run_stamp}_power.csv")
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            header = ["t_s"]
            header += [f"V_{n}" for n in self.servo_names]
            header += [f"A_{n}" for n in self.servo_names]
            header += [f"W_{n}" for n in self.servo_names]
            header += ["total_W"]
            w.writerow(header)
            for t, V, A, W in self.samples:
                # Sum ignorerer NaN så delvise samples ikke ødelægger totalen.
                total = float(np.nansum(W))
                w.writerow([f"{t:.4f}"] + V + A + W + [f"{total:.4f}"])
        self.get_logger().info(f"CSV gemt: {csv_path}")

        # Compute summary metrics on total power
        ts = np.array([s[0] for s in self.samples])
        W_matrix = np.array([s[3] for s in self.samples])  # (n_samples, n_servos)
        total_W = np.nansum(W_matrix, axis=1)

        metrics = {
            "samples": int(len(self.samples)),
            "duration_s": float(ts[-1] - ts[0]) if len(ts) > 1 else 0.0,
            "avg_total_W": float(np.mean(total_W)),
            "peak_total_W": float(np.max(total_W)),
            "min_total_W": float(np.min(total_W)),
            "stddev_total_W": float(np.std(total_W)),
            "per_servo_avg_W": {
                self.servo_names[i]: float(np.nanmean(W_matrix[:, i]))
                for i in range(len(self.servo_names))
            },
        }

        # Plot
        png_path = os.path.join(self.run_dir, f"{self.run_stamp}_power.png")
        self._plot_summary(ts, W_matrix, total_W, metrics, png_path)
        self.get_logger().info(f"Plot gemt: {png_path}")

        self._print_metrics(metrics)
        self._shutdown_anim()
        rclpy.shutdown()

    def _print_metrics(self, m):
        self.get_logger().info(
            f"=== Power summary ({self.scenario}) ==="
        )
        self.get_logger().info(
            f"  varighed         = {m['duration_s']:.2f} s ({m['samples']} samples)"
        )
        self.get_logger().info(
            f"  gennemsnitlig W  = {m['avg_total_W']:.2f}"
        )
        self.get_logger().info(
            f"  peak W           = {m['peak_total_W']:.2f}"
        )
        self.get_logger().info(
            f"  min W            = {m['min_total_W']:.2f}"
        )
        self.get_logger().info(
            f"  std W            = {m['stddev_total_W']:.2f}"
        )
        # Top 5 strømslugere
        top = sorted(
            m["per_servo_avg_W"].items(), key=lambda kv: kv[1], reverse=True
        )[:5]
        self.get_logger().info("  top 5 (avg W pr. servo):")
        for name, avg in top:
            self.get_logger().info(f"    {avg:6.2f}  {name}")

    # ---------------------- plotting ---------------------------

    def _plot_summary(self, ts, W_matrix, total_W, metrics, path):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, (ax_total, ax_bar) = plt.subplots(
            2, 1, figsize=(11, 7),
            gridspec_kw={"height_ratios": [2, 1]},
        )

        # Top: total W over tid
        ax_total.plot(ts, total_W, color="tab:red", linewidth=1.2, label="Total")
        ax_total.axhline(
            metrics["avg_total_W"], color="tab:gray",
            linestyle="--", linewidth=1.0,
            label=f"Gennemsnit ({metrics['avg_total_W']:.2f} W)",
        )
        ax_total.set_xlabel("Tid [s]")
        ax_total.set_ylabel("Effekt [W]")
        ax_total.set_title(f"Strømforbrug — scenarie: {self.scenario}")
        ax_total.grid(True, alpha=0.3)
        ax_total.legend(loc="upper right")

        txt = (
            f"Peak  : {metrics['peak_total_W']:.2f} W\n"
            f"Avg   : {metrics['avg_total_W']:.2f} W\n"
            f"Min   : {metrics['min_total_W']:.2f} W\n"
            f"Std   : {metrics['stddev_total_W']:.2f} W\n"
            f"Sampl : {metrics['samples']}"
        )
        ax_total.text(
            0.98, 0.97, txt,
            transform=ax_total.transAxes,
            fontsize=9, family="monospace",
            ha="right", va="top",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      alpha=0.9, edgecolor="lightgray"),
        )

        # Bund: per-servo gennemsnit som vandret bar chart (top 12)
        items = sorted(
            metrics["per_servo_avg_W"].items(), key=lambda kv: kv[1]
        )
        items = items[-12:] if len(items) > 12 else items
        names = [n for n, _ in items]
        vals = [v for _, v in items]
        colors = ["tab:orange" if v >= 0 else "tab:blue" for v in vals]
        ax_bar.barh(names, vals, color=colors)
        ax_bar.set_xlabel("Gennemsnitlig effekt [W]")
        ax_bar.set_title("Top 12 strømslugere (negativ = regenerativ)")
        ax_bar.grid(True, axis="x", alpha=0.3)

        fig.tight_layout()
        fig.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)

    # ---------------------- live viewer ------------------------

    def _init_live_viewer(self):
        # Åbn live matplotlib-vindue (fallback til headless ved fejl).
        try:
            import matplotlib
            import matplotlib.pyplot as plt
            from matplotlib.animation import FuncAnimation
        except ImportError as e:
            self.get_logger().warn(
                f"matplotlib ikke tilgængelig ({e}) — kører headless."
            )
            self.live = False
            return

        try:
            # Skift fra Agg (headless) til TkAgg hvis muligt.
            current_backend = matplotlib.get_backend().lower()
            if current_backend == "agg":
                matplotlib.use("TkAgg", force=True)
        except Exception as e:
            self.get_logger().warn(
                f"Kan ikke skifte til interaktiv backend ({e}) — kører headless."
            )
            self.live = False
            return

        # Reimport efter backend-skift.
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation

        max_pts = max(100, int(self.live_window_s * 60))  # buffer ved 60 Hz
        self._live_buf = deque(maxlen=max_pts)

        self._fig, (ax_line, ax_bar) = plt.subplots(
            2, 1, figsize=(10, 6),
            gridspec_kw={"height_ratios": [2, 1]},
        )
        self._fig.canvas.manager.set_window_title(
            f"Robot Power Monitor — {self.scenario}"
        )

        ax_line.set_xlabel("Tid [s]")
        ax_line.set_ylabel("Total effekt [W]")
        ax_line.set_title(f"Live wattage — scenarie: {self.scenario}")
        ax_line.grid(True, alpha=0.3)
        (self._line_total,) = ax_line.plot([], [], color="tab:red", linewidth=1.2)

        ax_bar.set_xlabel("Servo")
        ax_bar.set_ylabel("Effekt [W]")
        ax_bar.set_title("Per-servo (live)")
        ax_bar.tick_params(axis="x", labelrotation=75, labelsize=7)
        ax_bar.grid(True, axis="y", alpha=0.3)
        self._bars = ax_bar.bar(self.servo_names, [0.0] * len(self.servo_names))
        self._ax_line = ax_line
        self._ax_bar = ax_bar

        def _update(_frame):
            if not self._live_buf:
                return ()
            data = list(self._live_buf)
            ts = [d[0] for d in data]
            totals = [float(np.nansum(d[3])) for d in data]
            self._line_total.set_data(ts, totals)
            if ts:
                ax_line.set_xlim(max(0.0, ts[-1] - self.live_window_s), max(ts[-1], 1e-3))
                ymax = max(1.0, max(totals) * 1.15)
                ymin = min(0.0, min(totals) * 1.15)
                ax_line.set_ylim(ymin, ymax)
            last_W = data[-1][3]
            for bar, w in zip(self._bars, last_W):
                bar.set_height(w if not np.isnan(w) else 0.0)
            # Filtrer NaN saa max() ikke crasher hvis alle samples er NaN.
            valid = [abs(w) for w in last_W if not np.isnan(w)]
            top = max(1.0, max(valid) * 1.15) if valid else 1.0
            ax_bar.set_ylim(-top, top)
            return (self._line_total, *self._bars)

        self._anim = FuncAnimation(
            self._fig, _update, interval=100, blit=False, cache_frame_data=False
        )
        # Non-blocking: lille ROS-timer pumper matplotlib-event-loop'en.
        plt.show(block=False)
        self.create_timer(0.05, self._pump_gui)

    def _pump_gui(self):
        if self._fig is None:
            return
        try:
            import matplotlib.pyplot as plt
            plt.pause(0.001)
        except Exception:
            pass

    def _shutdown_anim(self):
        try:
            if self._anim is not None:
                self._anim.event_source.stop()
            if self._fig is not None:
                import matplotlib.pyplot as plt
                plt.close(self._fig)
        except Exception:
            pass


def main(args=None):
    rclpy.init(args=args)
    try:
        node = PowerMonitorNode()
    except SystemExit:
        rclpy.shutdown()
        return
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        if not node.finished:
            node._finalise()
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
