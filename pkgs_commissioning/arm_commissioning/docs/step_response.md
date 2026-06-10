# step_response_node

Karakteriserer én ST3215-servos respons på et kommanderet step. Måler de
klassiske kontrol-teoretiske størrelser (rise time, overshoot, settling
time, steady-state error) og skriver dem som **CSV + PNG** der kan stå
alene som rapport-figurer.

> **Rapport-kapitel**: 6.2 PID-tuning / servo-karakterisering

## Forudsætninger

Se [pakke-README](../README.md). Derudover:

- Servoen skal have `feedback_enabled: true` i sin JSON-config — ellers
  bliver feedback ikke læst og noden får nul samples.
- Det er en god idé at have servoen **lukket inde i en pose hvor den
  trygt kan flytte sig `step_size_deg`** uden at ramme noget.

## Kør

```bash
ros2 run arm_commissioning step_response_node --ros-args \
    -p joint_name:=joint_left_shoulder_pitch \
    -p step_size_deg:=10.0 \
    -p duration_s:=3.0
```

## Parametre

| Parameter | Default | Beskrivelse |
|-----------|---------|-------------|
| `joint_name` | (kræves) | Joint-navn fra `/joint_states` |
| `step_size_deg` | 10.0 | Step-størrelse (logisk vinkel, dvs. delta fra `default_position`) |
| `baseline_s` | 0.5 | Hold-tid på 0° før step udsendes |
| `duration_s` | 3.0 | Samlet kørselstid |
| `publish_rate` | 50.0 | Hz hvor kommandoen genudsendes |
| `settling_tol_pct` | 10.0 | Tolerance for settling time (% af step) |
| `output_dir` | `~/humanoid_ws/test_results` | Rod-mappe |

> **Tip**: ST3215 har en intern PID med deadband ~0.3-0.5°, så
> `settling_tol_pct=2` (klassisk lærebog) er for stram for små steps.
> Default 10% giver realistiske resultater.

## Output

`<output_dir>/<YYYY-MM-DD>/<joint>/<stamp>_step.csv` med kolonner:

```
t_s, cmd_deg, actual_deg
```

`<...>_step.png` med:
- Kommanderet vs. faktisk vinkel (normaliseret til delta-fra-baseline)
- Step-tidspunkt markeret
- Indlejret tekstboks med beregnede metrics

## Beregnede metrics

| Metric | Definition | Bruges til |
|--------|------------|------------|
| `rise_time_s` | Tid fra 10% til 90% af step-amplituden | Hvor "skarp" responsen er |
| `overshoot_pct` | (peak − target) / step × 100 | Om PID'en er for aggressiv |
| `settling_time_s` | Tid før \|fejl\| ≤ tolerance og forbliver der | Hvor lang tid før systemet er "i mål" |
| `steady_state_error_deg` | Slutfejl efter indsving | Statisk fejl (P-gain for lav?) |
| `baseline_phys_deg` | Faktisk start-vinkel før step | Kontekst |
| `target_delta_deg` | Kommanderet step | Kontekst |

## Tolkning til rapport

- **Lille rise time + intet overshoot + lille slutfejl** = god tuning
- **Stort overshoot + lang settling** = for høj P, for lav D
- **Stor slutfejl uden overshoot** = for lav P (men ST3215's interne PID
  kan ikke ændres herfra — så det er en hardware-grænse)
- **Manglende samples** = `feedback_enabled` er false eller
  servo_manager publicerer ikke `/joint_states_feedback`

## Foreslået test-batch til rapport

Kør 3 steps pr. servo (lille / mellem / stor) for at vise at responsen
skalerer fornuftigt:

```bash
for STEP in 5 10 20; do
  ros2 run arm_commissioning step_response_node --ros-args \
    -p joint_name:=joint_left_shoulder_pitch \
    -p step_size_deg:=$STEP \
    -p duration_s:=3.0
  sleep 2
done
```
