# Eksamens-oplæg (15 min)

Disposition og talepunkter til min eksamens-præsentation. Tidsbudget
nederst.

> Mål: vise hvad jeg har lavet, hvorfor jeg har valgt det jeg har
> valgt, og at jeg forstår systemet — ikke at gennemgå hver linje kode.

---

## 1. Intro — Teknologisk Institut (≈ 1 min)

- Hvor jeg har været i praktik og hvilken afdeling (robotteknologi).
- Kort rids: hvad laver afdelingen, hvilken type opgaver.
- Hvad min rolle har været i projektet (egen branch `alex/min-opgave`,
  fokus på idriftsættelse/commissioning af én arm + opsætnings-
  automation).

**Backup-slide:** logo + et billede fra værkstedet hvis jeg har et.

---

## 2. Kort intro til robotten (≈ 1 min)

- Open source humanoid bygget af Energi Robotter / "Elrik"-familien.
- Form-faktor: torso + to arme + to hænder + hoved (ZED 2 + servo
  pan/tilt). Ikke benene.
- Formål i projektet: platform til teleoperation og animations-
  afspilning.
- Vis robotten live hvis den er klar, ellers ét billede.

**Sætning der binder:**
> "Den er bygget åbent og modulært — så jeg har kunnet skille
> idriftsættelse af én arm ud i sin egen pakke uden at røre resten."

---

## 3. Komponenter (≈ 1.5 min)

Gå hurtigt gennem de fire fysiske dele uden at gå i detaljer
(detaljer kommer i pkt. 5 og 6):

- **Jetson Orin Nano** på robotten — kører ROS 2 Humble, hoster servo-
  drivere og kinematik.
- **Laptop** — udvikling, GUI, Quest 3 bridge.
- **ESP32 bus-bridges** (3 stk) — USB ↔ TTL half-duplex til servo-bus.
- **Servoer**: ST3215 (12-bit) i arme/hoved, SC09 (10-bit) i fingre.
- **Sensorer**: ZED 2 stereokamera, Quest 3 headset (hånd-tracking).

**Vis evt.:** simpel boks-tegning af forbindelser (Jetson → 3× ESP32 →
servo-bus). Kan tegnes på tavlen.

---

## 4. GUI — `launcher_gui` (≈ 2.5 min)

Det visuelle anker i præsentationen. Åbn det live.

**Hvad det er:**
Tkinter-baseret kontrolpanel der starter hele stakken fra ét vindue
(ZED, servoer, animationer, demo-noder).

**Hvorfor jeg lavede det:**
- Før: 6–8 terminaler skulle åbnes manuelt, hver med sin
  `source install/setup.bash` og sin `ros2 launch ...`. Stort
  fejl-areal, dårlig demo-oplevelse.
- ESP32-portene må sidde i samme USB-stik hver gang. GUI'en
  verificerer `/dev/serial/by-path/...` symlinks ved opstart.
- Animationer skulle startes med præcis kommandolinje hver gang —
  nu er det 18 knapper.
- Password-prompts for `sudo`-services skulle samles ét sted →
  zenity ASKPASS.

**Hvad jeg viser i demoen:**
1. Klik "Bringup" → servoer + ZED starter, log dukker op i fanen.
2. Klik en animation → robotten bevæger sig.
3. Manuel slider-fane → finger-test direkte fra GUI.

**Ærligt:** Det er en intern udviklings-GUI, ikke et produkt. Det er
markeret "Demo Launcher".

---

## 5. Servo-opsætning + værktøjer (≈ 2.5 min)

Her ligger min hovedbidrag (`arm_commissioning`-pakken).

**Problemet:**
Hver servo skal kalibreres: hvad er den fysiske min-vinkel, max-vinkel,
default-position. Hvis det er forkert, kører servoen ind i sig selv
eller starter i underlig stilling.

**Mit værktøj `calibration_tool_node`:**
- Interaktivt tastatur-værktøj (pile = bevæg, `n` = næste servo,
  `s` = sæt min, `S` = sæt max, `d` = sæt default).
- Skriver direkte i JSON-config og laver tidsstemplet backup.
- Kan køres pr. servo eller hele konfigurationsfilen igennem.

