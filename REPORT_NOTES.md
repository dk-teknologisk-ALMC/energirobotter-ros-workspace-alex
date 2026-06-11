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

#### 6.9.1 Iterationer & bug-fixes (2026-06-11)

GUI'en var brugbar efter første implementering, men flere konkrete
problemer dukkede op i smoke-test og første rigtige hardware-test.
Hver iteration er dokumenteret nedenfor med problem → analyse → løsning,
fordi forløbet er mere illustrativt end slutresultatet alene.

**Bug 1 — Window-close-hang når DHCP kørte (commit `1964712`).**
- *Symptom:* Hvis `dhcp` (startet via `pkexec dnsmasq …`) kørte og man
  lukkede GUI'en, frøs Tk-vinduet og processen skulle dræbes med
  `pkill`.
- *Årsag:* `on_close` → `stop_all` → `Service.stop` kaldte
  `os.killpg(getpgid(pid), SIGINT)` på dnsmasq, som kører som `root`
  (pkexec). Almindelig bruger må ikke signalere root-processer →
  `PermissionError` blev kastet, ikke fanget, og bobled op gennem
  `WM_DELETE_WINDOW`-handleren. Tk's main-loop blev stående med en
  unhandled exception og malede aldrig destroy.
- *Løsning, to dele:*
  1. `Service.stop` fanger nu `PermissionError` (ud over den
     forventede `ProcessLookupError`) og logger en oplysende besked i
     stedet for at kaste.
  2. Service-spec'en udvidet med valgfrit `stop_command`-felt; for
     `dhcp` er det `pkexec pkill -TERM dnsmasq` så stop foregår med
     samme privilegerede kanal som start. `on_close`/`stop_all` er
     desuden wrapped i try/except, og `destroy` schedulered via
     `self.after(1500, …)` så subprocesser får 1,5 s grace.
- *Verifikation:* lukkede GUI'en gentagne gange med dhcp running —
  ingen hang, dnsmasq stoppes korrekt.
- *Lessons learned for rapport:* Når en GUI orkestrerer privilegerede
  processer, skal kontrolflowet kunne håndtere både "kan ikke se
  processen" (allerede død) og "må ikke signalere processen"
  (privilegium-mismatch). Privilegium-eskalering via pkexec er nem at
  starte men kræver symmetrisk privilegeret stop.

**Bug 2 — SSH-services prompted for password i en usynlig terminal
(commit `47c55ef`).**
- *Symptom:* Ved første `Start` på `jetson_camera` skete der
  tilsyneladende ingenting; service-pillen blev rød efter et par
  sekunder. Loggen viste `…: Permission denied, please try again.` i
  loop.
- *Årsag:* SSH til Jetson bruger password (key var ikke deployed på
  test-tidspunktet). GUI-Popen er startet uden TTY (det er bevidst —
  vi vil ikke have en konsol-pop-up pr. service), så SSH kunne
  hverken læse stdin eller åbne `/dev/tty`. Den ledte derefter efter
  en ASKPASS-helper, men der var ingen `SSH_ASKPASS`-binær på
  systemet (`ssh-askpass-gnome` ikke installeret).
- *Forsøgt fix der fejlede:* `sudo apt install ssh-askpass-gnome`
  fejlede grundet en urelateret apt-konflikt mellem
  `nvidia-dkms-535` og `nvidia-driver-535` på maskinen. Vi vurderede
  at det var uden for opgavens scope at oprydde i Nvidia-driver-
  stakken på en lab-maskine, så vi valgte en alternativ vej.
- *Løsning:* GUI'en skriver ved opstart en lille askpass-shellscript
  til `/tmp/launcher_gui_askpass.sh` (mode `0o700`) som blot kalder
  `zenity --password --title "$1"`. Subprocesser får så
  `SSH_ASKPASS=/tmp/launcher_gui_askpass.sh`,
  `SSH_ASKPASS_REQUIRE=force`, `DISPLAY=:0` og `stdin=DEVNULL` →
  SSH-klienten falder tilbage til ASKPASS i stedet for at fejle på
  manglende TTY, og brugeren får en grafisk Zenity-prompt for sit
  remote-password.
- *Lessons learned for rapport:* Forskellen mellem "den korrekte
  løsning" (deploy SSH-keys, eller installer den standardiserede
  askpass-helper) og "den korrekte løsning vi havde tid til" (zenity-
  shim) er værd at reflektere over i en eksamenstekst. Pragmatisme
  er ikke det samme som teknisk gæld så længe workaround'en er
  selvforklarende og dokumenteret. `zenity` er allerede installeret
  med GNOME → ingen ny systempakke kræves.

