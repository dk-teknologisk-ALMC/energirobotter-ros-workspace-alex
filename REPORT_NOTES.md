# Rapportnotater — Humanoid Build

> **Formål:** Arbejdsdokument der løbende samler tekniske ændringer, begrundelser og
> testresultater fra arbejdet på `alex/min-opgave`, struktureret efter
> rapportens kapitler. Notaterne er **arbejdsmateriale** — udvælg og omformuler
> det relevante til `Chapters/Chapter<N>.tex` i rapport-repoet.
>
> Format pr. entry:
> - **Hvad:** kort teknisk beskrivelse af ændringen
> - **Hvorfor:** rationale + alternativer der blev forkastet
> - **Implementering:** filer, commit-hash, kort kodeeksempel hvor relevant
> - **Test:** procedure, observerede resultater, evt. CSV/figur-stier
> - **Til rapport:** tekstforslag eller pointer der kan paraphraseres

---

## Kap. 5 — Elektrisk integration og wiring

### 5.1 USB-portbinding via `/dev/serial/by-path/` (2026-05-27)

**Hvad:**
Tre ESP32-bokse (left arm, right arm + head, hænder) tilsluttes Jetson Orin
Nano via USB. Tidligere blev de adresseret som `/dev/ttyUSB0`, `/dev/ttyUSB1`,
`/dev/ttyUSB2` i `wattson_servo_manager_node.py`. Nu adresseres de via
`/dev/serial/by-path/platform-3610000.usb-usb-0:2.<N>:1.0-port0`, hvor `N`
peger på den fysiske USB-port på Jetson'en.

**Hvorfor:**
- Linux's `ttyUSB`-nummerering tildeles **i tilslutningsrækkefølge** ved boot
  eller hot-plug. Hvis bokse plugges ind i en anden rækkefølge end forrige
  gang, byttes rollerne om — venstre arm bliver styret af kommandoer beregnet
  til højre arm, med uforudsigelige bevægelser til følge.
