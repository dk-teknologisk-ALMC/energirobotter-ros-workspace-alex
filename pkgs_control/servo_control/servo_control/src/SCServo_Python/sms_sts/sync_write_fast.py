#!/usr/bin/env python
#
# *********     Sync Write Example      *********
#
#
# Available ST Servo model on this example : All models using Protocol ST
# This example is tested with a ST Servo(ST3215/ST3020/ST3025), and an URT
#

import sys
import os
import itertools

if os.name == "nt":
    import msvcrt

    def getch():
        return msvcrt.getch().decode()

else:
    import sys, tty, termios

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    def getch():
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scservo_sdk import *  # Uses SC Servo SDK library

# Default setting
BAUDRATE = 115200  # SC Servo default baudrate : 1000000
DEVICENAME = "/dev/ttyUSB0"  # Check which port is being used on your controller
# ex) Windows: "COM1"   Linux: "/dev/ttyUSB0" Mac: "/dev/tty.usbserial-*"

SCS_MINIMUM_POSITION_VALUE = 1800  # SC Servo will rotate between this value
SCS_MAXIMUM_POSITION_VALUE = 2400
SCS_MOVING_SPEED = 3000  # SC Servo moving speed
SCS_MOVING_ACC = 50  # SC Servo moving acc

index = 0


# Initialize PortHandler instance
# Set the port path
# Get methods and members of PortHandlerLinux or PortHandlerWindows
portHandler = PortHandler(DEVICENAME)

# Initialize PacketHandler instance
# Get methods and members of Protocol
packetHandler = sms_sts(portHandler)

# Open port
if portHandler.openPort():
    print("Succeeded to open the port")
else:
    print("Failed to open the port")
    print("Press any key to terminate...")
    getch()
    quit()


# Set port baudrate
if portHandler.setBaudRate(BAUDRATE):
    print("Succeeded to change the baudrate")
else:
    print("Failed to change the baudrate")
    print("Press any key to terminate...")
    getch()
    quit()

while 1:

    scs_id = 11

    # Create the up and down sequence
    step = 5
    sequence = list(
        range(SCS_MINIMUM_POSITION_VALUE, SCS_MAXIMUM_POSITION_VALUE + 1, step)
    ) + list(
        range(SCS_MAXIMUM_POSITION_VALUE - step, SCS_MINIMUM_POSITION_VALUE - 1, -step)
    )

    for i in itertools.cycle(sequence):

        print(i)

        # Add SC Servo#1~10 goal position\moving speed\moving accc value to the Syncwrite parameter storage
        scs_addparam_result = packetHandler.SyncWritePos(
            scs_id, i, SCS_MOVING_SPEED, SCS_MOVING_ACC
        )
        if scs_addparam_result != True:
            print("[ID:%03d] groupSyncWrite addparam failed" % scs_id)

        # Syncwrite goal position
        scs_comm_result = packetHandler.groupSyncWrite.txPacket()
        if scs_comm_result != COMM_SUCCESS:
            print("%s" % packetHandler.getTxRxResult(scs_comm_result))

        # Clear syncwrite parameter storage
        packetHandler.groupSyncWrite.clearParam()


# Close port
portHandler.closePort()