**UX-iteration 1 — Per-service log-faner (commit `47c55ef`).**
- *Motivation:* I første version havde GUI'en én samlet
  `ScrolledText`-rude. Når 4-5 services kørte samtidigt (camera +
  adb + vuer + servos) blev den linære log uoverskuelig — output fra
  ZED-kameraet (mange linjer/sek) drukner kortere men kritiske
  beskeder fra fx adb eller power-monitor. Brugeren bad eksplicit om
  separate "vinduer pr. service" fordi det "giver mere overblik over
  problemer som opstår".
- *Løsning:* Log-ruden er nu en `ttk.Notebook` med en altid-til-stede
  "Alle"-fane (kronologisk samlet stream med `[key]`-prefix, så man
  kan cross-reference timing) og per-service-faner der oprettes
  lazily første gang en service producerer output. På service-fanen
  vises beskeden uden prefix — fanen er kilden.
- *API-ændring internt:* `log_msg` skiftede signatur fra
  `log_msg(line)` til `log_msg(source_key, message)`. `source_key=""`
  bruges til system-beskeder (kun "Alle"). En ny `Service._log()`
  helper fjerner duplikering af `[key]`-formattering på kald-stedet.
- *Lessons learned for rapport:* Worth noting at design-iteration
  drevet af konkret hardware-test giver mere værdi end up-front-
  perfektionering. Den oprindelige flade log var "fin nok"
  isoleret, men ubrugelig under en faktisk multi-service-bringup.

**Note om commit-rækkefølge:**
Iteration 1 (close-hang) gik som `1964712` mens GUI'en blev pushet
første gang; iteration 2 og 3 (zenity + faner) er bundlet i `47c55ef`
fordi de blev udviklet og testet i samme arbejdsgang og deler intet
overlappende API ud over den nye `log_msg`-signatur.

**Bug 3 — `power_monitor` fejlede ved opstart med
`InvalidParameterTypeException`.**
- *Symptom:* Service-fanen viste øjeblikkeligt en stack-trace:
  `Trying to set parameter 'duration_s' to '600' of type 'INTEGER',
  expecting type 'DOUBLE'`. Exit 1.
- *Årsag:* Node'n deklarerer `duration_s` med default `30.0` →
  ROS 2 låser parameter-typen til DOUBLE. Service-spec'en sendte
  `-p duration_s:=600` (heltals-literal) → ros2 cli parsede som
  INTEGER → type-check kastede.
- *Løsning (samme commit):* `-p duration_s:=600.0`. Tilsvarende
  type-bevidsthed dokumenteret som inline-kommentar i service-spec'en
  så fremtidige justeringer husker det.
- *Lessons learned for rapport:* ROS 2's strikte parameter-type-check
  er en god ting — den fanger silent-coercion-bugs ved opstart i
  stedet for ved første brug. Men det betyder at CLI-argumenter
  skal matche node'ns deklaration eksakt, hvilket gør duck-typing-
  bringup-scripts skrøbelige.

**Bug 4 — Servo-launchen på Jetson fejlede med
`FileNotFoundError` på relativ config-sti.**
- *Symptom:* Service-fanen viste:
  `FileNotFoundError: [Errno 2] No such file or directory:
  'install/wattson_description/share/wattson_description/servo_configs/
  servo_arm_left_params.json'` efterfulgt af
  `process has died … exit code 1`.
- *Årsag:* `wattson_servo_manager_node` åbner sin config via en
  *relativ* sti der antager cwd = `~/energinet/`. Vores
  `ssh -tt … '<cmds>'` lander i remote-bruger-`$HOME` (samme katalog
  som `~`), så stien blev resolved til `~/install/...` — som ikke
  findes. Det fungerer i original-workflowet fordi den dokumenterede
  procedure starter med "`cd ~/energinet`" i terminalen.
- *Løsning (samme commit):* `JETSON_SOURCES` udvidet med `cd
  ~/energinet` før sourcing, så alle Jetson-services får samme
  consistent cwd. Det gør ingen forskel for camera-launchen (der
  bruger absolutte stier i ROS package-share), men er nødvendigt for
  servos.
