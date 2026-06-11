"""
launcher_gui_node — én-vindue demo-launcher for Wattson.

Til eksamens-demo og generelt arbejde hvor man ikke gider åbne 5-6
terminaler manuelt. Værktøjet:

  1. Viser en pre-flight checklist for de skridt der IKKE kan automatiseres
     (USB-rækkefølge, ESP32 Serial Forwarding, Quest USB-debugging).
  2. Tilbyder Start/Stop pr. service med live-status (kører / stoppet).
  3. Sender alle stdout/stderr-strømme ind i én log-rude i GUI'en så man
     ikke skal klikke rundt mellem vinduer for at se fejl.
  4. Har en "Start demo"-knap der starter de typiske demo-services i den
     rigtige rækkefølge.

Brug:
    ros2 run arm_commissioning launcher_gui

Det er bevidst IKKE en ROS-node (importerer ikke rclpy) — det er bare et
tkinter-program der shell'er ud til `ros2 launch`/`ros2 run`/ssh/pkexec.
At placere det i arm_commissioning sparer en hel ROS-pakke for noget der
i bund og grund er et lille hjælpe-script.
"""

import os
import shlex
import signal
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext

# ----------------------------------------------------------------------
# Konfiguration — opdater her hvis IP/host/Wi-Fi-navne ændrer sig
# ----------------------------------------------------------------------

JETSON_HOST = "elrik@192.168.1.105"
JETSON_SOURCES = (
    "source /opt/ros/humble/setup.bash"
    " && source ~/energinet/install/setup.bash"
)

# Sourcing-prefix for lokale ROS-kommandoer. shell-string der prepends
# foran service-kommandoer der har needs_ros_source=True.
LOCAL_ROS_SOURCES = (
    "source /opt/ros/humble/setup.bash"
    " && source $HOME/humanoid_ws/install/setup.bash"
)

# Hver service-spec:
#   key:              intern nøgle, vises i log som [key]
#   label:            menneske-læselig tekst i GUI
#   section:          gruppering i GUI'en
#   command:          shell-streng der kører som bash-c
#   needs_ros_source: hvis True, prepends LOCAL_ROS_SOURCES
SERVICES = [
    # --- Network / forudsætninger ---
    {
        "key": "dhcp",
        "label": "DHCP server (dnsmasq)",
        "section": "Network",
        # pkexec åbner et grafisk passwordprompt så vi ikke skal embedde
        # password i GUI'en. Bruger Polkit's standard auth-dialog.
        "command": (
            "pkexec dnsmasq --no-daemon --port=0"
            " --interface=enp0s31f6 --bind-interfaces"
            " --dhcp-range=192.168.1.100,192.168.1.200,255.255.255.0,1h"
            " --dhcp-host=48:b0:2d:eb:e3:58,192.168.1.105,elrik-jetson"
            " --log-dhcp"
        ),
        # dnsmasq kører som root via pkexec, så vores bruger kan ikke
        # signalere det direkte. Stop via pkexec (prompter for password
        # igen, eller bruger Polkit-cache hvis under timeout).
        "stop_command": "pkexec pkill -TERM dnsmasq",
    },
    {
        "key": "adb_reverse",
        "label": "adb reverse (Quest port-forward)",
        "section": "Network",
        # Vi vil gerne kunne stoppe denne som en "service"; men kommandoen
        # er sekund-hurtig. Derfor wrapper vi i en sleep-loop så processen
        # bliver "kørende" og man tydeligt ser den i GUI'en. Stop-knappen
        # afbryder loopet.
        "command": (
            "adb devices"
            " && adb reverse tcp:8012 tcp:8012"
            " && echo '[adb_reverse] aktiv — port 8012 forwarded'"
            " && while true; do sleep 30; done"
        ),
    },

    # --- Robot (kører over SSH) ---
    {
        "key": "jetson_camera",
        "label": "Camera (Jetson)",
        "section": "Robot",
        "command": (
            f"ssh -tt {JETSON_HOST}"
            f" '{JETSON_SOURCES} && ros2 launch energirobotter_bringup"
            f" camera.launch.py camera_model:=zed2i rotate:=270'"
        ),
    },
    {
        "key": "jetson_servos",
        "label": "Servos (Jetson)",
        "section": "Robot",
        "command": (
            f"ssh -tt {JETSON_HOST}"
            f" '{JETSON_SOURCES} && ros2 launch energirobotter_bringup"
            f" servos.launch.py'"
        ),
    },

    # --- Demo / lokal præsentation ---
    {
        "key": "vuer_camera",
        "label": "Vuer teleop — kun kamera",
        "section": "Demo",
        "needs_ros_source": True,
        "command": (
            "ros2 launch energirobotter_bringup teleoperation_vuer.launch.py"
            " camera_source:=ros stereo_enabled:=false"
            " ik_enabled:=false rviz:=false"
        ),
    },
    {
        "key": "vuer_ik",
        "label": "Vuer teleop — kamera + IK (servoer kræves)",
        "section": "Demo",
        "needs_ros_source": True,
        "command": (
            "ros2 launch energirobotter_bringup teleoperation_vuer.launch.py"
            " camera_source:=ros stereo_enabled:=false"
            " ik_enabled:=true rviz:=false"
        ),
    },
    {
        "key": "power_monitor",
        "label": "Power monitor (live viewer)",
        "section": "Demo",
        "needs_ros_source": True,
        "command": (
            "ros2 run arm_commissioning power_monitor_node --ros-args"
            " -p scenario:=demo -p duration_s:=600 -p live:=true"
        ),
    },
    {
        "key": "animation_idle1",
        "label": "Animation: idle1.csv",
        "section": "Demo",
        "needs_ros_source": True,
        "command": (
            "ros2 launch energirobotter_bringup animation.launch.py"
            " csv_file:=idle1"
        ),
    },
]

