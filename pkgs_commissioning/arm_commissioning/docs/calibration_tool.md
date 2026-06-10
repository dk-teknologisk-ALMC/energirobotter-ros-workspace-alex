# calibration_tool_node

Interaktivt keyboard-værktøj. Du jogger én servo ad gangen, læser den
fysiske vinkel af på robotten (eller med vinkelmåler), og låser
`angle_software_min`, `angle_software_max` og `default_position`. Værdierne
skrives tilbage til den angivne JSON-config med backup
`.bak.<timestamp>`.

> **Rapport-kapitel**: 6.1 Kalibrering

## Forudsætninger

Se [pakke-README](../README.md). Vigtigst: ingen andre publishere på
`/joint_states`.

## Kør

```bash
ros2 run arm_commissioning calibration_tool_node --ros-args \
  -p config_file:=$HOME/humanoid_ws/src/energirobotter-ros-workspace-alex/energirobotter_bringup/config/servos/servo_arm_left_params.json \
  -p joint_name:=joint_left_shoulder_pitch
```

Brug `ros2 run` (ikke `ros2 launch`) — værktøjet skal have en ægte TTY på
stdin for at kunne læse tastetryk.

## Tastatur

| Tast | Handling |
|------|----------|
| `a` / `d` | step −1° / +1° (fysisk) |
| `A` / `D` | step −5° / +5° |
| `z` / `c` | step ±0.1° (finjustering) |
| `h` | hjem (original `default_position`) |
| SPACE | hold (genudsend nuværende) |
| `[` | marker nuværende position som `angle_software_min` |
| `]` | marker nuværende som `angle_software_max` |
| `0` | marker nuværende som `default_position` |
| `p` | print tilstand |
| `s` | GEM til JSON (laver `.bak.<timestamp>`) |
| `x` / `q` | afslut |
| `?` | vis hjælp |

## Sikkerhed

- Tool clipper aldrig udenfor `[angle_min, angle_max]` (hardware-grænser
  fra JSON), uanset hvor langt du jogger.
- **Start altid med `h`** for at gå til en kendt position før du jogger
  mod et nyt endepunkt.
- Hvis servoen ikke flytter sig som forventet (knirker, brummer): tryk
  `h` straks eller Ctrl-C.

## Anbefalet arbejdsgang pr. servo

1. `h` — gå til original default
2. Jog forsigtigt nedad (`a`/`A`) mod den ene fysiske endeposition
3. Når armen rører endestop / kabel strammes / mekanisk modstand mærkes:
   bak 1–2° (`d`/`d`)
4. Tryk `[` — det er din nye `angle_software_min`
5. `h` igen
6. Jog opad (`d`/`D`) mod den anden endeposition, samme procedure → `]`
7. Find midten / komfortabel hvileposition → `0`
8. `p` for at se alle 3 værdier
9. `s` for at gemme
10. Notér i målejournal: servo-ID, nye værdier, dato, observatør, evt.
    fysisk forklaring

## Efter `s` — genbyg

JSON er opdateret i `src/`. Du SKAL genbygge for at få det med i
`install/`:

```bash
cd ~/humanoid_ws
colcon build --packages-select energirobotter_bringup wattson_description elrik_description
source install/setup.bash
```

…og genstart `servos.launch.py` for at indlæse de nye værdier.

## Kendt begrænsning

Værktøjet har ingen live-feedback fra servoen — du må læse den fysiske
vinkel manuelt. Hvis du jogger ud over de eksisterende
`angle_software_min/max`, vil `wattson_servo_manager` clippe kommandoen
til den gamle grænse. For at finde **bredere** grænser end de gamle, må
du midlertidigt udvide dem i JSON først → byg → relaunch → kalibrér.
