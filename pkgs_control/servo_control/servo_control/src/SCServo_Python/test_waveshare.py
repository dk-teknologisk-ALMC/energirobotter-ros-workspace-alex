"""
Test of writing to a Waveshare servo, and cheching timing.
Run this script directly after changing the constants to match your setup.
It will count down from three and then send the PWM to the servo.
"""

import time

from scservo_sdk import PortHandler, sms_sts, scscl

PORT = "/dev/ttyUSB0"
BAUDRATE = 115200

SERVO_MODEL = "SC09"
SERVO_ID = 23
SERVO_PWM = 500

supported_servos = {
    "ST3215": sms_sts,
    "SC09": scscl,
}

# Port Setup
print("Initializing serial communication with Waveshare...")
try:
    port_handler = PortHandler(PORT)

    if not port_handler.openPort():
        print("Failed to open port, exiting...")
        exit()
    if not port_handler.setBaudRate(BAUDRATE):
        print("Failed to set baud rate, exiting...")
        exit()

    DriverClass = supported_servos[SERVO_MODEL]
    packet_handler = DriverClass(port_handler)

    print("Serial communication succesful")
except:
    print("Failed to open port, exiting...")
    exit()


print(f"Sending PWM of {SERVO_PWM} to servo {SERVO_ID} of model {SERVO_MODEL}")

for i in range(3, 0, -1):
    print(f"Countdown: {i}")
    time.sleep(1)

scs_comm_result, scs_error = packet_handler.WritePos(
    SERVO_ID, SERVO_PWM, SCS_MOVING_SPEED := 100, SCS_MOVING_ACC := 255
)

print(f"GO!")