**Vis i demoen:**
- Åbn `wattson_description/servo_configs/servo_arm_left_params.json`
  så de ser hvad jeg arbejder med.
- Kør én kalibrerings-iteration på én servo (max 30 sek).

**Tre WIP-test-værktøjer i samme pakke** (nævn kort, demonstrer ikke):
- `step_response_node` — rise time / overshoot / settling time.
- `repeatability_node` — spredning over N cyklusser.
- `power_monitor_node` — strømforbrug pr. servo over tid.

**Sætning:** "Næste step er at gøre disse tre færdige så vi har
objektive før/efter-tal når vi justerer mekanik eller PID."

---

## 6. Jetson-opsætning + faste USB-porte (≈ 2 min)

**Problemet:**
Når man flasher JetPack på en ny Orin Nano, er der ~30 manuelle skridt
før robotten kører. Nem at glemme noget. Og `/dev/ttyUSB0/1/2` skifter
rækkefølge — så arme får hånd-firmware ved næste boot.

**Min løsning:**
- `scripts/setup/setup-orin-nano.sh` — idempotent script der
  installerer ROS 2, sætter dialout-gruppe, kører `rosdep install`,
  laver første colcon build, og verificerer `by-path`-symlinks.
- `scripts/setup/HARDWARE_SETUP.md` — komplet trin-for-trin guide
  som backup hvis scriptet fejler eller bruges manuelt.
- USB-porte navngivet med `/dev/serial/by-path/...-portN` så
  hardware-position dikterer software-navn — ikke boot-rækkefølge.
- `scripts/setup/clone-esp32.sh` — `esptool`-wrapper til read/write/
  verify så vi kan klone en kendt-god ESP32 til en ny.

**Sætning:** "Det betyder at hvis Jetson dør, kan vi flashe en ny og
være tilbage i drift på en eftermiddag i stedet for en uge."

---

## 7. Udfordringer (≈ 1.5 min)

Vælg 2–3 reelle, ikke alt sammen. Forslag:

**A. To kopier af servo-configs.**
Der lå `servo_*_params.json` to steder
(`energirobotter_bringup/config/servos/` og
`wattson_description/servo_configs/`). Kun den ene blev brugt — jeg
brugte timer på at redigere den forkerte før jeg fandt ud af det.
Læring: følg `ros2 launch ... --show-args` og læs hvad der faktisk
loades.

**B. USB-port-rotation.**
`/dev/ttyUSB0/1/2` skiftede rækkefølge ved reboot. Servoer fik
firmware-mismatch og bussen hang. Løsning: `/dev/serial/by-path/`.

**C. Animation-loop hang i 30–60 sek.**
`launcher_gui` ventede på at en CSV-fil var afspillet helt færdig før
brugeren kunne klikke "stop". Fix: separat loop-flag og kortere
poll-interval (commit `88a66e3`).

**D. Servo bus-throughput.**
Da `wattson_servo_manager` udsendte `voltage`/`current`/`power` i
control-loopet, blev bussen overbelastet og positions-kommandoer kom
for sent. Løsning: splittet telemetry ud i sin egen lavere-rate timer
(commit `9e5e4da`).

Vælg dem der passer bedst til hvad censor spørger om — alle står i
`REPORT_NOTES.md`.

---

## 8. Afslutning (≈ 0.5 min)

- Hvad fungerer: kalibrering, basic teleop, animationer, GUI.
- Hvad er WIP: step_response, repeatability, power_monitor (tre test-
  noder klar i kode, men ikke verificerede mod baseline).
- Næste skridt: færdiggør test-noderne så vi kan citere tal i en
  rapport, og kør baseline-måling før første eksterne demo.
- Hvad jeg har lært: ROS 2 i praksis, idriftsættelse af serielle
  servo-busser, automation af setup, hvordan man holder hardware-
  config konsistent.

**Sidste sætning:** "Hele projektet ligger på branchen
`alex/min-opgave`, og BIDRAG.md viser præcist hvad jeg har tilføjet."

---

## 9. Spørgsmål (≈ 3 min)

Sandsynlige spørgsmål — forbered korte svar:

