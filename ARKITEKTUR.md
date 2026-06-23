# Arkitektur-overblik (til mig selv)

Forklaring af hvordan robotten hænger sammen, hvorfor vi bruger ROS 2,
og hvad de fagord betyder som jeg selv bliver i tvivl om. Skrevet til
mig selv som forberedelse til eksamen.

---

## 1. Hardware-overblik

Robotten består af fire fysiske dele der snakker sammen:

**Jetson Orin Nano (på robotten)**
Linux-computer med Ubuntu 22.04 + ROS 2 Humble. Kører alt det realtid-
agtige: servo-driverne, kinematik, animation playback. Forbindes til
laptoppen over Ethernet/LAN. Hostname: `elrik`, IP fast på
`192.168.1.105`.

**Min laptop (udvikling + GUI)**
Samme Ubuntu + ROS 2 Humble. Bruges til at skrive kode, køre Vuer-web-
GUI'en (teleop), `launcher_gui`, Foxglove til debugging og bare som
bridge til Quest 3. Da begge maskiner har `ROS_DOMAIN_ID=0` og samme
DDS-config, ser de hinandens topics automatisk.

**ESP32 bus-bridge boards (3 stk)**
Små mikrocontrollere der oversætter USB-serial fra Jetson til
TTL/half-duplex på servo-bussen. Hver ESP32 hænger på sin egen faste
USB-port (`/dev/serial/by-path/...-port0/1/2`):
- Arme (12 ST3215-servoer fordelt på venstre/højre)
- Hænder (10 SC09-servoer, 5 fingre pr. hånd)
- Hoved (3 ST3215 til pan/tilt og evt. nakke)

**Servoer**
- **ST3215** — 12-bit (4096 raw ticks), 360° range. Bruges i armene
  og hovedet. Har intern strøm/spændings-feedback.
- **SC09** — 10-bit (1024 raw ticks), ca. 300° range. Bruges i
  fingrene. Billigere, ingen feedback ud over position.

**ZED 2 kamera + Quest 3 headset**
ZED leverer stereo-video og dybde fra robottens "hoved". Quest 3 bruges
til teleoperation: brugerens hånd-tracking sendes ind som mål for IK.

---

## 2. Hvorfor ROS 2?

Når man har én CPU og én proces der gør det hele, ender man hurtigt
med kode der gør alt på én gang og er svær at teste. ROS 2 løser tre
konkrete problemer for os:

**Decoupling.**
Servo-driveren behøver ikke vide noget om kinematik. Kinematik-noden
behøver ikke vide noget om Quest 3. De snakker sammen via veldefinerede
*topics* med standardiserede beskeder (`sensor_msgs/JointState`,
`geometry_msgs/PoseStamped` osv.). Jeg kan udskifte den ene side uden
at røre den anden.

**Sprog-agnostisk.**
Vores stak blander Python (de fleste noder, hurtige iterationer) og
C++ (KDL kinematik, ZED-driveren). De snakker sammen helt
problemløst fordi alt går over DDS med protobuf-lignende beskeder.

**Distribueret af natur.**
Jeg kan starte `launcher_gui` på laptoppen og samtidig køre
`wattson_servo_manager` på Jetson, og en topic publiseret det ene sted
kan subscribes det andet sted uden netværkskode. Det er bare ét
`ROS_DOMAIN_ID` der binder dem sammen.

**Værktøjer "for free".**
`ros2 topic echo`, `ros2 topic hz`, `rqt_graph`, `foxglove`,
`ros2 bag record` — alt sammen virker uden at jeg behøver bygge det
selv.

---

## 3. ROS 2 i praksis — koncepter

**Node.**
En proces der gør én ting. Eksempel: `wattson_servo_manager_node`
læser `/joint_states` og skriver til servo-bussen. Noder kan startes
enkeltvis (`ros2 run <pakke> <node>`) eller via en launch-fil.

**Topic.**
Navngivet besked-kanal med pub/sub-semantik. Publiseres af én eller
flere noder, subscribes af én eller flere. Eksempel: `/joint_states`,
`/servo_power`, `/cmd_vel`. Asynkron — sender ikke fejl hvis ingen
lytter.

**Service.**
Synkron request/response (mere som RPC). Vi bruger det sparsomt;
de fleste ting er hellere topics.

**Pakke.**
En mappe med `package.xml` + enten `setup.py` (Python) eller
`CMakeLists.txt` (C++). En pakke kan indeholde 1..N noder, launch-
filer, configs, beskeder. Vores pakker ligger under `src/...` og
bygges med `colcon build`.

**Launch-fil.**
Python- eller XML-fil der starter mange noder på én gang med
parametre. Eksempel: `energirobotter_bringup/launch/robot/servos.launch.py`
starter både arm-, hånd- og hoved-serven med parametre fra YAML.

**Parameters.**
Pr. node konfiguration der kan sættes ved start (`-p name:=value`)
eller fra YAML. Bruges fx til at sætte `joint_name` på
`command_test_node`.

**TF (transform tree).**
ROS 2's standard for at holde styr på koordinatsystemer over tid
(baselink → shoulder → elbow → wrist). RViz bruger TF til at vise
URDF'en korrekt.

---

## 4. ROS-pakke vs Docker — vigtigt at holde fra hinanden

Det er noget jeg selv blev forvirret over:

- En **ROS 2-pakke** er bare en mappe med `package.xml` som colcon
  bygger og installerer ind i `install/`. Den deler Python-tolk og
  Linux-bibliotek med resten af systemet.
- En **Docker-container** er et indkapslet OS-image. Vi bruger ikke
  Docker nogen steder i dette projekt. Alt kører direkte mod den
  installerede ROS 2 Humble.