- Tidligere workaround var en manuel procedure ("plug rød → gul → hvid i den
  rækkefølge efter at kameraet har kørt mindst én gang"), som er fejludsat og
  besværlig at demonstrere.
- `/dev/serial/by-path/` er en kerne-genereret stabil sti baseret på USB-bus
  topologien. Når et kabel sættes i samme fysiske port, får man altid samme
  sti. Tildelingen bliver dermed afhængig af *hvilken port*, ikke *hvornår*.
- Alternativer overvejet og forkastet:
  - **udev-regler med `idVendor`/`idProduct`:** alle tre ESP32-bokse bruger
    samme CP210x USB-serial chip → samme VID/PID, så de kan ikke skelnes på
    den måde.
  - **Serienummer-baseret udev-regel:** ESP32-firmware skriver ikke unikke
    serienumre på chippen, og bokse er ombyttelige hardware-mæssigt.
  - **`/dev/serial/by-id/`:** indeholder kun VID/PID/serial — samme problem
    som ovenfor.
  - **`/dev/serial/by-path/`:** baseret på fysisk topologi, virker uden
    udev-konfiguration eller firmware-ændringer. **Valgt.**

**Implementering:**
- Fil: `pkgs_control/servo_control/servo_control/wattson_servo_manager_node.py`
- Commit: `9a1c988` på `alex/min-opgave`
- Tre `port_path=`-strenge ændret:
  - Left arm → `…:2.2:1.0-port0` (RØD boks)
  - Right arm + head → `…:2.3:1.0-port0` (GUL boks)
  - Hænder → `…:2.1:1.0-port0` (HVID boks)
- Tilsvarende patch lavet direkte på Jetson'en med backup
  (`.bak.<timestamp>`) — den lokale Jetson-repo divergerer fra laptop-fork'en
  og kunne ikke synkroniseres via git.

**Test:**
- Procedure:
  1. Boot Jetson, plug bokse ind i vilkårlig rækkefølge
  2. `ros2 launch energirobotter_bringup servos.launch.py`
  3. Verificér i log at alle tre drivers udskriver
     `Serial communication successful`
  4. Åbn `slider_control` GUI, bevæg en slider, verificér at den
     korrekte fysiske led bevæger sig
- Resultat (2026-05-27):
  - Alle tre drivers initialiserede succesfuldt uden ompluggning
  - Slider-bevægelse på venstre skulder pitch flyttede den rigtige servo
  - Brugerbekræftelse: "yes det virker"

**Til rapport:**
- Pointe til driftssikkerhed: går fra **proceduremæssig garanti** (manuel
  rækkefølge) til **strukturel garanti** (fysisk port → logisk funktion).
- Dokumentation opdateret i `README.md` med ASCII-layout af USB-boksen og
  mapping-tabel.
- Egnet figur til rapporten: foto af USB-boksen + diagram der viser de fire
  porte (GUL, SORT/ZED, HVID, RØD) og hvilken funktion hver styrer.

---

## Kap. 6 — Idriftsættelse og test

### 6.1 Feedback-publisher i `wattson_servo_manager_node` (2026-05-28)

**Hvad:**
Servo-manager-noden publicerer nu et nyt topic `/joint_states_feedback`
(`sensor_msgs/JointState`) med de **faktiske** servovinkler aflæst tilbage
fra hardwaren via `DriverWaveshare.get_servo_angles()`. Topicet spejler
`/joint_states` i navne og enheder (radianer), men indeholder den målte
position i stedet for den kommanderede.

**Hvorfor:**
- Forudsætning for kvantitativ test af servo-controlleren. Uden adgang til
  den faktiske vinkel kan man kun antage at servoen følger ordren — man
  kan ikke måle om den gør det, eller hvor godt.
- ST3215 har en intern lukket-sløjfe PID. Producentens datablad opgiver
  ingen step-respons-tal, og PID-gains er forsøgsmæssigt indstillet i
  servo-config JSON. Vi har derfor brug for at karakterisere det faktiske
  system *som bygget* (servo + 3D-printet ledforbindelse + intern
  hastighedsbegrænsning) frem for at stole på katalogtal.
- Alternativer overvejet og forkastet:
  - **Eksternt encoder-tilbageblik (separat IMU/encoder):** kræver
    yderligere hardware og kabling, ligger ude af scope for arm-
    delsystemet.
  - **Estimering fra strømtræk:** mulig, men giver kun belastning, ikke
    position.
  - **Læse intern feedback direkte fra driveren i hver test-node:** ville
    duplikere serial-trafik og kollidere med servo-manager's ejerskab af
    porten. **Centraliseret feedback-publisher er den rene løsning.**

**Implementering:**
- Fil: `pkgs_control/servo_control/servo_control/wattson_servo_manager_node.py`
- Tilføjet:
  - `self.pub_joints_feedback = self.create_publisher(JointState, "/joint_states_feedback", 10)`
  - Helper `_publish_feedback(drivers)` der samler `get_servo_angles()` fra
    en eller flere drivers, konverterer fra deg til rad, og publicerer.
  - Kald af helperen efter `update_feedback()` i begge timer-callbacks
    (arms-timeren publicerer feedback for venstre+højre arm + hoved,
    hands-timeren publicerer for hænder).
- Ingen ændring i JSON-konfig nødvendig — `update_feedback()` læste i
  forvejen for alle servoer (kommentaren `# if self.servos[name].feedback_enabled`
  i `driver_servos.py` viser at filteret er bevidst slået fra).

**Test:**
- Build: `colcon build --packages-select servo_control --symlink-install`
  → succes (2026-05-28).
- Import-test: `python3 -c "from servo_control.wattson_servo_manager_node import ServoManagerNode"`
  → OK.
- Hardware-test: udestår — kræver Jetson-sync. Verificeres ved at køre
  `servos.launch.py` og `ros2 topic hz /joint_states_feedback` (skal vise
  ca. 10 Hz, matching control_frequency-parameteren).

**Til rapport:**
- Pointe: separationen "manager publicerer feedback, test-noder forbruger"
  følger ROS' pub/sub-mønster og holder serial-portens ejer entydig.
- Egnet figur: tidsforløb af én kommanderet vinkel + den faktiske
  feedback, plottet med `step_response_node` (se 6.2).

---

### 6.2 `step_response_node` — kvantificering af servo-respons (2026-05-28)

**Hvad:**
Nyt værktøj `step_response_node` i `arm_commissioning`-pakken der
kommanderer en step-input til én valgt led, logger den faktiske
positionsfeedback med høj rate (50 Hz), og producerer:

1. En CSV-fil med kolonnerne `t_s, cmd_deg, actual_deg`.
2. Et PNG-plot der viser kommando og faktisk vinkel på samme akse, med en
  textbox med beregnede mål.
3. Klassiske mål for step-respons:
   - **Rise time** (10 % → 90 % af step-amplituden)
   - **Overshoot** (procent over target)
   - **Settling time** (første tid hvor signalet permanent ligger inden
     for ±2 % af target)
   - **Steady-state error**

**Hvorfor:**
- Step-respons er den standardprocedure i klassisk reguleringsteori til
  at karakterisere en lukket-sløjfe PID-controllers ydelse. Det giver
  målbare tal der direkte kan refereres i rapportens analyse-afsnit og
  sammenlignes mellem leddene (er nogle led overdæmpede? har nogle
  overshoot pga. lille belastning?).
- Resultaterne kan ydermere bruges som baseline før/efter en eventuel
  justering af PID-gains i servo-config JSON, hvis vi senere får adgang
  til at ændre dem.

**Implementering:**
- Fil: `pkgs_commissioning/arm_commissioning/arm_commissioning/step_response_node.py`
- Parametre (alle med default):
  - `joint_name` (påkrævet)
  - `step_size_deg` (10.0)
  - `baseline_s` (0.5) — sekunder hvor target = 0° før step
  - `duration_s` (3.0)
  - `publish_rate` (50.0)
  - `output_dir` (`~/humanoid_ws/test_results`)
- Output gemmes i `<output_dir>/<YYYY-MM-DD>/<joint>/<stamp>_step.{csv,png}`
- `matplotlib` brugt med `Agg`-backend (headless, fungerer over SSH).
- Registreret som console-script i `setup.py`.
- `python3-matplotlib` og `python3-numpy` tilføjet som `exec_depend` i
  `package.xml`.

**Test:**
- Smoke-test uden hardware (2026-05-28): node starter, opretter output-
  bibliotek, kører loop, og udskriver korrekt fejlmeddelelse når
  `/joint_states_feedback` mangler. Exit-kode 124 fra `timeout` som
  forventet.
- Hardware-test (2026-05-28, `joint_left_shoulder_pitch`, step=10°,
  duration=12 s): rise time = 0.20 s, overshoot = 0 %, settling time =
  3.69 s (±10 %), slutfejl = 0.00°, n = 24 samples. Plot:
  `~/humanoid_ws/test_results/2026-05-28/joint_left_shoulder_pitch/2026-05-28_103729_step.png`.
  Bemærk: settling-tid på 3.69 s afspejler **ikke** servoens fysiske
  dynamik men command-pipelinens latency (se 6.4) — det "flade"
  stykke før kurven stiger er tiden fra step-publish til at
  `self.angle` opdateres i manageren.
- Senere multi-joint forsøg (`shoulder_roll`, `elbow_pitch`) viste 0°
  ændring i den loggede feedback selvom armen reelt bevægede sig —
  fordi feedback-publisheren rapporterer cached commanded position, og
  for disse led blev kommandoen sat før logging startede. Diagnosen
  dokumenteret i 6.4.

**Parametre tilføjet under hardware-validering:**
- `settling_tol_pct` (default 10.0): tidligere hardcoded til 2 %, som
  for små step (5–10°) gav target-vindue på 0.1–0.2°, mindre end
  ST3215's interne dødzone (~0.3–0.5°). 10 % giver fysisk meningsfulde
  settling-tider.

**Bug fix under hardware-validering:**
- Metric-beregningen sammenlignede `cmd` (logisk delta fra baseline,
  0 → step_size) direkte med `actual` (fysisk absolut vinkel, fx 145°),
  hvilket gav nonsens (steady-state-error ≈ 145°). Fix: beregn
  `baseline_phys = mean(actual[pre-step])` og normalisér
  `actual_norm = actual - baseline_phys` før alle metric-sammenligninger.
  Plottet viser nu `cmd` vs. `actual_norm` på samme delta-akse.

**Til rapport:**
- Procedure egnet til metode-afsnit: én tabel med joint, step, rise time,
  overshoot, settling time, steady-state error for hver af de 7 led.
- Plot fra én repræsentativ led som figur, med kommando vs. faktisk og
  alle mål annoteret.
- Diskussionspunkt: hvis 3D-printede tandhjul har slør, vil settling
  time være højere ved små step (dødzone) end ved store step.
- **Vigtig forbehold der skal med i rapporten:** målingerne karakteriserer
  **command-pipelinen** (ROS-topic → manager → SDK-write), ikke
  servoens lukkede regulatorsløjfe. Begrundelse i 6.4.

---

### 6.3 `repeatability_node` — repeterbarhed mellem to poser (2026-05-28)

**Hvad:**
Nyt værktøj `repeatability_node` i samme pakke. Sender én valgt led `N`
gange frem og tilbage mellem to vinkler A og B, holder hver position i
en konfigurerbar periode, og logger den **sidste** målte vinkel i hvert
hold-vindue.

Output:
1. CSV: kolonner `cycle, final_at_A_deg, final_at_B_deg`.
2. PNG: side-om-side histogrammer for pose A og pose B, med vertikale
  linjer for target og målt mean.
3. Statistik printet i terminal og overlagt på plot: mean, std,
  max-deviation fra target, range.

**Hvorfor:**
- En arm bygget af 3D-printede komponenter har flere kilder til
  positions-ikke-determinisme:
  - Backlash i printede tandhjul/coupler
  - Mekanisk slør i lejer
  - Servo-controllerens egen positions-noise omkring sat-punkt
  - Termiske effekter ved længere kørsler
- Den samlede effekt er det interessante for en bruger af systemet. Vi
  måler det "som-bygget" i stedet for at forsøge at adskille bidragene
  analytisk.
- Specifikt scenarie i rapportens diskussion (kap. 7): konsekvens af at
  alle komponenter er 3D-printet — dette værktøj giver tal til at
  understøtte påstande om repeterbarhed/slid.

**Implementering:**
- Fil: `pkgs_commissioning/arm_commissioning/arm_commissioning/repeatability_node.py`
- Parametre:
  - `joint_name` (påkrævet)
  - `pose_a_deg` (0.0), `pose_b_deg` (20.0)
  - `cycles` (10)
  - `hold_s` (1.5)
  - `publish_rate` (50.0)
  - `output_dir` (samme som step-response)
- Output sti: `<output_dir>/<YYYY-MM-DD>/<joint>/<stamp>_repeat.{csv,png}`
- Sample-strategi: noden bruger blot den seneste feedback-værdi modtaget
  inden phase-skift som "final" position. Det er en konservativ tilgang
  (kunne forfines til middel over de sidste 100 ms hvis støj viser sig
  at være et problem).

**Test:**
- Smoke-test uden hardware (2026-05-28): node starter, planlægger
  cyklusser, fejler korrekt på manglende feedback. OK.
- Hardware-test: udestår.

**Til rapport:**
- Tabel med joint, A, B, n, mean_A, std_A, max_dev_A, range_A, og
  tilsvarende for B.
- Diskussionspunkt: er std_dev ens for A og B, eller er den højere ved
  ekstreme vinkler (kunne indikere tandhjul-belastning)? Er der drift
  over `cycles` (sidste cyklus afviger mere end første) → opvarmning
  eller slid?
- Egnet figur: histogrammet for det led der har størst spredning, til at
  illustrere problemet visuelt.

---

### 6.4 Diagnostik — feedback-publisher rapporterer commanderet, ikke faktisk position (2026-05-28)

**Hvad:**
Under hardware-validering af `step_response_node` og `repeatability_node`
blev det opdaget at den `/joint_states_feedback`-topic som `wattson_servo_manager_node`
publicerer, **ikke afspejler servoens faktiske målte position**. Den
rapporterer i stedet den senest kommanderede vinkel cached i
`ServoControl.angle`.

Konsekvens: vores commissioning-værktøjer kan i den nuværende
konfiguration kun måle command-pipeline-latency og ekstern observation
(visuel/foto), ikke direkte servo-dynamik.

**Hvorfor (root cause — tre-niveau gating på `feedback_enabled`):**

Flag-værdier i produktions-config (`servo_arm_*_params.json`):
```
"feedback_enabled": false   # alle arm-servoer
```

1. **Per-servo gate** i `servo_control/src/servo_control.py`:
   - `set_feedback_pwm()` (linje 111): `if not self.feedback_enabled: return`
     → `self.angle` opdateres aldrig fra hardware-læsning.
   - `compute_command()` (linje ~220): `if not self.feedback_enabled: self.angle = angle_cmd`
     → `self.angle` sættes lig den seneste **commanderede** vinkel.

2. **Driver-instans gate** i `servo_control/src/driver_waveshare.py`:
   - `DriverWaveshare.__init__` (linje 33): `feedback_enabled=False` default.
   - `wattson_servo_manager_node` instantierer driveren uden at sætte
     argumentet → driveren er passive på read-siden.
   - `read_feedback()` (linje 105): `if not self.feedback_enabled: return`.
   - `_sync_commands_read()` (linje 153): `if not self.feedback_enabled: return`
     → baggrundstråden `loop_thread_read` kører tomt; SCServo SDK's
     `groupSyncRead` har aldrig data klar.

3. **Resultat**: `_publish_feedback([drivers])` → `driver.get_servo_angles()`
   → returnerer `self.servos[name].angle` → cached commanderet position.

**Hvorfor vi ikke fixer det nu:**

At aktivere feedback ville ændre kontrol-pipelinens karakter fra rent
open-loop til delvist closed-loop:
- Per-servo `feedback_enabled=true` slår `set_feedback_pwm` til, som
  *kunne* skrive til hardware (afhænger af `set_pwm`-stien i ServoControl).
- Open-loop er den **dokumenterede produktions-konfiguration** for armene;
  hele PID-løkken kører internt i ST3215. Commissioning-værktøjerne skal
  måle systemet **som det leveres**, ikke en hypotetisk variant.
- Risikoen ved at flippe flaget mid-commissioning er at ændre den
  observerede dynamik samtidigt med at vi prøver at måle den.

**Empirisk bekræftelse (2026-05-28):** Vi forsøgte alligevel at aktivere
feedback for at få ægte position-data:
- Patch: `feedback_enabled=True` til `DriverWaveshare` for begge arme +
  flippede alle 7 servoer i `servo_arm_{left,right}_params.json` til
  `"feedback_enabled": true`. Rebuilt + restarted manager på Jetson.
- Resultat: `/joint_states_feedback` pulserede nu med ægte hardware-data
  (`ros2 topic hz` på Jetson viste ~15 Hz), MEN arm-leddene begyndte
  straks at **oscillere frem og tilbage** uden at have modtaget nogen
  ROS-kommando.
- Årsag: `ServoControl.compute_command` ændrer beregning når
  `feedback_enabled=True`. I open-loop er `self.angle = sidste cmd`
  (monotont mod target). I closed-loop bliver `angle_delta =
  angle_target - actual_pos`, så `angle_cmd` rampes ud fra reel
  position. Med de eksisterende PID-gains (tunet til open-loop /
  passiv brug) og 10 Hz control_frequency er sløjfen ustabil.
- **Konklusion**: feedback-flag kan **ikke** flippes uden samtidig
  PID-tuning. Det er en strukturel egenskab ved kontrolloop-designet,
  ikke en konfig-bug. Reverteret til open-loop med det samme.

Alternativer overvejet:
- **(a) Enable `feedback_enabled` per arm-servo i JSON.** Ændrer
  kontrolloop-adfærden. Forkastet for nu.
- **(b) Sidecar SDK-call udenom drivertråden i `_publish_feedback`.**
  Kræver eksklusiv adgang til serial-porten samtidig med at
  `loop_thread_write` skriver kommandoer; ville indføre race-conditions
  uden eksplicit locking. Kompleks for marginal commissioning-gevinst.
- **(c) Dedikeret read-only commissioning-mode på driveren.** Mest
  korrekt løsning, men er ny feature og falder uden for opgavens scope.
- **(d) Acceptér begrænsningen, dokumentér det, og udnyt det
  command-pipelinen *kan* måle.** **Valgt.**

**Hvad værktøjerne så **kan** måle uden config-ændringer:**

- **Command-pipeline-latency**: tiden fra `JointState` publiceres på
  `/joint_states` til `wattson_servo_manager_node` har eksekveret
  `compute_command` og `self.angle` afspejler den nye target. Set
  empirisk: ~3 s for shoulder_pitch step (sandsynligvis dominerede af
  manager's interne control_frequency-loop og kommando-batching).
- **Forventet kontrol-frekvens**: `ros2 topic hz /joint_states_feedback`
  skal vise `control_frequency` parameteren (~10 Hz).
- **Ekstern observation**: foto før/efter, manuel vinkelmåling, eller
  ekstern sensor → uden for software-pipelinen.

**Implementering:**
- Ingen kode-ændring foretaget. Kun diagnose dokumenteret her.
- Filer hvor gating-kæden findes (til reference i rapport):
  - `servo_control/src/servo_control.py` linje 75, 111, ~220
  - `servo_control/src/driver_waveshare.py` linje 33, 105, 153
  - `servo_control/wattson_servo_manager_node.py` (instantierer driver
    uden `feedback_enabled=True`)
- Konfig:
  `energirobotter_bringup/config/servos/servo_arm_left_params.json` og
  tilsvarende for `right` — alle med `"feedback_enabled": false`.

**Til rapport:**
- **Framework-discovery til diskussions-afsnit:** robotten kører i sin
  nuværende konfiguration **fuldstændig open-loop på arm-niveau**;
  hver ST3215-servo har sin egen indlejrede PID, og ROS-laget er en
  ren kommando-fanout uden positions-tilbagemelding. Det er et
  bevidst design-trade-off (enkelhed, færre serial-bus-collisions),
  men det betyder at *softwarestakken er blind for hvor armen faktisk
  er* — al closed-loop-opførsel sker inde i servoerne selv.
- **Lukket sløjfe er ikke en "drop-in"-ændring:** Vores forsøg på at
  aktivere ROS-niveau feedback gav øjeblikkelig oscillation (se
  empirisk bekræftelse ovenfor). En reel closed-loop-implementering
  ville kræve: (a) re-tuning af `gain_P/I/D` i alle JSON-filer for
  closed-loop scenarie, (b) højere `control_frequency` (10 Hz er for
  langsomt til closed-loop på en hurtig servo), (c) anti-windup på
  integralleddet. Det er en separat opgave på størrelse med dette
  projekt.
- **Konsekvens for commissioning:** klassiske step-respons- og
  repeterbarhedsmål kan ikke beregnes fra ROS-topics alene. Enten
  skal feedback aktiveres (kræver kontrolloop-redesign), eller der
  skal bruges en ekstern sensor.
- **Gravitations-sag observation**: shoulder_pitch hænger ved
  ~145° når default er 150° — armens egenvægt overvinder servoens
  holde-moment med ~5°. Bekræftet af foto. Dette er kun synligt
  fordi vi i `step_response_node._compute_metrics` registrerer
  `baseline_phys_deg` før step.

---

### 6.5 Test-output-konvention

Alle testværktøjer skriver til samme rod-bibliotek:

```
~/humanoid_ws/test_results/<YYYY-MM-DD>/<joint_name>/<HHMMSS>_<test>.{csv,png}
```

Dette holder rådata adskilt fra kode (ikke i git), grupperet pr. dag og
pr. led. Direkte egnet til at uploade som bilag til rapporten i
`Appendices/test_data/`.

---

### 6.6 Statisk holdetilstand — arm falder i udstrakt pose (2026-05-28)

**Hvad:** Under VR-teleoperation observeret at armen langsomt falder
nedad af sig selv når den holdes ude i en udstrakt pose (skulder-pitch
~ 90°, albue helt strakt), selvom der ikke kommanderes nogen ny
bevægelse. Bemærket under wired Quest 3 → `teleoperation_vuer_node` →
`elrik_kdl_kinematics_node` → `/joint_states` → servos demo.

**Årsager (sandsynlige, ikke verificeret enkeltvis):**

1. *Statisk moment overstiger servoens holdemoment.* ST3215 er
   specificeret til ca. 30 kg·cm. En udstrakt arm har den maksimale
   momentarm — armens egenvægt × afstand fra skulderen giver et
   gravitationsmoment der i værste fald ligger tæt på eller over
   servoens stall-værdi.
2. *Open-loop holdetilstand.* Den ydre kontrol kører i open-loop og
   sender ikke aktivt korrigerende kommandoer; den nedstrøms ST3215
   firmware-PID forsøger at holde sidste `Goal_Position`, men ved en
   stationær fejl der ligger under dens interne deadband (eller hvis
   `Torque_Limit` er sat konservativt) får tyngdekraften lov til
   langsomt at trække armen ned.
3. *Termisk derating / overload-beskyttelse.* Hvis servoen har holdt
   stort moment i et stykke tid stiger `Present_Temperature`; ST3215
   reducerer momentet automatisk for at undgå skade.
4. *Backlash i geartog.* Selv ved perfekt holdt `Goal_Position` giver
   gear-slør et par graders synlig "creep" i ledet, hvilket forstærkes
   af tyngdekraften.

**Implikation for projektet:** Robotens nyttige arbejdsrum er reelt
mindre end den geometriske rækkevidde. Poser med fuldt strakte arme i
horisontal stilling bør undgås i demo/teleoperation — eller kun bruges
kortvarigt. Dette er en mekanisk/dimensioneringsmæssig begrænsning, ikke
en software-fejl.

**Foreslåede næste skridt (efter VR-demoen):**

- Logge `Present_Load`, `Present_Temperature`, `Present_Position` vs
  `Goal_Position` for skulder-pitch og albue-pitch under en kontrolleret
  *hold-test* (kommandér armen til horisontal udstrakt og log i fx 30 s).
  Sammenligne mod tilsvarende log med armen hængende lodret nedad
  (lille momentarm).
- Aflæse `Torque_Limit` for hver arm-servo via SCServo SDK og vurdere
  om den er sat lavere end nødvendigt.
- Hvis problemet bekræftes mekanisk: dokumentere worst-case statisk
  moment vs servo-specifikation i rapportens kapitel om mekanisk
  dimensionering, og evt. anbefale gear-reduktion eller modvægt for
  fremtidige iterationer.

**Opdatering samme dag (efter slider-verifikation):**

- Den servo der så ud til at fejle blev efterfølgende verificeret OK ved
  manuel test med `slider_control.launch.py` — den responderer korrekt på
  position-kommandoer. Konklusionen om at servoen var brændt af var altså
  forkert.
- Den observerede "faldende arm" skete *i forbindelse med shutdown* af
  `teleoperation_vuer_node` (Ctrl+C). Mest sandsynlige forklaring: under
  shutdown nåede IK-noden at publicere én sidste `JointState` baseret på
  en transient/ustabil VR-tracking-værdi (når headsetet mister tracking
  eller man tager fingrene væk), og servo-manageren rampede derefter mod
  denne stale target uden at flere kommandoer kom efter. Det er altså en
  kombination af (a) reel mekanisk grænse i udstrakt pose, og (b)
  manglende håndtering af graceful shutdown / stale-target i kæden
  `tracking → IK → servo`.
- Dette ændrer ikke konklusionen om at *worst-case statisk moment* er en
  reel begrænsning der bør indgå i rapportens diskussion af arbejdsrum
  — men forklarer hvorfor symptomet fremstod dramatisk: armen blev
  effektivt kommanderet ned, ikke bare "tabt".
- Mulig forbedring: lade `teleoperation_vuer_node` publicere en sidste
  "safe pose" (eller seneste *kendte gode* tracking-frame) ved
  graceful shutdown, så servo-manageren ikke står tilbage med en stale
  target fra et øjebliks dårligt tracking.


---

### 6.7 Kinematics-node timer-race ved opstart (2026-05-28)

**Hvad:**
`elrik_kdl_kinematics_node` crashede sporadisk under opstart med
`AttributeError: 'ElrikKdlKinematics' object has no attribute 'end_effectors'`.
Fixet ved at flytte `create_timer(0.1, callback_timer_publish_joint_states)`
fra første del af `__init__` til slutningen, efter `retrieve_urdf()` og alle
end-effector-felter er initialiseret.

**Hvorfor:**
- `rclpy`-timere er **armed med det samme** ved `create_timer`.
- `retrieve_urdf()` kalder `rclpy.spin_once()` for at vente på
  `/robot_description`-topicet. Mens spin'en kører, kan executor'en
  dispatche timer-callback'et.
- Hvis det sker før `self.end_effectors = …`-linjen længere nede i
  `__init__`, så fejler callback'et ved første attribut-adgang.
- Timing-race: optræder kun nogle gange (når `/robot_description` er
  langsom nok til at trigge én tick på 100 ms-timeren under spin'en).

**Implementering:**
- Fil: `pkgs_control/elrik_kdl_kinematics/elrik_kdl_kinematics/elrik_kdl_kinematics_node.py`
- Commit: `885aa06` (samme commit som step_response/repeatability — fundet
  fordi step-response-pipeline-end-to-end-test ramte fejlen ved opstart af
  IK-noden).
- Diff: 4 linjer flyttet — `create_timer`-kaldet udklippet fra linje 45-46
  og indsat efter "Kinematics node ready!"-loggen, med kommentar der
  forklarer rækkefølge-kravet.

**Test:**
- Manuelt verificeret: 10 successive starts af `kinematics_manager`-launch'en
  uden AttributeError-stacktrace.

**Til rapport:**
- Egnet som lille bullet i et "diskussion af software-stabilitet"- eller
  "lessons learned"-afsnit. Ikke en hovedhistorie, men illustrerer en
  konkret rclpy-fælde værd at advare om: timer-creation skal være sidste
  trin i `__init__`, ellers risikerer man dispatch under konstruktion.

---

### 6.8 Power-monitor stack — per-servo elektrisk telemetri (2026-06-10)

**Hvad:**
End-to-end-pipeline til at måle servoernes elektriske forbrug pr. led,
publicere det som ROS-topic, og logge det til CSV+PNG med valgfri
live-viewer. Fire lag:

1. **Per-servo måling** i `ServoControl` — nye attributter `voltage` og
  `current`, plus settere `set_feedback_voltage(raw)` og
  `set_feedback_current(raw)` der konverterer ST3215's rå register-værdier
  (`PRESENT_VOLTAGE` reg 62 = 0.1 V/unit; `PRESENT_CURRENT` reg 69-70 =
  6.5 mA/unit, bit 15 = fortegns-bit).
2. **Driver-aggregation** i `DriverWaveshare._update_servo_feedback` — gemmer
  V/A pr. servo. Nye getters `get_servo_voltages()`, `get_servo_currents()`,
  `get_servo_powers()`.
3. **Manager-publish** — `wattson_servo_manager_node` har nu et nyt
  `/servo_power` (sensor_msgs/JointState) topic ved siden af
  `/joint_states_feedback`. Mapping: `position[i]` = volt, `velocity[i]` =
  ampere, `effort[i]` = watt for servo `name[i]`.
4. **Commissioning-værktøj** — nyt `power_monitor_node` i `arm_commissioning`,
  parametre: `scenario`, `duration_s`, `live`, `live_window_s`, `output_dir`.
  Output: `<output_dir>/<dato>/<scenario>/<stamp>_power.{csv,png}`.
  CSV-kolonner: `t_s, V_<servo>..., A_<servo>..., W_<servo>..., total_W`.
  PNG: total-W timeseries (top), per-servo bar chart (bund, top 12 ledere).
  Live-viewer: `TkAgg` + `FuncAnimation`, graceful headless-fallback.

**Hvorfor:**
- Kapitel 7 har brug for kvantitative tal for elektrisk forbrug pr.
  scenarie — datablads-tal for ST3215 dækker kun max-træk under stall,
  ikke realistisk demo-forbrug.
- Per-led decomposition er nødvendig for at koble §6.6 (statisk
  holdetilstand) til strømmål — vi forventer at shoulder_pitch dominerer
  i udstrakte poser.
- Live-viewer giver hurtig diagnose under demo (kan man se en spike når
  armen rammer en grænse?).
- CSV-output går direkte i `Appendices/test_data/` til rapporten.

**⚠ Vigtig forbehold der SKAL med i rapporten:**
- Målingerne dækker **kun servo-busset** (24 V til ESP32-bokse → servoer).
- Følgende forbruges men måles **ikke**:
  - Jetson Orin Nano (~7-15 W typisk)
  - ZED 2i kamera (~1.9 W)
  - ESP32-bokse selv (~0.5-1 W stk.)
  - PSU-tab og kabel-resistens
- Det reelle total-systemforbrug er **højere** end `total_W` i CSV'en.
- Værdien er at vi kan **sammenligne scenarier mod hinanden** og
  identificere de tunge led — ikke at vi har en kalibreret system-måler.

Forkastede alternativer:
- **(a) Eksternt clamp-meter på PSU-output:** ville give kalibreret
  total-forbrug, men ingen per-led decomposition. Kan stadig laves som
  supplement til rapporten hvis tid tillader det.
- **(b) Subscribe direkte til ROS-topic uden manager-publish:** ville
  duplikere serial-reads og kollidere med drivertråden — samme rationale
  som §6.1 (centraliseret feedback-publisher).
- **(c) Beregn watt fra position-derivat × moment-konstant:** kræver
  præcise mekaniske parametre for hvert led, mere usikkerhed end direkte
  V·A-måling. Forkastet.

**Implementering:**
- Filer:
  - `pkgs_control/servo_control/servo_control/src/servo_control.py` (+36 linjer)
  - `pkgs_control/servo_control/servo_control/src/driver_servos.py` (+39 linjer)
  - `pkgs_control/servo_control/servo_control/wattson_servo_manager_node.py`
    (+105 linjer; del af samme commit som §6.1 feedback-publisher)
  - `pkgs_commissioning/arm_commissioning/arm_commissioning/power_monitor_node.py`
    (419 linjer — nyt værktøj)
  - `pkgs_commissioning/arm_commissioning/docs/power_monitor.md` (185 linjer
    bruger-dokumentation med samme forbehold)
- Commit: `2ea1b48`
- `python3-tk` tilføjet til `package.xml` (live-viewer kræver TkAgg-backend).

**Test:**
- Smoke-test (2026-06-10): syntetisk `JointState`-publisher kørte mod
  `power_monitor_node` med `live:=true`. Resultater: gyldig CSV med
  korrekte kolonner, PNG genereret med begge sub-plots, live-viewer-vinduet
  åbnede og opdaterede ved 10 Hz uden frame-drops.
- Hardware-test: udestår — planlagt til næste lab-dag (foreslået scenarier:
  `idle`, `teleop_neutral`, `teleop_extended`, `animation_wave`).

**Til rapport:**
- Tabel: scenarie × (idle_W, mean_W, peak_W) + top-3 mest-forbrugende led.
- Figur: én repræsentativ time-series (helst med en synlig spike fra fx
  en hånd-griber) + bar chart fra samme run.
- Diskussion:
  - Sammenhæng med §6.6: er shoulder_pitch målbart varmere/mere strøm-
    krævende i udstrakt pose end i neutral?
  - Eksplicit afgrænsning: hvad indgår IKKE i målingen, og hvorfor.
  - Implikation for batteridrift / PSU-dimensionering for fremtidige
    iterationer (hvis det er relevant for projektets scope).

---

### 6.9 Tkinter demo-launcher GUI (2026-06-10)

**Hvad:**
Et-vindue control panel (`launcher_gui_node` i `arm_commissioning`) der
samler de typiske demo-services bag Start/Stop-knapper med live status,
samlet log-rude og en "Start demo"-knap der eksekverer den kanoniske
sekvens (DHCP → camera → adb reverse → vuer) med 1-6 sekunders pauser
mellem trin. 8 konfigurerede services: `dhcp`, `adb_reverse`,
`jetson_camera`, `jetson_servos`, `vuer_camera`, `vuer_ik`,
`power_monitor`, `animation_idle1`. 3-punkts pre-flight checklist
(ESP32-port-mapping, Jetson-DHCP-status, Quest-USB-debug).

**Hvorfor:**
- Den dokumenterede demo-procedure krævede 5-6 manuelt åbnede terminaler
  med præcis rækkefølge og argument-syntaks. Det er fragilt under en
  eksamens-fremvisning hvor man både skal tale og operere.
- Et samlet panel reducerer demo-fejl-rummet (ingen tastefejl i
  kommandoer), giver en visuel pre-flight checklist (man glemmer ikke
  ESP32-port-mapping), og samler stdout fra alle services i én log
  (lettere at se hvor noget fejler).

Forkastede alternativer:
- **(a) Bash-script der spawner `gnome-terminal`-vinduer:** virker, men
  giver hverken samlet log eller fælles stop-knap. Processer overlever
  scriptet og skal kill'es manuelt med `pgrep -f`-magi.
- **(b) Streamlit/web-dashboard:** kræver browser-kontekst, langsommere
  at starte, og GUI er fint til en lokal laptop — overkill med web-server.
- **(c) ROS launch-fil med alle noder samlet:** kan ikke håndtere
  SSH/sudo/adb gracefully (de er ikke ROS-noder), og ville stadig kræve
  separate terminaler for at se output. Launch-modellen passer ikke til
  bringup-orkestrering.

**Implementering:**
- Filer:
  - `pkgs_commissioning/arm_commissioning/arm_commissioning/launcher_gui_node.py`
    (434 linjer)
  - `pkgs_commissioning/arm_commissioning/docs/launcher_gui.md`
    (bruger-dokumentation)
- Commits: `f0c9af4` (initial), `c8cde61` (checklist opdateret efter §5.1's
  faste port-bindings — den gamle "USB-rækkefølge"-instruktion fjernet og
  erstattet med RØD/GUL/HVID-port-mapping; samtidig fjernet ESP32 Serial
  Forwarding-dans da firmware fra 2026-05-27 starter den automatisk).
- Stdlib `tkinter` (kun apt-pakken `python3-tk` kræves som runtime-dep).
- `subprocess.Popen` med `preexec_fn=os.setsid` → clean stop af proces-
  grupper via `os.killpg(SIGINT)`, hard `SIGTERM` efter 3 s grace.
- SSH-services bruger `ssh -tt` for at videreføre signaler til remote
  `ros2 launch` (force-tty: så Ctrl+C går igennem).
- DHCP via `pkexec dnsmasq …` → grafisk Polkit-prompt, ingen
  sudo-password embedded i GUI'en.

**Test:**
- Module-import OK (alle 8 services definerede, demo-sekvens loadet).
- Entry-point smoke-test (2026-06-10): vinduet åbner, services vises
  grupperet i Network/Robot/Demo-sektioner, status-prikker opdateres,
  log-rude virker. Eksplicit ikke startet under smoke-test for at undgå
  mid-test sudo-prompt.
- Fuld-stak hardware-test: udestår — planlagt under første rigtige
  demo-rehearsal.

**Til rapport:**
- Mest relevant for et "demonstration & operationel ergonomi"-afsnit
  eller appendix. Ikke en videnskabelig kontribution, men et håndværks-
  artefakt værd at nævne hvis der er plads.
- Diskussionspunkt: forskellen mellem "værktøjet virker for udvikleren
  der byggede det" og "værktøjet kan demonstreres uden assistance" —
  GUI'en er en konkret instans af det.
- Egnet figur: skærmbillede af GUI'en med checklisten tikket og services
  i grøn status — viser visuelt at robot-bringup er en samlet handling.

---

## Skabelon til nye entries

```
### X.Y Titel (YYYY-MM-DD)

**Hvad:**

**Hvorfor:**

**Implementering:**
- Fil(er):
- Commit:

**Test:**
- Procedure:
- Resultat:

**Til rapport:**
```
