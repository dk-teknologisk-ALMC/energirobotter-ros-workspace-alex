import rclpy
from rclpy.node import Node
import std_msgs.msg
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

        self.joints_names = []
        for joint in self.csv_reader.get_header():
            self.joints_names.append(joint)

        self.joints_names = self.joints_names[1:]  # Skip frame

        # Timers
        self.timer = self.create_timer(1.0 / self.fps, self.callback_timer)

        # Publishers
        self.joint_state_pub = self.create_publisher(JointState, "/joint_states", 10)

        # Node variables
        self.joint_state_msg = JointState()
        self.joint_state_msg.name = self.joints_names

    def __del__(self):
        self.csv_reader.close()

    def callback_timer(self):

        row_data = self.csv_reader.get_next_row()
        joint_data = [float(x) for x in row_data[1:]]

        self.joint_state_msg.header.stamp = self.get_clock().now().to_msg()
        self.joint_state_msg.header.frame_id = row_data[0]
        self.joint_state_msg.position = joint_data

        # Publish the joint state message
        self.joint_state_pub.publish(self.joint_state_msg)


def main(args=None):
    rclpy.init(args=args)

    animation_player_node = AnimationPlayerNode()

    rclpy.spin(animation_player_node)
    animation_player_node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