CHECKLIST = [
    # ESP32-bokse er bundet til faste USB-porte via /dev/serial/by-path/,
    # så plug-rækkefølgen er ligegyldig — men de SKAL i den rigtige port.
    # Kameraet skal have kørt mindst én gang før bokse plugges i (per
    # workspace-rod README).
    "ESP32-bokse i rette porte: RØD=2.2 (left arm), GUL=2.3 (right arm+head),"
    " HVID=2.1 (hands) — efter kameraet er kørt mindst én gang",
    "Jetson tændt OG den har fået DHCP-adresse (tjek DHCP-log efter 'DHCPACK')",
    "Quest 3 tilsluttet via USB-C med USB-debugging accepteret (kun ved vuer)",
]

# Demo-rækkefølgen for "Start demo"-knappen. Sekvens med små pauser så
# Jetson når at boote services færdig før næste lokale service starter.
DEMO_SEQUENCE = [
    ("dhcp", 1.0),
    ("jetson_camera", 6.0),  # giv kameraet tid til at initialisere
    ("adb_reverse", 1.0),
    ("vuer_camera", 1.0),
]

# ---------------------------------------------------------------------------
# Service-håndtering
# ---------------------------------------------------------------------------

COLOR_RUNNING = "#4caf50"
COLOR_STOPPED = "#9e9e9e"
COLOR_ERROR = "#f44336"


