import numpy as np

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

from animation_player.src import csv_reader


class AnimationPlayerNode(Node):

    def __init__(self):
        super().__init__("animation_player_node")

        # Parameters
        self.declare_parameter("fps", 24)
        self.fps = self.get_parameter("fps").get_parameter_value().integer_value

        self.declare_parameter("csv_file_path", "")
        self.csv_file_path = (
            self.get_parameter("csv_file_path").get_parameter_value().string_value
        )

        # CSV file setup
        self.csv_reader = csv_reader.CSVReader(self.csv_file_path)

        header = self.csv_reader.get_header()
        self.joints_names = header[1:]  # Skip frame info

        # Split joints into arm (non-hand) and hand
        self.arm_names = [
            name for name in self.joints_names if name.startswith("joint_")
        ]
        self.hand_names = [
            name for name in self.joints_names if name.startswith("hand_")
        ]

        # Timers
        self.timer = self.create_timer(1.0 / self.fps, self.callback_timer)

        # Publishers
        self.joint_state_pub = self.create_publisher(JointState, "/joint_states", 10)
        self.joint_state_hands_pub = self.create_publisher(
            JointState, "/joint_states_hands", 10
        )

        # Node variables
        self.joint_state_msg = JointState()
        self.joint_state_msg.name = self.arm_names

        self.joint_state_hands_msg = JointState()
        self.joint_state_hands_msg.name = self.hand_names

    def __del__(self):
        self.csv_reader.close()

    def callback_timer(self):
        row_data = self.csv_reader.get_next_row()
        if row_data is None:
            return  # End of file, optional: loop or stop

        joint_values = [float(x) for x in row_data[1:]]  # Degrees
        joint_data = [np.deg2rad(v) for v in joint_values]  # To radians

        # Indices for splitting
        arm_indices = [
            i for i, name in enumerate(self.joints_names) if name.startswith("joint_")
        ]
        hand_indices = [
            i for i, name in enumerate(self.joints_names) if name.startswith("hand_")
        ]

        arm_positions = [joint_data[i] for i in arm_indices]
        hand_positions = [joint_data[i] for i in hand_indices]

        now = self.get_clock().now().to_msg()

        # Arm message
        self.joint_state_msg.header.stamp = now
        self.joint_state_msg.header.frame_id = row_data[0]
        self.joint_state_msg.position = arm_positions
        self.joint_state_pub.publish(self.joint_state_msg)

        # Hands message
        self.joint_state_hands_msg.header.stamp = now
        self.joint_state_hands_msg.header.frame_id = row_data[0]
        self.joint_state_hands_msg.position = hand_positions
        self.joint_state_hands_pub.publish(self.joint_state_hands_msg)


def main(args=None):
    rclpy.init(args=args)

    animation_player_node = AnimationPlayerNode()

    rclpy.spin(animation_player_node)
    animation_player_node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