**"Hvorfor ROS 2 og ikke bare en monolitisk Python-proces?"**
Decoupling, sprog-agnostisk, "gratis" værktøjer (`ros2 topic echo`,
`foxglove`, `ros2 bag`), distribueret over LAN uden netværkskode.

**"Hvad er forskellen på en ROS-pakke og en Docker-container?"**
ROS-pakke = mappe med `package.xml` der bygges af colcon ind i samme
Linux-system. Docker = indkapslet OS-image. Vi bruger ikke Docker.

**"Hvad sker der hvis Quest 3 mister tracking?"**
IK-noden får ikke nye target-frames, så `wattson_servo_manager` får
ikke nye `JointState`-beskeder, og armen står stille i sidste
kommanderede position.

**"Hvad er din rolle vs den oprindelige forfatter?"**
Pege på `BIDRAG.md`. Min hovedbidrag: `arm_commissioning`-pakken og
hardware-setup-automation.

**"Hvad er en god næste opgave?"**
Færdiggør WIP test-noder, automatisér baseline-måling, kør
regression-test før hver merge.

---

## 10. Dybde-baggrund (hvis de borer ned)

Det her er emner hvor jeg let kan blive fanget i et tomt svar. Læres
udenad så jeg kan svare i hele sætninger uden at famle.

### 10.1 Tkinter

**Hvad er det?**
Tkinter er Python's indbyggede GUI-bibliotek. Det er en tynd Python-
wrapper rundt om Tcl/Tk, et grafik-toolkit fra starten af 90'erne der
stadig vedligeholdes. Det følger med i standard CPython, så jeg
behøver ingen `pip install` — det er der bare. Derfor virker
`launcher_gui` på en frisk Jetson uden ekstra dependencies.

**Hvordan er det struktureret?**
Et Tkinter-program har én *root window* (`Tk()`), og man putter
*widgets* ind i den (knapper, labels, frames, tabs, text-bokse).
Layout sker enten med `pack()`, `grid()` eller `place()`. Vi bruger
`grid()` til at få knapperne på linje.

**Event loop.**
Tkinter er event-drevet — du starter `root.mainloop()`, og GUI'en
sidder og venter på events (klik, tastetryk, timer). Når brugeren
klikker en knap, kalder Tk det callback du har bundet på. Det betyder
**du må ikke blokere mainloop** — hvis du f.eks. starter et `ros2
launch` synkront, fryser GUI'en indtil launchet slutter.

**Hvordan løser jeg blokerings-problemet?**
Hver knap der starter en lang-løbende kommando spawner i stedet en
`subprocess.Popen(...)` (ikke `subprocess.run`). Stdout/stderr piped
til en `queue.Queue`, og en `root.after(100, drain_queue)` callback
trækker linjer ud af køen og skriver dem i log-fanen. Det er
*non-blocking* fordi `Popen` returnerer med det samme og processen
kører i baggrunden.

**Hvorfor Tkinter og ikke noget pænere (Qt, web, Electron)?**
- Zero dependencies — fungerer på et frisk JetPack-image.
- Det er et udviklings-værktøj til mig selv og kolleger, ikke et
  produkt — udseendet betyder ikke noget.
- Hurtigt at iterere på. Hver ny knap er ~5 linjer kode.
- Hvis det skulle blive et "produkt" engang, ville jeg skifte til
  en web-baseret GUI (Flask + Vue) så det også kan tilgås
  fra laptoppen uden at have X11 forwarding.

**Mulige opfølgnings-spørgsmål:**

*"Bruger du threads?"* — Nej, ikke direkte. Jeg bruger `subprocess.
Popen` + `root.after` polling. Det giver samme effekt uden GIL-
hovedpine.

*"Hvordan lukker du subprocesser pænt?"* — Ved exit kører jeg
`Popen.terminate()` på hver service. For root-ejede services bruger
jeg `pkexec` / `sudo kill` (commit `1964712` fixede en hang her).

### 10.2 "Idempotent" — hvad betyder det helt præcist?

**Definition:**
Et script (eller en operation generelt) er *idempotent* hvis det
giver samme slutresultat uanset hvor mange gange man kører det.
Anden gang skal ikke ødelægge noget der virkede første gang.