- *Lessons learned for rapport:* Working-directory-antagelser er en
  klassisk skjult kontrakt der bryder, så snart kaldsstedet ikke er
  en interaktiv terminal. To muligheder her: (a) fixe node'n så
  stien er package-share-relativ (rigtigste løsning, men kræver
  ændring i upstream `servo_control`-pakken), eller (b) fixe
  call-site'n så cwd er korrekt (mindre indgriben, vores valg af
  hensyn til scope). Begge er valide — vi valgte (b) fordi opgaven
  ikke skal sprede sig ind i upstream-pakker.

**Bug 5 — `camera.launch.py` på Jetson fejlede med
`package 'zed_wrapper' not found`.**
- *Symptom:* Service-fanen viste øjeblikkeligt:
  `Caught exception in launch … "package 'zed_wrapper' not found,
  searching: ['/home/elrik/energinet/install/...', '/opt/ros/humble']"`.
- *Årsag:* Den oprindelige README dokumenterer at `zed-ros2-wrapper`
  bygges i en *separat* workspace (`~/zed_wrapper_ws/`) og at brugeren
  skal tilføje en `source ~/zed_wrapper_ws/install/setup.bash` til sin
  `.bashrc` (README sektion "ZED ROS 2 Wrapper": *"do the optional
  command of sourcing the workspace in `.bashrc`"*). Den interaktive
  procedure i docs er `ssh elrik@…; cd energinet; shumble; sw; ros2
  launch …` — som virker fordi den ydre SSH-session er interaktiv og
  derfor sourcer `.bashrc` (incl. zed_wrapper_ws). Vores GUI bruger
  derimod `ssh -tt host "kommando"` som kører non-interaktivt; bash's
  standard-guard `[[ $- == *i* ]] || return` i `.bashrc` triggers, og
  zed_wrapper_ws bliver aldrig sourcet.
- *Løsning:* `JETSON_SOURCES` udvidet til at source
  `~/zed_wrapper_ws/install/setup.bash` *eksplicit* (med en `[ -f … ]`-
  guard så det giver en klar fejlmeddelelse hvis Jetson'ens wrapper-
  workspace har en anden sti, i stedet for den kryptiske
  `package not found`).
- *Refleksion (relevant for rapport):* Den oprindelige doc er en
  *interaktiv* recept; min første implementering oversatte den
  bogstaveligt til kommandoer, men oversatte ikke konteksten
  (interaktivt vs. non-interaktivt shell). Det er et generelt mønster
  ved at automatisere en manuel procedure: man skal eksplicit
  re-implementere alle de implicitte præmisser (her: hvad `.bashrc`
  bidrager med). I praksis betyder det at automatiserings-laget skal
  enten (a) replikere `.bashrc`-side-effects eksplicit, eller (b)
  indvinde sig dem ved at køre i interaktiv mode (`bash -ic …`).
  Vi valgte (a) fordi det er mere transparent — koden i
  `JETSON_SOURCES` viser præcist hvad der bliver sourcet og
  reviewet som en del af repo'en.

**UX-iteration 2 — Animationer-fane (commit `ad72387`).**
- *Motivation:* Bringup-flow'et og animations-afspilning er to
  forskellige mentale opgaver: bringup er sjældent brugt og
  procedure-tungt; animations-afspilning er hyppigt brugt under demo
  og kun ét knap-tryk pr. handling. Det første drev af GUI'en havde
  én enkelt service-række til `idle1.csv` blandet ind med de øvrige
  bringup-services — det skalerede ikke da brugeren ville prøve
  flere animationer.
- *Yderligere fund undervejs:* Den oprindelige
  `animation.launch.py` accepterer formelt et `csv_file:=`-argument,
  men launch-filen *ignorerer* det og hardkoder
  `mimic_alexander.csv`. Vores `animation_idle1`-service brugte
  derfor reelt mimic_alexander, ikke idle1 — en *latent* bug der
  først blev synlig da vi ville gøre afspilning til en fane.
- *Løsning:* GUI'en er nu en top-level `ttk.Notebook` med to faner:
  "Bringup" og "Animationer". Animationer-fanen viser 18
  forindstillede CSV'er (samme liste som `Animation_Commands.md`)
  grupperet i fire kategorier (sikre/blide, statiske positurer,
  sekvenser, test/commissioning). Hver knap er én klik som kalder
  `ros2 run animation_player animation_player_node --ros-args -p
  csv_file_path:=…/<name>.csv -p fps:=24` over SSH til Jetson.
  CSV-stien resolves runtime via `$(ros2 pkg prefix
  energirobotter_bringup)/share/…/animations/`, så den ikke afhænger
  af workspace-layout. En `AnimationRunner`-klasse holder kun én
  animation aktiv ad gangen — start af en ny stopper den
  forrige automatisk, så servoerne ikke får modstridende kommandoer
  fra to `animation_player_node`-instanser.
- *Forkastede alternativer:*
  - **(a) En service pr. animation:** ville fylde service-listen op
    med 18 ekstra rækker (i forvejen ikke en service, da de er
    fire-and-forget). Forstyrrer mental model af "service =
    langlevende baggrundsproces".
  - **(b) Én tekstbox + dropdown:** mindre opdageligt, kræver flere
    klik. Knap-grid med danske labels er bedre i en demo-kontekst.
- *Lessons learned for rapport:* Top-level fane-opdelingen er en
  god illustration af "task-domain-split": forskellige opgaver med
  forskellige tempo og hyppighed fortjener forskellige UI-paneler
  selv om de deler en backend (samme `log_msg`-stream, samme
  SSH-sourcing-recept). Det er en mikro-version af det samme
  princip som ligger bag fx VS Code's command palette vs.
  side-bar-views.

**Bug 6 — gentagne password-prompts pr. animation og ved nødstop (commit `5ac6069`).**
- *Symptom — del A:* Hver gang en animations-knap klikkes,
  prompter zenity for SSH-password til Jetson'en. Med 18
  animationer i fanen er det helt urealistisk i en demo. Samme
  problem ramte også `jetson_camera` og `jetson_servos`-services.
- *Symptom — del B:* `pkexec`-promptet for at starte
  `dnsmasq` returnerer igen når man trykker Stop, fordi
  `stop_command` brugte `pkexec pkill`. Det er specielt slemt for
  Stop-knappen, som er det tætteste vi kommer på et nødstop —
  brugeren skal IKKE skrive password ind under et stop.
- *Diagnose:* SSH bygger en ny TCP-forbindelse for hvert
  `ssh host 'cmd'`-kald. Uden public-key auth eller multiplexing
  betyder det fuld auth-runde hver gang — og fordi vi kører
  non-TTY (gennem subprocess), ryger den auth gennem
  `SSH_ASKPASS` → zenity. På `pkexec`-siden er problemet at
  Polkit's authority-cache er kort, og at `pkexec` ikke har et
  flag svarende til `sudo`'s timestamp-cache.
- *Løsning del A — OpenSSH `ControlMaster`/`ControlPersist`.*
  Tilføjet til alle `ssh`-invokationer:
  ```
  -o ControlMaster=auto
  -o ControlPath=/tmp/launcher_gui_ssh-%r@%h:%p
  -o ControlPersist=10m
  ```
  Første forbindelse autentificerer normalt og opretter en
  Unix-domain-socket på `ControlPath`. Alle efterfølgende `ssh`
  med samme `ControlPath` slutter sig til socketen og springer
  hele auth-runden over. `ControlPersist=10m` holder master-
  daemonen oppe i 10 min efter sidste forbindelse, så genstart
  af launcher inden for vinduet heller ikke prompter.
- *Løsning del B — `pkexec dnsmasq` → `sudo -A dnsmasq` med
  signal-forwarding i stedet for `pkexec pkill`.* `sudo -A` bruger
  `SUDO_ASKPASS` (vi sætter den til samme zenity-script som
  `SSH_ASKPASS`). Vigtigere: `Service.stop` kalder nu *ikke*
  længere `sudo pkill`. Den sender SIGINT til hele subprocess-
  pgroup'en (vores `bash` + `sudo` + `dnsmasq`). Sudo's manpage
  bestemmer at signaler fra det kaldende user-process
  *videreformidles* til kommandoens børn — så selvom vi som
  ikke-root ikke kan signalere root-dnsmasq direkte (kernel-
  EPERM), når SIGINT'en frem via sudo. Resultat: Stop er
  øjeblikkeligt og kræver ingen yderligere auth.
- *Forkastede alternativer:*
  - **(i) Sudoers-NOPASSWD-entry for dnsmasq.** Permanent
    løsning, men kræver manuel rod-redigering af `/etc/sudoers.d/`
    på hver maskine — ikke ideelt for et repo-styret workspace.
  - **(ii) ssh-copy-id (public-key auth).** Også permanent og
    sikkerhedsmæssigt foretrukket, men kræver én-gangs setup på
    Jetson-siden. ControlMaster løser problemet uden at røre
    Jetson, så vi har det som default — `ssh-copy-id` er nævnt i
    koden som den "rigtige" permanente løsning.
  - **(iii) En vedvarende sudo-shell vi pipe'r kommandoer ind i.**
    Mere fragilt (man skal håndtere prompt-detection, escape,
    pipe-buffer), og signal-forwarding-tricket gør det helt
    unødvendigt.
- *Lessons learned for rapport:* "Authentication amortization" er
  generelt undervurderet i developer-tooling. Det er let at
  bygge et UI hvor hver handling teknisk virker, men hvor
  cumulative friction (samlet password-tryk) gør det praktisk
  ubrugeligt. SSH multiplexing og sudo timestamp er begge
  designed til præcis dén type "burst of related actions"-
  workflow, men de er ikke aktiveret by default — UI-laget skal
  bevidst opte ind. Specifikt for nødstop er pointen endnu
  skarpere: et stop der kræver password er per definition ikke
  et nødstop. Den slags affordance-bug ville aldrig være kommet
  til syne i unit-tests; den blev fundet ved at bruge GUI'en i
  rigtig demo-kontekst, hvilket understøtter argumentet i
  rapportens UX-afsnit om at hardware-iteration kræver
  *stedfortrædende brug*, ikke bare automatiseret verifikation.

**Bug 7 — 30-60 sekunders respons-lag på animations-knapper (commit `88a66e3`).**
- *Symptom:* Klik på "Start animation B" mens animation A kører
  → robotten gjorde ingenting i op mod et minut, og bevægede sig
  herefter mærkeligt (som om to animationer var aktive
  samtidig). Klik på "Stop animation" gav samme oplevelse —
  servoerne kørte videre 30+ sekunder før de standsede.
- *Diagnose — tre selvstændige årsager:*
  1. **Remote `ros2 run` overlevede lokal SSH-kill.**
     `AnimationRunner._kill()` sendte SIGINT til den *lokale*
     SSH-clients pgroup. Lokal ssh døde med det samme, men
     remote `animation_player_node` på Jetson'en hørte aldrig
     signalet: når sshd registrerer at SSH-kanalen er lukket,
     sendes SIGHUP til den remote bash-shell, og bash sender
     videre til sine børn — men `rclpy` registrerer kun en
     `SIGINT`-handler, så SIGHUP blev ignoreret. Animationen
     kørte dermed til CSV'ens slutning (op til 60 sek), og hvis
     brugeren klikkede en ny animation imens, kom der to
     `animation_player_node`-instanser som hver publicerede
     `/cmd_position` til samme servoer. Servo-managernoden tog
     bare den seneste besked → wild oscillation.
  2. **Tkinter event-loop blev kvalt af log-spam.** Hver
     output-linje fra remote subprocess blev skedulet som sin
     egen `self.after(0, _append_log)`. `animation_player_node`
     + `ros2`-launch-noise emitterer nemt 50-100 linjer/sek. Hver
     `_append_log` lavede `tab.insert("end", line)` +
     `tab.see("end")` på *to* `ScrolledText`-widgets (fanen +
     "Alle"-fanen) — hver insert udløser scrollbar-recompute og
     re-render. Bruger-clicks havner som tk-events i samme
     event-queue og blev FIFO-processeret *bag* alle de pending
     log-callbacks, hvilket gav perceived UI-lag på ti-sekund-
     skalaen.
  3. **`pkill`-fallback fandtes slet ikke.** Hvis (1) eller (2)
     fejlede var der ingen recovery — animationen var bare i
     gang, og hverken Stop eller relauncher hjalp.
- *Løsning:* Tre samtidige rettelser i `launcher_gui_node.py`
  (commit `88a66e3`):
  - Remote command bruger nu `… && exec ros2 run …` så remote
    bash *erstattes* af `ros2`-processen. Når SSH-kanalen
    lukker rammer SIGHUP `rclpy` direkte (Python's default
    SIGHUP-handler er `terminate`), og `animation_player_node`
    dør på milisekund-skalaen.
  - `stop()` og `play()` (ved switch) sender desuden et
    fire-and-forget `pkill -INT -f animation_player_node` over
    SSH. Det genbruger den eksisterende `ControlMaster`-socket
    så det er <100 ms, og det fungerer som belt-and-suspenders
    hvis SIGHUP-propageringen alligevel skulle svigte.
  - Log-pipelinen bruger nu en thread-safe `deque(maxlen=5000)`
    + `self.after(50, _flush_log_queue)` periodic flush. Op til
    200 linjer pr. flush, grupperes pr. tab og indsættes som ÉN
    string via `"\n".join(lines)`. Tk-event-loopet er nu ledig
    >95 % af tiden uanset hvor meget remote-processen logger,
    og clicks reagerer øjeblikkeligt.
- *Hvorfor det aldrig blev fanget tidligere:* I unit-test- og
  desktop-kontekst kører subprocesser lokalt og signaler
  propagerer "som forventet". Bug'en kræver nøjagtigt vores
  topologi: `local-shell → ssh-client → sshd-på-remote → bash
  → ros2-python`. Hver led i kæden har sine egne signal-regler,
  og det er kun den *fulde* kæde der eksponerer at SIGINT-på-
  lokal-ssh ikke når frem til remote rclpy.
- *Forkastede alternativer:*
  - **(i) Brug `ros2 lifecycle`** til at managere
    animation_player som en lifecycle-node. Korrekt langsigtet,
    men kræver refaktorering af noden, og lifecycle-services
    har deres egne ~100 ms-overhead pr. transition.
  - **(ii) Drop `-tt` (ingen pty).** Uden pty propagerer SIGHUP
    bedre. Men `-tt` er nødvendig for at få interaktive
    Python-noder til at skrive til stdout uden line-buffering,
    og uden det vises log'en kun ved exit.
  - **(iii) Lokal proces-pool i stedet for SSH pr. animation.**
    Ville kræve at vi vedligeholder en remote-side daemon der
    accepterer kommandoer — meget mere infrastruktur end
    `pkill`-trick'et tilfører.
- *Lessons learned for rapport:* Klassisk system-arkitektur-
  bug: enkeltkomponenter er korrekte, men *integrationen*
  fejler fordi to abstraktioner (signaler, line-buffering)
  kolliderer. UI-thread-prioritering er en anden fælde der
  især hitter "skriv-én-linje-pr-event"-implementeringer; den
  korrekte default i en log-tung GUI er altid: buffer +
  periodic flush + group inserts. Begge problemer var
  diagnosticerbare ved at rationalisere fra symptomet ("hvad
  *kunne* der bruge 30 sek?") frem for at gætte fixes.

**Bug 8 — `wattson_servo_manager_node.py` syntactically broken siden commit `2ea1b48`; Jetson kørte cached install (commit `29ca1a5`).**
- *Symptom:* Brugeren rapporterede at statiske 1-frame poser
  (`pose_peace`, `pose_handshake`, `pose_kungfu`, `pose_rocknroll`)
  "stopper halvvejs og fortsætter så til slut position" når de
  afspilles via launcher-GUI'en. Diagnosen var i første omgang en
  hypotese om CSV-looping (Bug 9), men brugeren pushede tilbage:
  *"selv dem som er statiske … er du sikker på vi snakker om det
  samme?"* — og det var en helt korrekt indvending. Et 1-frame CSV
  kan IKKE producere stutter via looping (hvert "frame" er identisk).
- *Diagnose:* Da jeg dykkede ned i `pkgs_control/servo_control/.../
  wattson_servo_manager_node.py` for at se efter trajectory-
  smoothing eller delta-limit-logik fandt jeg at filen var
  **syntactically invalid Python**. To metoder var sammenfletet
  ovenpå hinanden:
  ```python
  self.servo_driver_hands.command_servos(self.servo
  self._publish_power([self.servo_driver_hands])_commands_hands)
  ```
  Og `_publish_power`-metodens body var embedded inde i
  `_publish_feedback`'s slutning (`np.deg2rad(positi` truncated, og
  `ons_deg))` "uddrev" fra slutningen af _publish_power's body).
  `python3 -c "import ast; ast.parse(open('wattson_servo_manager_node.py').read())"`
  rapporterede `SyntaxError: invalid syntax` på linje 193.
  
  Git blame viste at corruption blev indført i commit `2ea1b48`
  ("power_monitor: per-servo voltage/current/power telemetry +
  live viewer") — en af mine egne tidligere commits. En
  `multi_replace_string_in_file`-operation havde matchet et
  ikke-unikt mønster og injicerede den nye linje ind i argument-
  listen til `command_servos(...)` i stedet for som en separat
  efterfølgende statement. Den lille editor-fejl havde altså været
  ubemærket i ~en uge, og *hver* `colcon build --packages-select
  servo_control` siden den dato havde fejlet stille — colcon
  rapporterer SyntaxError fra `setuptools install` med exit-code
  != 0 men output blev typisk drowned i andre build-meddelelser.
  
  Jetson'ens `~/energinet/install/servo_control/` lå derfor
  uændret siden før commit `2ea1b48`. Det betyder at **alle bug-
  fixes vi har troet vi havde deployeret de sidste dage** ikke
  faktisk var aktive på robotten — Jetson'en kørte en
  ~uge-gammel binær.
- *Fix (commit `29ca1a5`):* Rekonstrueret `callback_timer_hands`
  så `command_servos(self.servo_commands_hands)` står på sin egen
  linje, fulgt af `self._publish_feedback(...)` og
  `self._publish_power(...)` som separate kald. Rekonstrueret
  `_publish_feedback` til at slutte med korrekt
  `msg.position = list(np.deg2rad(positions_deg))` +
  `self.pub_joints_feedback.publish(msg)`. Flyttet
  `_publish_power` ud som en egen separat metode.
- *Hvorfor det blev fundet sent:* Lokalt test-build af `arm_commissioning`
  fungerer fordi den pakke ikke importerer `servo_control`. Lokal
  workflow ramte aldrig `colcon build servo_control`. Test-mappen
  for `servo_control` bruger flake8 som test-runner, men
  `setup.py`'s entry_point evalueres ved install-time *før* pytest
  kører, og Jetson-builden var den eneste sti hvor problemet ville
  manifestere sig som en byggefejl. Det er en klassisk
  "monorepo-pakke-isolation"-fælde.
- *Sekundærfund:* `power_monitor`-servicen i launcher_gui var i
  praksis en no-op siden samme dato. `_publish_power(...)` blev
  aldrig kaldt på hand-driver, og `_publish_feedback(...)` returnerede
  uden at publishe (truncated kald). Brugeren har ikke aktivt
  brugt power-monitoreringen, så det blev ikke fanget — dvs. den
  manglede integrationsverifikation der ville have ringet en
  alarm-klokke.
- *Lessons learned for rapport:* Klassisk eksempel på
  "edit-tools have failure modes too": `multi_replace`-operationer
  baserer sig på regex/literal-match og kan fejle på subtile måder
  hvis matchet ikke er præcist unikt. To beskytter:
  (a) **build-verifikation efter hver multi-edit, ikke bare lokal
  syntaks-check** — colcon-build på den faktiske target-platform
  ville have eksponeret problemet samme dag,
  (b) **Jetson skal bruge en build-pipeline der fejler højlydt
  ved compile errors** — i øjeblikket bygger den interaktivt over
  SSH, så fejl drukner i terminal-output. En lille commit-hook
  eller CI-job der bygger på en standard ARM-runner ville have
  fanget det. Begge er strukturelle læringspunkter der retfærdigvis
  hører til i rapportens "kontinuerlig integration"-afsnit.
- *Konsekvens for tidligere bug-fixes:* Bug 6 (password-prompts) og
  Bug 7 (animation respons-lag) som vi har troet var verificeret
  på Jetson, var det ikke for `servo_control`-relaterede stier.
  Animationskommandoerne nåede frem til Jetson korrekt (det er
  `animation_player`-pakken der faktisk byggede), men
  servo-driveren der modtog dem var en gammel binær. Efter denne
  fix er hele kæden first time live på robotten i ca. en uge.

**Bug 9 — `csv_reader.get_next_row()` looper uendeligt; ingen "play once"-mode (commit `29ca1a5`).**
- *Symptom — del A:* Trajectory-animationer (`gesture_wave` 90
  frames, `mimic_alexander` 850 frames) "stutter" når de afspilles
  via GUI'en — lige før de når deres slut-pose ser man bevægelsen
  hoppe baglæns mod start, og så starter den forfra mod slut igen.
  *Symptom — del B:* Animationer der intuitivt burde være "kør én
  gang og bliv stående" (de fleste poser/sekvenser) blev aldrig
  færdige — `animation_player_node` blev ved med at publicere
  joint-states forever og kunne kun stoppes med Stop-knappen.
- *Diagnose:* `pkgs_control/animation_player/.../src/csv_reader.py`
  havde en `get_next_row` der ved `StopIteration` recursivt kaldte
  `reset_iterator()` + `get_next_row()`. Der fandtes ingen
  loop-flag, så afspillerens **eneste mode var uendelig looping**.
  Dette var dokumenteret implicit som "End of file, optional: loop
  or stop"-kommentar i `animation_player_node.callback_timer`,
  hvor en TODO-tagende `if row_data is None: return` aldrig kunne
  fyre fordi `get_next_row` aldrig returnerede `None`.
  
  For trajectory-CSV'er (gesture_wave, mimic_alexander) gav det
  præcist det observerede stutter: sidste frame indeholder fx 60°
  arm-position, frame 0 indeholder 0°. Når CSV'en wrapper, sender
  animation_player_node pludselig 0°. Servo-driveren udfører den
  store delta som en aggressiv tilbage-bevægelse, og når næste
  loop-cyklus starter er servoen midt i den tilbagevej. Det ligner
  fra bruger-perspektiv et "robot snapper baglæns og fortsætter".
  
  For 1-frame statiske poser var symptomet ikke fra looping
  (samme frame hver iteration); det viste sig at være Bug 8.
- *Fix:*
  1. `csv_reader.CSVReader.__init__` tager nu en `loop`-parameter
     (default `True` for legacy bagudkompatibilitet med eksterne
     kaldere).
  2. `get_next_row` returnerer `None` ved EOF når `loop=False`,
     i stedet for at recurse.
  3. `animation_player_node` declarerer `loop`-parameter (default
     `False` — "play once" er den intuitive default for "kør denne
     animation nu"). Konstrueret CSVReader med samme flag.
  4. I `callback_timer` ved `row_data is None`: cancel timeren,
     log `"animation completed"`, kald `rclpy.shutdown()` så
     `main()`'s `spin()` returnerer og processen afslutter
     pent (exit=0).
  5. I launcher-GUI'en udvidet `ANIMATIONS`-listen med en eksplicit
     `loop`-bool pr. animation. Bevidste valg:
     - `idle1` + alle gestures (`gesture_yes/no/shrug/wave`) →
       `loop=True`. Disse skal blive ved indtil bruger trykker stop
       (idle skal være evig; en vinkende robot der efter 3 sek
       siger "okay, jeg er færdig" er forkert affordance).
     - Statiske poser (`pose_peace/handshake/rocknroll/kungfu`) →
       `loop=False`. Disse er destinations, ikke loops.
     - Sekvenser (`mimic_alexander`, `mimic_optimus`,
       `animation_fingerguns`, `animation_headbang`) → `loop=False`.
       En sekvens har en naturlig slutning; loop ville bryde
       narrativet.
     - Test/recording → `loop=False`. Diagnostik kører én gang.
   6. Loop-animationer markeres med `↻`-glyph i knap-teksten så
      brugeren visuelt ser hvilke der vil køre forever.
- *Forkastede alternativer:*
  - **(i) Hardkode "play once" som eneste mode.** Brugeren
    indvendte eksplicit at noget *skal* loope (vinkende robot).
    Pareto-optimal default afhænger af animationen, ikke af
    afspilningssystemet.
  - **(ii) En `--num-loops N`-parameter i stedet for boolean.**
    Mere fleksibelt, men ingen af vores faktiske animationer har
    brug for "afspil 3 gange og stop". Komplexiteten er ikke
    berettiget.
  - **(iii) Loop-control via en runtime ROS-service.** Ville lade
    bruger toggle loop mens animationen kører, men den eneste
    use-case ville være "lad mig stoppe nu, men færdiggør den
    nuværende cyklus først" — som er en akademisk feature for et
    demo-system. Stop-knappen er god nok.
- *Lessons learned for rapport:* En interessant observation er at
  Bug 8 og Bug 9 var **fundet via samme symptomrapport** — bruger
  rapporterede "stutter mid-animation". Min første hypotese var
  Bug 9 (looping), men brugerens skarpe pushback (*"selv dem som
  er statiske…"*) tvang mig til at grave dybere, hvilket
  eksponerede Bug 8 (corrupt source). Det understøtter et generelt
  punkt om at *brugerens evne til at udfordre en for-tidlig
  diagnose er en kritisk del af debugging-loopet*. Hvis brugeren
  havde accepteret Bug 9 som den hele forklaring, ville Bug 8
  forblive skjult og videregivet til næste udviklergeneration.

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