Når jeg ser ordet "container" i vores stak handler det altid om Python-
strukturer eller GUI-widgets — aldrig Docker.

---

## 5. Hvordan en bevægelse rejser fra input til servo

Det er stort set samme rejse uanset om input er Quest 3, en CSV-
animation eller `command_test_node`:

```
[ input-kilde ]
      │   sender enten kartesiske mål (Quest) eller
      │   joint-vinkler (animation / test)
      ▼
[ kinematik-node ]  (kun ved kartesisk input)
      │   sensor_msgs/JointState på /joint_states
      ▼
[ wattson_servo_manager_node ]
      │   konverterer rad → raw ticks vha. servo_*_params.json
      │   skriver via pyserial til /dev/serial/by-path/...
      ▼
[ ESP32 bus-bridge ]
      │   half-duplex TTL til servo-bussen
      ▼
[ ST3215 / SC09 servo ]
```

To selvstændige stier kører parallelt:

- **Arm-siden:** `/joint_states` → arm-segmentet i
  `wattson_servo_manager` → arm-bus.
- **Hånd-siden:** `/joint_states_hands` (separat topic!) → hånd-
  segmentet → hånd-bus.

Det er derfor finger-test bruger `-p topic_name:=/joint_states_hands`.

---

## 6. Vigtige design-valg vi har gjort

**Faste USB-porte via `by-path`.**
`/dev/ttyUSB0/1/2` skifter rækkefølge efter genstart. Det giver
silent fejl hvor arme pludselig får hænder-firmware. Vi bruger
`/dev/serial/by-path/...-port<N>` der binder navnet til den fysiske
USB-controller-port. Tvinger også opsætteren til at sætte stikkene
de samme steder hver gang.

**To kopier af servo-configs.**
Der ligger `servo_*_params.json` både i
`energirobotter_bringup/config/servos/` og i
`wattson_description/servo_configs/`. **Det er kun
`wattson_description`-versionen launch-filen læser.** Den anden er
historisk. Husk det inden du redigerer.

**WIP test-tools.**
`step_response`, `repeatability` og `power_monitor` er markeret WIP.
De kan startes, men de skal verificeres mod en kendt baseline før
tallene må citeres i en rapport.

**Ingen Docker, ingen container-orchestration.**
Hvis noget skal genstartes, gøres det med `Ctrl+C` og `ros2 run` /
`ros2 launch`. `launcher_gui` automatiserer det fra én skærm.

---

## 7. Ordliste / fagord

**ROS 2** — Robot Operating System v2. Middleware (ikke et OS) for
robot-software. Vi bruger distributionen *Humble Hawksbill*.

**DDS** — Data Distribution Service. Transportlaget under ROS 2.
Default i ROS 2 Humble er Fast DDS. Det er DDS der finder andre noder
på netværket via `ROS_DOMAIN_ID`.

**`ROS_DOMAIN_ID`** — Et tal (0–101) der adskiller ROS-netværk på
samme LAN. Begge vores maskiner kører `0`.

**Topic** — Pub/sub-besked-kanal.

**Node** — En proces der bruger ROS API'et.

**Launch-fil** — Python-script der starter mange noder + parametre.

**colcon** — Build-værktøjet til ROS 2-workspaces. Erstatter `catkin`
fra ROS 1.

**rosdep** — Værktøj der installerer system-afhængigheder erklæret i
`package.xml` (`rosdep install --from-paths src`).

**URDF** — Unified Robot Description Format. XML-beskrivelse af
robottens led, geometri, fysik, masser. RViz læser URDF for at tegne
robotten. Vores ligger i `wattson_description/`.

**Joint / led** — Et roterende eller skydende mellemled. Hver servo
styrer ét joint.

**`JointState`** — `sensor_msgs/JointState`. Liste af `name`,
`position`, `velocity`, `effort`. Vores standard-topic for "her er
hvor jointsne skal hen".

**IK** — Inverse Kinematics. "Givet at jeg vil have håndleddet
*her*, hvilke vinkler skal hver arm-servo så have?". Vi bruger
KDL (`elrik_kdl_kinematics`).

**FK** — Forward Kinematics. Modsat: "givet disse vinkler, hvor er
håndleddet?".

**PWM** — Pulse Width Modulation. Hvordan servoen internt styrer
motor-effekt. Bruges ikke direkte af os — vi sender position.

**PID** — Proportional/Integral/Derivative controller. ST3215 har
sin egen indbyggede PID; vi sender bare ønsket position og servoen
finder dertil.

**`/dev/serial/by-path/`** — Stabilt USB-serial-symlink baseret på
hvilket USB-bus/-port enheden sidder i. Modsat `/dev/ttyUSB0` der
gentildeles ved hver boot.

**ESP32** — Mikrocontroller med USB + GPIO. I vores tilfælde bruges
den som "translator" fra USB-serial til half-duplex TTL servo-bus.

**ST3215 / SC09** — Vores to servo-typer. ST3215 = 12-bit, høj
kvalitet, brugt i arme/hoved. SC09 = 10-bit, billig, brugt i fingre.

**Vuer** — Web-baseret 3D-frontend vi bruger til Quest 3 teleop.
Hosted lokalt på laptoppen, Quest tilgår den over `adb reverse`.

**Quest 3** — Meta VR-headset. Vi bruger kun hånd-tracking herfra
som IK-target. Forbindes wired via USB-C.

**ZED 2** — Stereolabs stereokamera. Leverer farve + dybde via
`zed_ros2_wrapper`.

**`colcon build --packages-select <pkg>`** — Bygger kun én pakke i
stedet for hele workspace. Vores standard når man har redigeret ét
sted.

**Bringup** — ROS-jargon for "start hele systemet op for ægte hardware".
Vores `energirobotter_bringup`-pakke samler launch-filer til det.
