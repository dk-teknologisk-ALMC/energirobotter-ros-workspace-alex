# repeatability_node

Måler en servos **positions-spredning** ved at sende den N gange mellem
to poser. Karakteriserer den samlede effekt af backlash, mekanisk slør
og servo-controllerens positions-noise. Output er rapport-klar CSV + PNG.

> **Rapport-kapitel**: 6.3 Funktionstest / repeterbarhed

## Forudsætninger

Se [pakke-README](../README.md). Derudover:

- Servoen skal have `feedback_enabled: true`.
- Pose A og pose B skal være **mekanisk sikre** — armen vil køre frem og
  tilbage `cycles` × 2 gange.

## Kør

```bash
ros2 run arm_commissioning repeatability_node --ros-args \
    -p joint_name:=joint_left_shoulder_pitch \
    -p pose_a_deg:=0.0 \
    -p pose_b_deg:=20.0 \
    -p cycles:=10 \
    -p hold_s:=1.5
```

## Parametre

| Parameter | Default | Beskrivelse |
|-----------|---------|-------------|
| `joint_name` | (kræves) | Joint-navn fra `/joint_states` |
| `pose_a_deg` | 0.0 | Pose A (logisk vinkel, delta fra default) |
| `pose_b_deg` | 20.0 | Pose B |
| `cycles` | 10 | Antal frem-og-tilbage-cyklusser |
| `hold_s` | 1.5 | Hold-tid pr. pose (skal være > settling time) |
| `publish_rate` | 50.0 | Hz hvor kommandoen genudsendes |
| `output_dir` | `~/humanoid_ws/test_results` | Rod-mappe |

> **Tip**: Sæt `hold_s` mindst lig med `settling_time_s` målt af
> `step_response_node` for samme servo + samme step-størrelse. Ellers
> får du for-tidlige målinger.

## Output

`<output_dir>/<YYYY-MM-DD>/<joint>/<stamp>_repeat.csv` med slut-position
pr. cyklus pr. pose.

`<...>_repeat.png` med:
- Scatter-plot af målinger pr. pose
- Std + min/max vist som horisontale linjer
- Indlejret tekstboks med samlede statistikker

## Beregnede metrics

| Metric | Beskrivelse |
|--------|-------------|
| `n_cycles` | Antal kørte cyklusser |
| `pose_a_mean_deg` / `pose_b_mean_deg` | Faktisk gennemsnits-position |
| `pose_a_std_deg` / `pose_b_std_deg` | Standardafvigelse (spredning) |
| `pose_a_max_dev_deg` / `pose_b_max_dev_deg` | Maks. afvigelse fra gennemsnit |

## Tolkning til rapport

- **Std < 0.1°**: superb repeterbarhed, ST3215 er ved sin grænse
- **Std 0.1–0.5°**: typisk for et 3D-printet led med moderat backlash
- **Std > 1°**: noget galt mekanisk — fx løs gearing, slap kobling
- **Stor forskel mellem pose A og pose B**: tyngdekraft eller fjeder
  trækker konsekvent mod den ene side (positions-bias)

## Forslag til rapport-test

Kør pose-pair der dækker servoens **arbejdsområde**, så I dokumenterer
repeterbarhed over hele bevægelsesintervallet:

```bash
# Lille bevægelse
ros2 run arm_commissioning repeatability_node --ros-args \
    -p joint_name:=joint_left_shoulder_pitch \
    -p pose_a_deg:=0 -p pose_b_deg:=5 -p cycles:=10

# Mellem
ros2 run arm_commissioning repeatability_node --ros-args \
    -p joint_name:=joint_left_shoulder_pitch \
    -p pose_a_deg:=0 -p pose_b_deg:=20 -p cycles:=10

# Stor
ros2 run arm_commissioning repeatability_node --ros-args \
    -p joint_name:=joint_left_shoulder_pitch \
    -p pose_a_deg:=-30 -p pose_b_deg:=30 -p cycles:=10
```
