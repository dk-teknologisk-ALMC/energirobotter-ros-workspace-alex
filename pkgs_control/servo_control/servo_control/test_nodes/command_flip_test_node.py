import numpy as np
import time
import sys, tty, termios

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


fd = sys.stdin.fileno()
old_settings = termios.tcgetattr(fd)


def getch():
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


class CommandTestNode(Node):

    def __init__(self):
        super().__init__("command_test_node")

        # Parameters
        self.declare_parameter("topic_name", "/joint_states")
        topic_name = self.get_parameter("topic_name").get_parameter_value().string_value

        self.declare_parameter("joint_name", "joint")
        joint_name = self.get_parameter("joint_name").get_parameter_value().string_value

        # Publishers
        joint_state_pub = self.create_publisher(JointState, topic_name, 1)

        # Prepare message
        joint_state_msg = JointState()
        joint_state_msg.name = [joint_name]
        joint_state_msg.header.stamp = self.get_clock().now().to_msg()

        angles = [30, 60]

        index = 0
        while 1:
            self.get_logger().info("Press any key to continue! (or press ESC to quit!)")
            if getch() == chr(0x1B):
                break

            joint_positions = [np.deg2rad(angles[index])]
            joint_state_msg.position = joint_positions

            self.get_logger().info(
                f"Published joint state command:\ntopic_name: {topic_name}\njoint_name: {joint_name}\nangle (degrees): {angles[index]}"
            )
            joint_state_pub.publish(joint_state_msg)

            if index == 0:
                index = 1
            else:
                index = 0


def main(args=None):
    rclpy.init(args=args)

    node_handle = CommandTestNode()
    node_handle.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
