"""
Servo driver/manager of humanoid robot servos, which are servos controlled by a Waveshare driver.
"""

import json
import threading
import time

from .SCServo_Python.scservo_sdk import PortHandler, sms_sts, scscl, scservo_def
from .utils import interval_map
from servo_control.src.driver_servos import DriverServos
from servo_control.src.servo_control import ServoControl

PORT = "/dev/ttyUSB0"
BAUDRATE = 115200

supported_servos = {
    "ST3215": sms_sts,
    "SC09": scscl,
}


class DriverWaveshare(DriverServos):
    def __init__(self, config_files, control_frequency):
        super().__init__(config_files)

        self.servo_models = []
        for config in config_files:
            with open(config, "r") as file:
                group_config = json.load(file)
                servo_model = group_config["group"]["servo_model"]
                self.servo_models.append(servo_model)

        self.driver_objects = {}
        self.port_handler = None
        self.running = True
        self.lock = threading.Lock()

        self.loop_thread_read = threading.Thread(
            target=self.loop_sync_commands,
            args=(self.sync_commands_read, 1.0),
            daemon=True,
        )

        self.loop_thread_write = threading.Thread(
            target=self.loop_sync_commands,
            args=(self.sync_commands_write, control_frequency),
            daemon=True,
        )

    def __del__(self):
        self.running = False
        self.port_handler.closePort()

    def setup_driver(self):

        self.logger.info("Initializing serial communication with Waveshare...")

        try:
            self.port_handler = PortHandler(PORT)

            if not self.port_handler.openPort():
                self.logger.error("Failed to open port")
                return False

            if not self.port_handler.setBaudRate(BAUDRATE):
                self.logger.error("Failed to set baud rate")
                return False

            # Setup different driver classes for different servo models
            for model in self.servo_models:
                DriverClass = supported_servos[model]
                driver_object = DriverClass(self.port_handler)
                self.driver_objects[model] = driver_object

            self.logger.info(
                f"Drivers setup for servo model: {', '.join(self.servo_models)}"
            )

            # Start threads after driver setup
            self.loop_thread_read.start()
            self.loop_thread_write.start()

            self.logger.info("Serial communication successful")
            return True

        except Exception as e:
            self.logger.error(f"Failed to open port: {e}")
            return False

    def loop_sync_commands(self, callback_func, frequency=1.0):
        interval = 1.0 / frequency

        while self.running:
            start = time.time()
            callback_func()  # call the passed-in function
            elapsed = time.time() - start
            time.sleep(max(0, interval - elapsed))

    def sync_commands_read(self):

        if not "ST3215" in self.driver_objects:
            return

        driver = self.driver_objects["ST3215"]

        with self.lock:

            # Sync read
            driver.groupSyncRead.clearParam()

            for servo in self.servos.values():
                scs_addparam_result = driver.groupSyncRead.addParam(servo.servo_id)

            scs_comm_result = driver.groupSyncRead.txRxPacket()
            if scs_comm_result != scservo_def.COMM_SUCCESS:
                self.logger.error(
                    f"Communication error while reading: {driver.getTxRxResult(scs_comm_result)}"
                )

    def sync_commands_write(self):

        with self.lock:

            for driver in self.driver_objects.values():

                # Sync write
                scs_comm_result = driver.groupSyncWrite.txPacket()
                if scs_comm_result != scservo_def.COMM_SUCCESS:
                    self.logger.error(
                        f"Communication error while writing: {driver.getTxRxResult(scs_comm_result)}"
                    )
                driver.groupSyncWrite.clearParam()

    def read_feedback(self, servo: ServoControl):

        if not "ST3215" in self.driver_objects:
            return

        driver = self.driver_objects["ST3215"]

        try:
            feedback = driver.SyncRead(servo.servo_id)
            return feedback

        except Exception as e:
            self.logger.error(f"Failed to read feedback: {e}")
            return None

    def write_command(self, servo: ServoControl, pwm):

        with self.lock:
            # self.logger.info(f"Servo: {servo.servo_id}. Stopping pwm of: {pwm}")
            # return

            for driver in self.driver_objects.values():

                # Add SC position\moving speed\moving accc value to the Syncwrite parameter storage
                scs_addparam_result = driver.SyncWritePos(
                    servo.servo_id,
                    pwm,
                    SCS_MOVING_SPEED := 2000,
                    SCS_MOVING_ACC := 64,
                )

                if scs_addparam_result != True:
                    self.logger.warning(
                        f"groupSyncWrite addparam failed, servo ID: {servo.servo_id}"
                    )

    def map_finger_to_servo(servo: ServoControl, angle_cmd):
        # Function specific to finger servos, that takes an angle between 0-90 and converts to correct range

        angle_mapped = interval_map(
            angle_cmd,
            0,
            90,
            servo.angle_software_min - servo.default_position,
            servo.angle_software_max - servo.default_position,
        )

        return angle_mapped
