# Hardware-opsætning af ny Jetson Orin Nano + ESP32-bokse

Denne procedure tager en frisk Orin Nano og tre nye ESP32-moduler fra "lige
ud af pakken" til "kører den eksisterende workspace identisk med det gamle
system". Materialet i denne mappe (`scripts/setup/`) automatiserer alt det
der kan automatiseres; resten er manuelle skridt der enten kræver en
host-PC, en interaktiv download eller fysisk arbejde.

## Forudsætninger

- En **Jetson Orin Nano Developer Kit** (8\,GB) med tom SD-kort eller eMMC
- En **host-PC med Ubuntu** og NVIDIA SDK Manager installeret (til JetPack-flashing)
- Tre **nye ESP32-moduler** af samme type som de eksisterende
- En **eksisterende, virkende ESP32** at klone firmwaren fra
- USB-A-til-micro-USB- eller USB-C-kabel afhængigt af ESP32-varianten
- Internetforbindelse på Jetson under setup

## Trin 1 — Flash JetPack 6.x på Jetson

Kør **NVIDIA SDK Manager** på host-PC'en og flash JetPack 6.x (Ubuntu 22.04
L4T 36.x). Følg SDK Managers guidede flow:

1. Sæt Orin Nano i recovery mode (jumper på REC-pin, så strøm)
2. Tilslut USB-C til host-PC
3. Vælg target = Jetson Orin Nano, OS = Ubuntu 22.04
4. Lad SDK Manager flash'e (~20\,min)

Når Jetson booter første gang, opret bruger (foreslår `elrik` for at matche
det eksisterende setup), sæt password, accepter OEM-konfigurationen.

## Trin 2 — Kør automatisk post-flash-setup

Log ind på Jetson, klon dette repo, og kør setup-scriptet:

```bash
sudo apt-get update && sudo apt-get install -y git
mkdir -p ~/humanoid_ws/src && cd ~/humanoid_ws/src
git clone --branch alex/min-opgave \
    https://github.com/dk-teknologisk-ALMC/energirobotter-ros-workspace-alex.git
cd energirobotter-ros-workspace-alex
chmod +x scripts/setup/setup-orin-nano.sh
./scripts/setup/setup-orin-nano.sh
```

Scriptet er idempotent — det kan køres igen uden bivirkninger.

Det tager sig af:
- ROS 2 Humble-installation
- Tilføjelse til `dialout`-gruppen
- `rosdep`-initialisering og opdatering
- Klone af workspace + `trac_ik`
- Python-deps fra `requirements.txt`
- Chrony til NTP-tidsync
- `colcon build` af workspace
- Verifikation af `/dev/serial/by-path/`-stier matcher hardkodede stier i koden

## Trin 3 — Manuelle skridt efter scriptet

Scriptet udskriver disse skridt i slutningen, men her er de samlet:

### 3.1 Log ud og ind igen

`dialout`-gruppe-ændringen træder først i kraft efter en ny login.

### 3.2 Tilføj shell-aliaser

Append til `~/.bashrc`:

```bash
alias shumble='source /opt/ros/humble/setup.bash'
alias sw='source ~/humanoid_ws/install/setup.bash'
```

### 3.3 Statisk IP til 192.168.1.105

Vælg én strategi:

**A — Statisk IP via netplan** (Jetson selv styrer)

```bash
sudo tee /etc/netplan/99-elrik.yaml >/dev/null <<'EOF'
network:
  version: 2
  ethernets:
    eth0:
      addresses: [192.168.1.105/24]
      routes:
        - to: default
          via: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 1.1.1.1]
EOF
sudo chmod 600 /etc/netplan/99-elrik.yaml
sudo netplan apply
```

**B — DHCP-reservation** (router/laptop-DHCP styrer)

Find Jetsons MAC: `ip link show eth0 | awk '/ether/ {print $2}'`

Reserve den MAC til 192.168.1.105 i din router, eller tilføj
`--dhcp-host=<MAC>,192.168.1.105,elrik-jetson` til den eksisterende
`dnsmasq`-konfiguration på laptoppen.

### 3.4 Kopier SSH-nøgle fra laptop

Fra **laptoppen** (ikke Jetson):

```bash
ssh-copy-id elrik@192.168.1.105
```