**Kontrast (ikke-idempotent):**
- `echo "elrik 192.168.1.105" >> /etc/hosts` kører to gange =
  to identiske linjer, hvilket er rod.
- `adduser elrik` kører to gange = fejl anden gang.

**Sådan gør `setup-orin-nano.sh` det idempotent:**
- `apt install -y` springer pakker over der allerede er der.
- Linjer der tilføjes til config-filer wrappes i `grep -qF "linje"
  /etc/file || echo "linje" >> /etc/file` — kun hvis den ikke
  findes i forvejen.
- `usermod -aG dialout $USER` er allerede idempotent (Linux melder
  bare "already in group").
- `colcon build` er naturligt idempotent — den genbygger kun det
  der er ændret.
- Symlinks oprettes med `ln -sfn` (force + no-deref) i stedet for
  `ln -s` som fejler hvis target findes.

**Hvorfor er det vigtigt?**
- Jeg kan stoppe scriptet halvvejs (Ctrl+C, strømsvigt) og bare køre
  det igen.
- Hvis et trin fejler kan jeg fixe det og køre igen uden at skulle
  starte fra en frisk JetPack-flash.
- Det er en grundlæggende egenskab i Ansible, Terraform osv. — så
  jeg viser at jeg kender konceptet.

**Hvis de spørger om Ansible:** Idempotens er hele kernen i
Ansible — hvert "modul" garanterer at slutresultatet er det samme
uanset start-tilstand. Mit shell-script er en simplere udgave af
samme idé.

### 10.3 Faste USB-porte via `/dev/serial/by-path/`

**Problemet i detaljer:**
Linux opdager USB-enheder i den rækkefølge kernen ser dem under
boot. To genstarter senere kan ESP32 der før var `ttyUSB0` nu være
`ttyUSB2`. Det er race-condition-styret og ikke noget brugeren kan
styre.

