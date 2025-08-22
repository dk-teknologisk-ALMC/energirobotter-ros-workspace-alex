from dataclasses import dataclass, field
import numpy as np
from typing import Callable, Dict

import pyroki as pk
import pyroki.examples.pyroki_snippets as pks

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile
from std_msgs.msg import String
from sensor_msgs.msg import JointState
from geometry_msgs.msg import Pose, PoseStamped


@dataclass
class EndEffector:
    name: str
    chain_name: str
    callback: Callable
    locked_joints: Dict[int, float] = field(
        default_factory=dict
    )  # {link_id(int), angle(float)}
    target_position: np.ndarray = field(
        default_factory=lambda: np.array([0.5, 0.5, 0.5])
    )
    target_rotation: np.ndarray = field(
        default_factory=lambda: np.array([0.0, 0.0, 0.0, 1.0])
    )


class KinematicsManagerNode(Node):
    def __init__(self):
        super().__init__("kinematics_manager_node")

        self.end_effectors = {
            "left": EndEffector(
                name="link_left_hand",
                chain_name="left",
                callback=self.callback_target_pos_left,
            ),
            "right": EndEffector(
                name="link_right_hand",
                chain_name="right",
                callback=self.callback_target_pos_right,
            ),
        }

        self.timer = self.create_timer(0.1, self.callback_timer_publish_joint_states)

        # Create robot
        urdf = self.retrieve_urdf()
        self.robot = pk.Robot.from_urdf(urdf)

    def retrieve_urdf(self, timeout_sec: float = 15):
        self.get_logger().info('Retrieving URDF from "/robot_description"...')

        qos_profile = QoSProfile(depth=1)
        qos_profile.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL

        self.urdf = None

        def urdf_received(msg: String):
            self.urdf = msg.data

        self.create_subscription(
            msg_type=String,
            topic="/robot_description",
            qos_profile=qos_profile,
            callback=urdf_received,
        )
        rclpy.spin_once(self, timeout_sec=timeout_sec)

        if self.urdf is None:
            self.get_logger().error("Could not retrieve the URDF!")
            raise EnvironmentError("Could not retrieve the URDF!")

        self.get_logger().info("Done!")

        return self.urdf

    def ros_pose_to_pos_rot(self, pose: Pose):

        position = np.ndarray([pose.position.x, pose.position.y, pose.position.z])
        rotation = np.ndarray(
            [
                pose.orientation.w,
                pose.orientation.x,
                pose.orientation.y,
                pose.orientation.z,
            ]
        )

        return position, rotation

    def callback_target_pos_left(self, msg: PoseStamped):
        pos, rot = self.ros_pose_to_pos_rot(msg.pose)
        self.end_effectors["left"].target_position = pos
        self.end_effectors["left"].target_rotation = rot

    def callback_target_pos_right(self, msg: PoseStamped):
        pos, rot = self.ros_pose_to_pos_rot(msg.pose)
        self.end_effectors["right"].target_position = pos
        self.end_effectors["right"].target_rotation = rot

    def callback_timer_publish_joint_states(self):
        """
        Publish the joint states based on the IK solution.
        """

        solution = pks.solve_ik(
            robot=self.robot,
            target_link_name=self.end_effectors[0],
            target_position=self.target_posistion[0],
            target_wxyz=self.target_rotation[0],
        )

        self.get_logger().info(solution)


def main(args=None):
    rclpy.init(args=args)

    node_handle = KinematicsManagerNode()
    rclpy.spin(node_handle)
    node_handle.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
