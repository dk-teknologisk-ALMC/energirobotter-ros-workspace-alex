import rclpy
from rclpy import Node
import std_msgs.msg

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

        self.joint_idx: int = {}
        self.joint_publishers = {}
        for idx, joint in enumerate(self.csv_reader.get_header()):
            self.joint_idx[joint] = idx
            self.joint_publishers[joint] = None

        # Timers
        self.timer = self.create_timer(1.0 / self.fps, self.callback_timer)

        # Publishers
        for joint in self.joint_publishers.keys():
            self.joint_publishers[joint] = self.create_publisher(
                std_msgs.msg.Float64, "/" + joint + "/set_error", 1
            )

        # Node variables

    def __del__(self):
        self.csv_reader.close()

    def callback_timer(self):

        if None in self.joint_publishers.values():
            return

        row = self.csv_reader.get_next_row()

        for joint in self.joint_publishers.keys():
            data = row[self.joint_idx[joint]]
            self.joint_publishers[joint].publish(std_msgs.msg.Float64(data=float(data)))


def main(args=None):
    rclpy.init(args=args)

    animation_player_node = AnimationPlayerNode()

    rclpy.spin(animation_player_node)
    animation_player_node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