### 3.5 ZED SDK + ZED ROS 2 wrapper

Følg sektionerne **ZED SDK** og **ZED ROS 2 Wrapper** i workspace
[README.md](../../README.md). Dette kræver en interaktiv `.run`-download fra
Stereolabs som ikke kan automatiseres.

### 3.6 AI-model

Download `yolov8n-face.pt` fra
<https://github.com/akanametov/yolov8-face/releases/tag/v0.0.0> og placer i
`pkgs_vision/face_detection/models/`. Beskrevet i README.md afsnit
"AI model".

## Trin 4 — Klon ESP32-firmwaren

Med en kendt-god ESP32 tilsluttet `/dev/ttyUSB0` på laptoppen:

```bash
cd ~/humanoid_ws/src/energirobotter-ros-workspace-alex/scripts/setup
chmod +x clone-esp32.sh
./clone-esp32.sh read /dev/ttyUSB0
```

Det producerer `esp32_firmware_clone.bin` i nuværende mappe.

For hver ny ESP32, tilslut den én ad gangen og kør:

```bash
./clone-esp32.sh write /dev/ttyUSB0
./clone-esp32.sh verify /dev/ttyUSB0
```

Power-cycle den nye ESP32 og verificer at den booter normalt (LED-mønster
matcher den gamle).

## Trin 5 — Fysisk mærkning

For hvert servobus-bridge-modul:

| Gruppe | Kabelfarve | ESP32 | Servo-ID-range |
|---|---|---|---|
| Venstre arm | Rød | 1 stk. | 1-7 |
| Højre arm + hoved | Gul | 1 stk. | 1-7 (arm) + 8, 9 (hoved) |
| Begge hænder | Hvid | 1 stk. | 1-5 (pr. hånd) |

Mærk hvert ESP32-modul med et stykke farvet tape eller en clip-on-label
matchende ovenstående. På Jetsons fysiske USB-block: Rød skal i port 2.2,
Gul i 2.3, Hvid i 2.1.

## Trin 6 — Slut-verifikation

På Jetson:

```bash
shumble
sw
ros2 launch energirobotter_bringup servos.launch.py
```

Bekræft at alle led når deres `default_position` uden fejl, og at
manager-noden ikke logger "could not open port"-fejl. Hvis den gør, tjek:

1. Er ESP32-bokse plugget i de rigtige farvede USB-porte?
2. `ls /dev/serial/by-path/` — er alle tre `platform-3610000.usb-...:2.{1,2,3}:1.0-port0`-stier til stede?
3. Er brugeren i `dialout`-gruppen? (`groups | grep dialout`)
4. Er ESP32-firmware-klonen flashet korrekt? (`./clone-esp32.sh verify <port>`)

## Fejlfinding

### `/dev/serial/by-path/`-stien har ikke prefix `platform-3610000.usb-...`

Det er sjældent på Orin Nano dev kit, men kan ske hvis NVIDIA ændrer
USB-controller-mapping i en ny JetPack-version. I så fald:

1. Find den korrekte sti: `ls -l /dev/serial/by-path/`
2. Opdater `port_path=`-strenge i
   `pkgs_control/servo_control/servo_control/wattson_servo_manager_node.py`
   linje ~95, ~107, ~120
3. Genbyg: `cd ~/humanoid_ws && colcon build --packages-select servo_control`

### `colcon build` fejler på pakke der kræver ZED SDK

Forventet hvis ZED SDK ikke er installeret. Tilføj `COLCON_IGNORE`-fil i
ZED-pakkens mappe for at springe den over, eller installer ZED SDK først
(se Trin 3.5).

### Klonet ESP32 booter ikke

1. Verificer at de to ESP32-moduler har **samme flash-størrelse**
   (`./clone-esp32.sh` afviser hvis ikke)
2. Verificer at de er **samme chip-revision**
   (`esptool.py --port /dev/ttyUSB0 chip_id`)
3. Hvis chippene er forskellige (fx ESP32 vs ESP32-S3) er bit-for-bit-klon
   ikke en option — du skal have firmware-kildekoden og rebuild'e for den
   nye chip. Spørg den der oprindeligt udviklede firmwaren.

---

**Sidst opdateret:** 15. juni 2026.