class Service:
    """Wrapper omkring én underliggende subprocess + GUI-status."""

    def __init__(self, spec):
        self.spec = spec
        self.proc = None
        self.last_exit_code = None
        # GUI-elementer sættes af LauncherApp under build_ui
        self.status_label = None
        self.start_btn = None
        self.stop_btn = None

    def is_running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, log_fn):
        if self.is_running():
            log_fn(f"[{self.spec['key']}] kører allerede — ignoreret")
            return
        cmd = self.spec["command"]
        if self.spec.get("needs_ros_source"):
            cmd = f"{LOCAL_ROS_SOURCES} && {cmd}"

        log_fn(f"[{self.spec['key']}] starter")
        # Eksplicit setsid → vi får en pgroup vi kan SIGINT'e samlet
        # uden at ramme launcher-GUI'en selv.
        try:
            self.proc = subprocess.Popen(
                ["bash", "-c", cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            log_fn(f"[{self.spec['key']}] kunne ikke starte: {e}")
            return
        threading.Thread(target=self._pump, args=(log_fn,), daemon=True).start()

    def stop(self, log_fn, hard=False):
        if not self.is_running():
            return
        sig = signal.SIGTERM if hard else signal.SIGINT

        # Hvis servicen kan ikke signaleres direkte (fx root-ejet via
        # pkexec), bruges en eksplicit stop-kommando i stedet.
        stop_cmd = self.spec.get("stop_command")
        if stop_cmd:
            log_fn(f"[{self.spec['key']}] stopper via stop_command: {stop_cmd}")
            try:
                subprocess.Popen(["bash", "-c", stop_cmd])
            except Exception as e:
                log_fn(f"[{self.spec['key']}] stop_command fejl: {e}")
            return

        log_fn(
            f"[{self.spec['key']}] stopper "
            f"({'SIGTERM' if hard else 'SIGINT'} til pgroup {self.proc.pid})"
        )
        try:
            os.killpg(os.getpgid(self.proc.pid), sig)
        except ProcessLookupError:
            pass
        except PermissionError as e:
            # Sker hvis processen kører som root (pkexec) og vi prøver at
            # signalere som almindelig bruger. Logges, men crasher ikke.
            log_fn(
                f"[{self.spec['key']}] kunne ikke signalere ({e}) — "
                f"processen er privileged. Brug evt. 'pkexec pkill ...' manuelt."
            )

    def _pump(self, log_fn):
        try:
            for line in self.proc.stdout:
                # Trim helt blanke linjer for at holde loggen kompakt
                if line.strip():
                    log_fn(f"[{self.spec['key']}] {line.rstrip()}")
        except Exception as e:
            log_fn(f"[{self.spec['key']}] log-pump fejl: {e}")
        rc = self.proc.wait()
        self.last_exit_code = rc
        log_fn(f"[{self.spec['key']}] afsluttet (exit={rc})")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------


class LauncherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Wattson Demo Launcher")
        self.geometry("960x780")
        self.minsize(820, 620)

        self.services = {s["key"]: Service(s) for s in SERVICES}

        self._build_ui()
        # Start status-poll-loop
        self.after(500, self._refresh_status)

    # ------------------------- UI-konstruktion -----------------------------

    def _build_ui(self):
        header = ttk.Label(
            self, text="Wattson Demo Launcher", font=("", 18, "bold")
        )
        header.pack(pady=(10, 6))

        # --- Pre-flight checklist ---
        chk_frame = ttk.LabelFrame(
            self, text="Pre-flight checklist (klik når gjort)"
        )
        chk_frame.pack(fill="x", padx=10, pady=4)
        self.checklist_vars = []
        for item in CHECKLIST:
            v = tk.BooleanVar(value=False)
            self.checklist_vars.append(v)
            ttk.Checkbutton(chk_frame, text=item, variable=v).pack(
                anchor="w", padx=8, pady=2
            )

        # --- Services ---
        sec_frame = ttk.LabelFrame(self, text="Services")
        sec_frame.pack(fill="x", padx=10, pady=4)
        self._build_services(sec_frame)

        # --- Top-level controls ---
        ctrl = ttk.Frame(self)
        ctrl.pack(fill="x", padx=10, pady=6)

        ttk.Button(
            ctrl,
            text="▶ Start demo (DHCP → Camera → adb → Vuer)",
            command=self.start_demo,
        ).pack(side="left")

        ttk.Button(ctrl, text="■ Stop alle", command=self.stop_all).pack(
            side="right", padx=(4, 0)
        )
        ttk.Button(ctrl, text="Ryd log", command=self._clear_log).pack(
            side="right", padx=4
        )

        # --- Log ---
        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.log = scrolledtext.ScrolledText(
            log_frame, height=14, font=("monospace", 9), wrap="word"
        )
        self.log.pack(fill="both", expand=True, padx=4, pady=4)
        self._append_log(
            "Klar. Tjek pre-flight checklist, start så de services du har brug for."
        )

    def _build_services(self, parent):
        # Gruppér efter section og bevar definitions-rækkefølgen
        sections = {}
        for spec in SERVICES:
            sections.setdefault(spec.get("section", ""), []).append(spec)

        for sec_name, specs in sections.items():
            sec_lbl = ttk.Label(parent, text=sec_name, font=("", 11, "bold"))
            sec_lbl.pack(anchor="w", padx=8, pady=(8, 2))
            for spec in specs:
                self._build_service_row(parent, spec)

    def _build_service_row(self, parent, spec):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=8, pady=2)

        svc = self.services[spec["key"]]

        status = tk.Label(row, text="●", fg=COLOR_STOPPED, font=("", 14))
        status.pack(side="left", padx=(0, 6))
        svc.status_label = status

        lbl = ttk.Label(row, text=spec["label"], width=42, anchor="w")
        lbl.pack(side="left")

        start = ttk.Button(
            row, text="Start", width=8,
            command=lambda k=spec["key"]: self.start(k),
        )
        start.pack(side="left", padx=2)
        stop = ttk.Button(
            row, text="Stop", width=8,
            command=lambda k=spec["key"]: self.stop(k),
        )
        stop.pack(side="left", padx=2)
        svc.start_btn = start
        svc.stop_btn = stop

    # ------------------------- log/status helpers --------------------------

    def log_msg(self, line):
        # Thread-safe: schedule append on main thread
        self.after(0, self._append_log, line)

    def _append_log(self, line):
        self.log.insert("end", f"{line}\n")
        self.log.see("end")

    def _clear_log(self):
        self.log.delete("1.0", "end")

    def _refresh_status(self):
        for svc in self.services.values():
            if svc.is_running():
                color = COLOR_RUNNING
            elif svc.last_exit_code is not None and svc.last_exit_code not in (
                0, -2, -15, 130, 143
            ):
                # 0 = clean, -2/-15 = vores SIGINT/SIGTERM, 130/143 = unix conv.
                color = COLOR_ERROR
            else:
                color = COLOR_STOPPED
            if svc.status_label is not None:
                svc.status_label.config(fg=color)
        self.after(500, self._refresh_status)

    # ------------------------- handlers ------------------------------------

    def start(self, key):
        self.services[key].start(self.log_msg)

    def stop(self, key):
        self.services[key].stop(self.log_msg)

    def stop_all(self):
        # Soft stop først (SIGINT), hardstop efter en kort grace-periode
        for svc in self.services.values():
            try:
                svc.stop(self.log_msg, hard=False)
            except Exception as e:
                # Forhindr at en enkelt fejlende service blokerer
                # vinduet i at lukke.
                self.log_msg(f"[{svc.spec['key']}] stop fejl: {e}")

        def hard_kill_remaining():
            time.sleep(3.0)
            for svc in self.services.values():
                if svc.is_running():
                    try:
                        svc.stop(self.log_msg, hard=True)
                    except Exception as e:
                        self.log_msg(
                            f"[{svc.spec['key']}] hard stop fejl: {e}"
                        )

        threading.Thread(target=hard_kill_remaining, daemon=True).start()

    def start_demo(self):
        def run():
            for key, delay in DEMO_SEQUENCE:
                self.start(key)
                time.sleep(delay)
            self.log_msg("[demo] sekvens færdig — åbn http://localhost:8012 i Quest")

        threading.Thread(target=run, daemon=True).start()

    # ------------------------- shutdown ------------------------------------

    def on_close(self):
        self.log_msg("Lukker — stopper alle services…")
        try:
            self.stop_all()
        except Exception as e:
            # Aldrig blokere window-close på en stop-fejl.
            self.log_msg(f"stop_all fejl under shutdown: {e}")
        # Giv subprocesser et øjeblik til at lukke pænt; destroy uanset.
        self.after(1500, self.destroy)


def main(args=None):
    app = LauncherApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
