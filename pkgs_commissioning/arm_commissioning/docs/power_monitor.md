# power_monitor_node

Live-viewer + logger for robotens **strømforbrug** (per-servo + total).
Bygget til at producere strømbudget-tabeller og før/efter-grafer til
rapporten, samt at fungere som live-demonstrationsværktøj.

> **Rapport-kapitel**: Strømbudget

## Hvad måler det?

ST3215-servoerne har indbygget shunt og rapporterer på bussen:

| Størrelse | Register | Opløsning |
|-----------|----------|-----------|
| Spænding | `PRESENT_VOLTAGE` (62) | 0.1 V/unit |
| Strøm | `PRESENT_CURRENT_L/H` (69–70) | 6.5 mA/unit, bit 15 = sign |

Servo-manager-noden gør disse værdier tilgængelige på topicen
`/servo_power` (se [Topic-format](#topic-format)). Dette værktøj
abonnerer, beregner `P = V × I` pr. servo + total, og producerer både
live-visning og CSV/PNG-output pr. scenarie.

## ⚠ Vigtig caveat (skriv eksplicit i rapporten)

Målingerne dækker **kun servo-bussen**. De inkluderer IKKE:

- Jetson Orin Nano (~10–15 W under teleop)
- ZED-kameraet (~2–3 W ekstra)
- ESP32 + Wi-Fi
- 12V → 5V step-down konverteringstab

For et **fuldt system-strømbudget** skal noden suppleres med en ekstern
USB-strømmåler ved hovedforsyningen (~150 kr på Amazon). Beskriv det vi
har som **"servo bus power"** i rapport-figurerne — det er fagligt
korrekt.

## Præcision

ST3215's strøm-måling har ~6.5 mA opløsning og spænding ~0.1 V. Det er
**ikke lab-instrument-præcision**, men mere end nok til at vise idle vs.
aktiv (typisk 5×–10× forskel) og til at sammenligne iterationer.

## Forudsætninger

Se [pakke-README](../README.md). Derudover:

- Servoerne skal have `feedback_enabled: true` i deres JSON-config
  (alle servoer der ønskes med i målingen)
- Live-viewer (`live:=true`) kræver X11 — kør den på laptoppen, ikke
  over SSH til Jetson
- Hvis du arbejder via SSH (fx på Jetson), brug `live:=false` og hent
  PNG'en bagefter

## Kør

### Live demo (med viewer)

```bash
ros2 run arm_commissioning power_monitor_node --ros-args \
    -p scenario:=idle \
    -p duration_s:=30.0 \
    -p live:=true
```

Et matplotlib-vindue åbner med:
- Øverst: total W over de seneste `live_window_s` sekunder (default 20s)
- Nederst: per-servo bar chart, live-opdateret

Vinduet kan stå åbent under en hel demo — det "ruller" automatisk.

### Headless (kun CSV/PNG)

```bash
ros2 run arm_commissioning power_monitor_node --ros-args \
    -p scenario:=animation_idle1 \
    -p duration_s:=60.0 \
    -p live:=false
```

### Manuel afslutning

`Ctrl-C` skriver CSV/PNG ud med hvad der er nået at samle — du behøver
ikke vente på `duration_s` udløb.

## Parametre

| Parameter | Default | Beskrivelse |
|-----------|---------|-------------|
| `scenario` | `default` | Mappe-navn for outputtet — vælg sigende navne (`idle`, `animation_wave`, `teleop`) |
| `duration_s` | 30.0 | Hvornår noden auto-afslutter |
| `live` | `true` | Åbn matplotlib live-viewer |
| `live_window_s` | 20.0 | Bredde af rullende vindue i viewer |
| `output_dir` | `~/humanoid_ws/test_results` | Rod-mappe |

## Output

`<output_dir>/<YYYY-MM-DD>/<scenario>/<stamp>_power.csv` med kolonner:

```
t_s, V_<servo1>, V_<servo2>..., A_<servo1>..., W_<servo1>..., total_W
```

`<...>_power.png` med:
- Øverst: total W over hele kørslen + gennemsnitslinje + statistik-boks
- Nederst: top 12 strømslugere som vandret bar chart

I terminalen printes en sammenfatning:

```
=== Power summary (idle) ===
  varighed         = 30.04 s (598 samples)
  gennemsnitlig W  =  6.81
  peak W           = 10.42
  min W            =  5.83
  std W            =  0.71
  top 5 (avg W pr. servo):
      1.42  joint_left_shoulder_pitch
      1.31  joint_left_shoulder_roll
      ...
```

## Foreslåede test-scenarier til rapport

For at få en meningsfuld strømbudget-tabel, kør samme `duration_s` for
hvert scenarie og sammenlign:

| Scenarie | Hvad du gør | Hvad det viser |
|----------|-------------|----------------|
| `idle` | Robotten holder default pose, ingen kommandoer sendes | Statisk hvilestrøm (PID kompenserer mod tyngdekraft) |
| `holding_extended` | Arm strakt ud i tung pose, hold | Max statisk last |
| `animation_idle1` | Kør `idle1.csv` animation | Typisk "alive" forbrug |
| `animation_wave` | Kør en aktiv animation | Højere dynamisk forbrug |
| `step_test` | Kør samtidigt med `step_response_node` | Transient peak under hurtige bevægelser |
| `teleop_calm` | Quest 3 teleop, små bevægelser | Realistic teleop-budget |
| `teleop_active` | Quest 3 teleop, store bevægelser | Worst-case teleop |

### Eksempel — sammenlign idle vs. aktiv

```bash
# Terminal 1: servo-stack kører
ros2 launch energirobotter_bringup servos.launch.py

# Terminal 2: idle baseline (30 s)
ros2 run arm_commissioning power_monitor_node --ros-args \
    -p scenario:=idle -p duration_s:=30.0 -p live:=false

# Terminal 3 (efter idle er færdig): start en animation
ros2 launch energirobotter_bringup animation.launch.py csv_file:=idle1

# Terminal 2: kør samme måling under animationen
ros2 run arm_commissioning power_monitor_node --ros-args \
    -p scenario:=animation_idle1 -p duration_s:=30.0 -p live:=false
```

Bagefter har du to PNG'er og to CSV'er du kan stille op side om side i
rapporten.

## Topic-format

`/servo_power` er en `sensor_msgs/msg/JointState` hvor felterne
genbruges som:

| Felt | Indhold | Enhed |
|------|---------|-------|
| `name[i]` | Servo-navn | — |
| `position[i]` | Spænding | V |
| `velocity[i]` | Strøm (signed) | A |
| `effort[i]` | Effekt | W |

Det er ikke den "rene" semantik for JointState, men det undgår at vi
skal lave en custom msg, og giver et frit per-element name-mapping.

## Fejlfinding

- **"Ingen /servo_power samples modtaget"** — tjek
  `ros2 topic hz /servo_power`. Skulle være ~10 Hz (= control_frequency
  i servo_manager).
- **Alle W er nul** — `feedback_enabled: false` i servo-config, eller
  servoerne svarer ikke (kabel/USB-port).
- **Negative W på enkelte servoer** — er fysisk korrekt under
  regenerativ last (servoen bremser en faldende arm). Hvis ALT er
  negativt, er sign-håndteringen muligvis omvendt for jeres
  firmware-version — sig til så fikser vi det i `set_feedback_current`.
- **Live-viewer åbner ikke** — tjek at du er på laptoppen (ikke SSH), og
  at `python3-tk` er installeret (`sudo apt install python3-tk`).
