# Servo Control

PID control and communication for servo motors, over Serial or I2C through
a servo driver: a
[Waveshare driver](https://www.waveshare.com/servo-driver-with-esp32.htm),
a [PCA9685](https://www.adafruit.com/product/815), or an
[Arduino](https://www.arduino.cc/) board.

See `examples/` for usage examples. Run from the workspace root:

```
python3 src/energirobotter-ros-workspace-alex/pkgs_control/servo_control/examples/arduino_single_servo_example.py
```

## `ServoDriverWaveshare`

Driver for the
[Waveshare driver](https://www.waveshare.com/servo-driver-with-esp32.htm)
board.

| Name     | Type     | Description | Default          |
| -------- | -------- | ----------- | ---------------- |
| port     | `string` | Port name.  | `"/dev/ttyACM0"` |
| baudrate | `int`    | Baudrate    | `115200`         |

## `ServoDriverPCA9685`

Driver for the [PCA9685](https://www.adafruit.com/product/815) board.

## `ServoDriverArduino`

Driver for an [Arduino](https://www.arduino.cc/) board.

| Name     | Type     | Description                       | Default          |
| -------- | -------- | --------------------------------- | ---------------- |
| port     | `string` | Port name.                        | `"/dev/ttyACM0"` |
| baudrate | `int`    | Baudrate                          | `115200`         |
| timeout  | `float`  | Serial-communication timeout.     | `1.0`            |

## `ServoControlNode`

Node representing a single servo. Wraps the `ServoControl` class with
hardware configuration and movement logic.

| Name               | Type     | Description                                                                                                                                                                                  | Default     |
| ------------------ | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| servo_id           | `int`    | Servo id/channel on the PCA9685 board (only applicable for `driver_device:=pca9685`).                                                                                                        | `0`         |
| operation_mode     | `string` | Operation mode, similar to PPM and CSP EtherCAT operation modes. Requesting a position/angle, or sending error commands in a fixed time loop. Supported protocols are `angle` and `control`. | `"angle"`   |
| driver_device      | `string` | Driver device name. Supported devices are `arduino` and `pca9685`.                                                                                                                           | `"pca9685"` |
| control_frequency  | `float`  | Control-loop frequency.                                                                                                                                                                      | `0.05`      |
| pwm_min            | `int`    | Servo minimum PWM (16-bit).                                                                                                                                                                  | `0`         |
| pwm_max            | `int`    | Servo maximum PWM (16-bit).                                                                                                                                                                  | `4095`      |
| angle_min          | `int`    | Servo minimum position in degrees.                                                                                                                                                           | `0`         |
| angle_software_min | `int`    | Software-limited minimum angle, set by physical configuration limits.                                                                                                                        | `0`         |
| angle_max          | `int`    | Servo maximum position in degrees.                                                                                                                                                           | `180`       |
| angle_software_max | `int`    | Software-limited maximum angle, set by physical configuration limits.                                                                                                                        | `180`       |
| speed_max          | `int`    | Servo maximum speed in degrees per second.                                                                                                                                                   | `200`       |
| dir                | `int`    | Direction config for upside-down placement (-1 or 1).                                                                                                                                        | `1`         |
| gain_P             | `float`  | P gain of the PID controller.                                                                                                                                                                | `1.0`       |
| gain_I             | `float`  | I gain of the PID controller.                                                                                                                                                                | `0.0`       |
| gain_D             | `float`  | D gain of the PID controller.                                                                                                                                                                | `0.0`       |

### PWM Calculation Example

The [Tower Pro SG90 servo](http://www.ee.ic.ac.uk/pcheung/teaching/DE1_EE/stores/sg90_datasheet.pdf)
runs at `50 Hz` (PWM period `20 ms`). The minimum-angle pulse is `1 ms`
and the maximum-angle pulse is `2 ms`, i.e. PWM percent between `5%` and
`10%` for min and max position.

A 16-bit value has a maximum of 65535, so the min and max 16-bit PWM
values for this servo are `3276.75` and `6553.5` (written as ints).

## `ServoControl`

Class representing a single servo, containing hardware configuration and
movement logic. Implemented in `servo_control.py`; depends on
`servo_coms.py` in the same directory, which handles communication.

| Name               | Type     | Description                                                                         | Default          |
| ------------------ | -------- | ----------------------------------------------------------------------------------- | ---------------- |
| pwm_min            | `float`  | Servo minimum PWM (16-bit).                                                         | -                |
| pwm_max            | `float`  | Servo maximum PWM (16-bit).                                                         | -                |
| angle_min          | `float`  | Servo minimum position in degrees.                                                  | -                |
| angle_software_min | `float`  | Software-limited minimum angle, set by physical configuration limits.               | -                |
| angle_max          | `float`  | Servo maximum position in degrees.                                                  | -                |
| angle_software_max | `float`  | Software-limited maximum angle, set by physical configuration limits.               | -                |
| speed_max          | `float`  | Servo maximum speed in degrees per second.                                          | -                |
| servo_id           | `int`    | Servo id/channel on the PCA9685 board (only applicable for I2C protocol).           | `0`              |
| dir                | `int`    | Direction config for upside-down placement (-1 or 1).                               | `1`              |
| gain_P             | `float`  | P gain of the PID controller.                                                       | `1.0`            |
| gain_I             | `float`  | I gain of the PID controller.                                                       | `0.0`            |
| gain_D             | `float`  | D gain of the PID controller.                                                       | `0.0`            |
| protocol           | `string` | Communications protocol. Supported protocols are `serial` and `i2c`.                | `"serial"`       |
| port               | `string` | Port name.                                                                          | `"/dev/ttyACM0"` |

The I2C protocol requires the code to run on a board with I2C pins.

## Member functions

Three functions are relevant for users. All should be called periodically
with a known delta-time for smooth movement.

### `compute_control`

Compute and apply PID control. The error does not have to be in degrees
— e.g. `face_following` uses pixel error, with gains tuned accordingly.

#### Parameters
| Name          | Type    | Description                                                            | Default |
| ------------- | ------- | ---------------------------------------------------------------------- | ------- |
| t_d           | `float` | Delta time from last loop.                                             | -       |
| error         | `float` | Error input to the PID controller, equal to `reference - current`.     | -       |
| speed_desired | `float` | Desired speed in degrees per second; `-1` selects top speed.           | `-1`    |

### `reach_angle`

Move towards the desired angle at top speed.

#### Parameters
| Name  | Type    | Description                       | Default |
| ----- | ------- | --------------------------------- | ------- |
| t_d   | `float` | Delta time from last loop.        | -       |
| angle | `float` | Desired angle position (degrees). | -       |

### `reset_position`

Reset to the default position (angle of 90 degrees).

#### Parameters

| Name | Type    | Description                | Default |
| ---- | ------- | -------------------------- | ------- |
| t_d  | `float` | Delta time from last loop. | -       |
