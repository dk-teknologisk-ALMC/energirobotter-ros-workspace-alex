# launcher_gui

Tkinter-baseret én-vindue control panel for at starte robotten til
demo eller almindeligt arbejde uden at skulle åbne 5-6 terminaler.

> **Formål**: én klik = robot kører. Tænkt til eksamensfremvisning og
> daglig brug på laptoppen.

## Hvad det gør

- **Pre-flight checklist** for de skridt der ikke kan automatiseres
  (USB-rækkefølge, ESP32 Serial Forwarding, Quest USB-debugging).
- **Per-service Start/Stop** med live-statusprik (kører / stoppet /
  fejl).
- **Samlet log-rude** der viser stdout/stderr fra alle services — ingen
  jonglering med terminaler.
- **"Start demo"-knap** der kører en sekvens (DHCP → Camera → adb →
  Vuer) med små pauser så Jetson når at boote.
- **"Stop alle"-knap** med graciøs SIGINT og hard SIGTERM efter 3 sek.

## Hvad det IKKE gør

- Kan ikke automatisere ESP32 Serial Forwarding-dansen
  (kræver Wi-Fi-skift + browser-klik på 192.168.4.1).
- Kan ikke automatisere USB-plug-rækkefølgen.
- Er ikke en ROS-node — det shell'er bare ud til `ros2`/`ssh`/`pkexec`.

## Forudsætninger (engangs-opsætning)

```bash
# Tkinter (Ubuntu-pakke)
sudo apt install python3-tk

# Polkit/pkexec er allerede installeret på standard Ubuntu — det bruges
# til at få DHCP (dnsmasq) op uden at lægge sudo-password ind i GUI'en
```

## Kør

```bash
ros2 run arm_commissioning launcher_gui
```

(Husk `source install/setup.bash` først hvis det ikke er gjort i
shellet.)

Vinduet åbner. Du gør så følgende manuelt **én gang**:

1. Tjek af pre-flight checklist
2. Tilslut USB-kabler i den dokumenterede rækkefølge
3. Tænd Jetson
4. Lav ESP32 Serial Forwarding-dans (Wi-Fi → 192.168.4.1 → Start → Stop)
5. Tilslut Quest 3 hvis vuer skal bruges

Derefter kan du enten:

- Klikke **Start demo** og se det hele booter automatisk i sekvens, eller
- Klikke **Start** på de individuelle services du har brug for.

## Services

| Sektion | Service | Hvad det gør |
|---------|---------|--------------|
| Network | DHCP server | `pkexec dnsmasq …` (åbner grafisk password-prompt) |
| Network | adb reverse | Forwarder Quest's `localhost:8012` til laptop |
| Robot | Camera (Jetson) | SSH til Jetson, kører `camera.launch.py` |
| Robot | Servos (Jetson) | SSH til Jetson, kører `servos.launch.py` |
| Demo | Vuer teleop — kun kamera | Vuer med `ik_enabled:=false` |
| Demo | Vuer teleop — kamera + IK | Vuer med `ik_enabled:=true` (kræver servoer) |
| Demo | Power monitor | `power_monitor_node` med live-viewer |
| Demo | Animation: idle1.csv | Afspil `idle1` animation |

## Live-status

Status-prikken til venstre for hver service har tre tilstande:

- **● grøn** — proces kører
- **● grå** — stoppet (eller stoppet rent af brugeren)
- **● rød** — proces afsluttede med en uventet fejlkode

## Stop og oprydning

- **Stop**-knappen sender SIGINT (~`Ctrl-C`) til hele proces-gruppen
- **Stop alle** sender SIGINT til alt, og efter 3 sek. SIGTERM hvis
  noget hænger
- **Vinduet lukket (X)** kalder Stop alle inden GUI'en lukker

> **Bemærk om SSH**: SIGINT sendes til den lokale ssh-klient. Med `-tt`
> i kommandoen får remote-processen også SIGINT via TTY'en. Hvis Jetson
> stadig holder noget åbent (sjældent), så `ssh elrik@... pkill -f
> ros2` rydder det op manuelt.

## Tilpasning

Alle services + demo-sekvens er defineret som lister øverst i
[launcher_gui_node.py](../arm_commissioning/launcher_gui_node.py):

```python
SERVICES = [
    {"key": "...", "label": "...", "command": "...", ...},
]

DEMO_SEQUENCE = [("dhcp", 1.0), ("jetson_camera", 6.0), ...]
```

Tilføj/ret efter behov og rebuild:

```bash
colcon build --packages-select arm_commissioning --symlink-install
```

(Med `--symlink-install` kan du bare ændre Python-filen og genstarte
GUI'en uden at bygge.)

## Fejlfinding

| Symptom | Sandsynlig årsag | Fix |
|---------|------------------|-----|
| `_tkinter.TclError: no display name and no $DISPLAY` | Kører over SSH uden X | Kør på laptoppen direkte |
| `pkexec` fejler / dnsmasq starter ikke | Polkit accepterede ikke password | Prøv igen, eller kør `sudo dnsmasq …` manuelt i terminal |
| SSH til Jetson hænger med 'Connection refused' | Jetson ikke booted endnu / DHCP gav ikke adresse | Vent på `DHCPACK` i log før du starter Jetson-services |
| Vuer viser hvid/sort skærm | Camera-topic ikke aktiv | Tjek `ros2 topic hz /zed/zed_node/left/image_rect_color/compressed/rotated/compressed` (skal være ~60 Hz) |
| Quest "site can't be reached" | adb reverse ikke aktiv | Tjek `adb devices` viser headset; restart adb_reverse-service |
| Status-prik blev rød straks ved start | Kommandoen fejlede | Læs log-ruden — den indeholder den fulde fejlmeddelelse |