**Hvad `/dev/serial/by-path/` er:**
Udev (Linux's device-manager) opretter automatisk en mappe under
`/dev/serial/by-path/` med symlinks navngivet efter den *fysiske
position* i USB-træet. Eksempel:

```
/dev/serial/by-path/platform-3610000.xhci-usb-0:2.1:1.0-port0
```

Det her betyder cirka: "host-controlleren ved `3610000.xhci`, hub-
port 2 underport 1, USB-interface 0, serial-port 0". Symlinket
peger på `/dev/ttyUSB<noget>`, men selve navnet **ændrer sig
aldrig** så længe man bruger samme fysiske USB-stik.

**Hvorfor by-path og ikke by-id?**
- `by-id` bruger USB-deskriptorernes VID/PID + serial-nummer. Alle
  vores tre ESP32-boards har **samme** VID/PID (CP2102) og ofte
  også samme serial-nummer fra fabrikken. Så `by-id` ville give
  tre symlinks der peger på samme stub.
- `by-path` er låst til hardware-positionen, så jeg kan have tre
  identiske ESP32 og stadig skelne dem — så længe arme-stikket
  altid sidder i det samme USB-A-stik på Jetson.

**Hvordan jeg bruger det i koden:**
I `wattson_servo_manager_node` er servoport-parameteren ændret fra
`/dev/ttyUSB0` til den fulde by-path-streng. Når jeg setup'er en
ny Jetson, kører jeg `ls -la /dev/serial/by-path/` og kopierer
de tre paths ind i launch-config'en.

**Mulige opfølgnings-spørgsmål:**

*"Hvad er udev?"* — Linux's device-manager. Den lytter på kernel-
events (USB tilsluttet/frakoblet) og opretter device-noder i
`/dev/`. Den læser regler fra `/etc/udev/rules.d/` og kan også
udløse scripts.

*"Hvad er en symlink?"* — En "symbolsk link" — en fil der peger på
en anden fil. Når noget åbner symlinket, følger kernen pilen og
åbner target. `ls -la` viser pil-notation:
`by-path/xxx -> ../../ttyUSB0`.

### 10.4 Servo-bits, raw ticks og PID

**Hvad betyder "12-bit servo"?**
ST3215 har en intern position-encoder med 12-bit opløsning, dvs.
$2^{12} = 4096$ unikke positioner over 360°. Det giver
$360/4096 \approx 0.088°$ pr. tick. SC09 har kun 10-bit
($2^{10} = 1024$), dvs. ~$300/1024 \approx 0.29°$ pr. tick over et
mindre range.

**Rad → raw ticks:**
Vi sender ikke grader/radianer over bussen. Vi sender et tal mellem
0 og 4095 (ST3215). Konverteringen i `servo_control.py` er lineær:
hver servo har `angle_software_min`/`max` (grader) og
`raw_position_min`/`max` (ticks) i sin JSON. Mappingen er
proportional med eventuel `dir` (±1) og `offset`.

**Hvad er PID på en servo?**
ST3215 har en intern PID-controller (proportional/integral/
derivative). Jeg sender bare en target-position; servoens egen MCU
sammenligner mod den interne encoder og pulse-width-modulerer
motoren for at nå dertil. **Jeg tuner ikke selv PID'en** —
parametrene ligger i servoens firmware. Det er derfor jeg taler om
*ydre* test (step response, repeatability) frem for at tune
loopet.

### 10.5 Half-duplex servo-bus

ST3215 og SC09 bruger en seriel multidrop-bus hvor flere servoer
deler én datalinje. *Half-duplex* betyder at samme ledning bruges
til både send og modtag — kun én part må snakke ad gangen, ellers
kollision. ESP32 håndterer retning-skift via en direction-pin.
Jetson skriver via USB-serial til ESP32, ESP32 oversætter til
half-duplex med korrekt timing. Hver servo har et unikt ID (1–253)
og svarer kun når dens ID bliver adresseret.

### 10.6 Sammenfatning af "jeg ved hvad jeg taler om"-sætninger

Hvis jeg famler, fald tilbage på disse korte, præcise sætninger:

- *Tkinter:* "Python's indbyggede GUI-toolkit. Event-loop-baseret,
  så jeg starter subprocesser non-blocking via `Popen` og poller
  output via `root.after`."
- *Idempotent:* "Resultatet er det samme uanset hvor mange gange du
  kører det. Praktisk fordi jeg så kan genstarte setup midt i hvis
  noget fejler."
- *`by-path`:* "Udev-symlink baseret på fysisk USB-port, ikke på
  enhedens VID/PID. Det binder navnet til hardware-positionen."
- *12-bit:* "$2^{12} = 4096$ raw positioner over 360°."
- *Half-duplex:* "En ledning, to retninger — ESP32 styrer retning-
  skift via direction-pin."
- *PID på servoen:* "Den sidder internt i servoens MCU. Jeg sender
  kun target-position."

---

## Tidsbudget

```
 1. Intro TI                  1.0 min
 2. Robot-intro               1.0 min
 3. Komponenter               1.5 min
 4. GUI                       2.5 min
 5. Servo + værktøjer         2.5 min
 6. Jetson + USB              2.0 min
 7. Udfordringer              1.5 min
 8. Afslutning                0.5 min
 ─────────────────────────────────────
    Sum talt                 12.5 min
 9. Spørgsmål                 2.5 min
 ─────────────────────────────────────
    Total                    15.0 min
```

**Hvis jeg løber tør for tid:** spring "Komponenter" (pkt. 3) hurtigt
over — det meste fanges alligevel i pkt. 4–6.

**Hvis jeg får for meget tid:** udvid "Udfordringer" (pkt. 7) eller
"Servo-værktøjer" (pkt. 5) med en konkret bug-historie fra
REPORT_NOTES.

---

## Tjekliste lige før eksamen

- [ ] Robotten har strøm og er bootet.
- [ ] Laptop er på `192.168.1.x` og kan pinge Jetson.
- [ ] `launcher_gui` åbnes uden fejl.
- [ ] Én animation testet i forvejen samme dag.
- [ ] BIDRAG.md, ARKITEKTUR.md, EKSAMEN_OPLAEG.md åbne i hver sin
      fane.
- [ ] REPORT_NOTES.md tilgængelig (men ikke vist medmindre nødvendigt
      — det er privat arbejdslog).
