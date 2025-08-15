"""
Resets all servos to their default positions.
"""

import time

import rclpy
from rclpy.node import Node

from servo_control.src.driver_waveshare import DriverWaveshare


class ServoResetNode(Node):

    def __init__(self):
        super().__init__("servo_reset_node")

        # Parameters
        self.declare_parameter(
            "config_folder_path",
            "install/wattson_description/share/wattson_description/servo_configs",
        )
        config_folder_path = (
            self.get_parameter("config_folder_path").get_parameter_value().string_value
        )

        self.reset_servos(
            [f"{config_folder_path}/servo_arm_left_params.json"], "/dev/ttyUSB0"
        )

        self.reset_servos(
            [f"{config_folder_path}/servo_arm_right_params.json"], "/dev/ttyUSB1"
        )

        time.sleep(1.0)

    def reset_servos(self, config, port):
        self.servo_driver = DriverWaveshare(
            config,
            control_frequency=1.0,
            port_path=port,
        )
        self.servo_driver.initialize()

        # Send commands
        self.servo_commands = self.servo_driver.get_default_servo_commands()
        self.servo_driver.command_servos(self.servo_commands)


def main(args=None):
    rclpy.init(args=args)

    node_handle = ServoResetNode()
    node_handle.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
