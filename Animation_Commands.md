# Animation Commands

Kopiér og indsæt i en SSH-session på Jetson (`ssh elrik@192.168.1.105`).

## Setup (kør én gang per terminal)

```bash
source /opt/ros/humble/setup.bash
source ~/energinet/install/setup.bash
ANIMS=~/energinet/src/energirobotter-ros-workspace/energirobotter_bringup/animations
```

## Stop kørende animation

```bash
pkill -f animation_player_node
```

---

## Sikre / blide

### Idle (rolig start-stilling)
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/idle1.csv -p fps:=24
```

### Gesture: Yes (nik)
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/gesture_yes.csv -p fps:=24
```

### Gesture: No (ryst på hovedet)
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/gesture_no.csv -p fps:=24
```

### Gesture: Shrug (træk på skuldrene)
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/gesture_shrug.csv -p fps:=24
```

### Gesture: Wave (vink)
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/gesture_wave.csv -p fps:=24
```

---

## Statiske positurer

### Peace
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/pose_peace.csv -p fps:=24
```

### Rock 'n' Roll
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/pose_rocknroll.csv -p fps:=24
```

### Handshake
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/pose_handshake.csv -p fps:=24
```

### Kung Fu
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/pose_kungfu.csv -p fps:=24
```

### Pose Test (debug)
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/pose_test.csv -p fps:=24
```

---

## Animationer / længere sekvenser

### Finger Guns
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/animation_fingerguns.csv -p fps:=24
```

### Headbang
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/animation_headbang.csv -p fps:=24
```

### Mimic Alexander
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/mimic_alexander.csv -p fps:=24
```

### Mimic Optimus
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/mimic_optimus.csv -p fps:=24
```

---

## Test / recordings (mest til commissioning)

### Test servos (gennemgår alle led — brug med forsigtighed)
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/test_servos.csv -p fps:=24
```

### Recording: begge arme
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/recording_arms_test.csv -p fps:=24
```

### Recording: højre arm
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/recording_right_arm_test.csv -p fps:=24
```

### Recording: højre underarm
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/recording_right_underarm_test.csv -p fps:=24
```

### Recording: højre håndled
```bash
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/recording_right_wrist_test.csv -p fps:=24
```

---

## FPS-variation

```bash
# Halvt så hurtigt (sikrere)
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/animation_headbang.csv -p fps:=12

# Dobbelt så hurtigt
ros2 run animation_player animation_player_node --ros-args -p csv_file_path:=$ANIMS/gesture_wave.csv -p fps:=48
```
