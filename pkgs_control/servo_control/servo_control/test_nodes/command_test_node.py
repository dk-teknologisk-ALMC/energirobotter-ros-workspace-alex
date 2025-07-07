import numpy as np
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class CommandTestNode(Node):

    def __init__(self):
        super().__init__("command_test_node")

        # Parameters
        self.declare_parameter("angle", 0)
        angle = self.get_parameter("angle").get_parameter_value().integer_value

        self.declare_parameter("topic_name", "/joint_states")
        topic_name = self.get_parameter("topic_name").get_parameter_value().string_value

        self.declare_parameter("joint_name", "joint")
        joint_name = self.get_parameter("joint_name").get_parameter_value().string_value

        # Publishers
        joint_state_pub = self.create_publisher(JointState, topic_name, 1)

        # Prepare message
        joint_state_msg = JointState()
        joint_state_msg.name = [joint_name]
        joint_positions = [np.deg2rad(angle)]
        joint_state_msg.header.stamp = self.get_clock().now().to_msg()
        joint_state_msg.position = joint_positions

        # Publish once
        self.get_logger().info(
            f"Published joint state command:\ntopic_name: {topic_name}\njoint_name: {joint_name}\nangle (degrees): {angle}"
        )
        joint_state_pub.publish(joint_state_msg)

        # Sleep to ensure message is sent
        time.sleep(0.1)


def main(args=None):
    rclpy.init(args=args)

    node_handle = CommandTestNode()
    node_handle.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
