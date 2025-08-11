import numpy as np
import pyroki as pk
import pyroki.examples.pyroki_snippets as pks

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile
from std_msgs.msg import String
from sensor_msgs.msg import JointState
from geometry_msgs.msg import Pose, PoseStamped


class KinematicsManagerNode(Node):
    def __init__(self):
        super().__init__("kinematics_manager_node")

        self.end_effectors = [
            "link_left_hand",
            "link_right_hand",
            # "link_head_roll",
        ]

        self.chain_names = {
            self.end_effectors[0]: "left",
            self.end_effectors[1]: "right",
            # self.end_effectors[2]: "head",
        }

        self.locked_joints = {
            # {link_id(int), angle(float)}
            self.end_effectors[0]: {},
            self.end_effectors[1]: {},
            # self.end_effectors[2]: {},
        }

        self.end_effector_callback_subs = {
            self.end_effectors[0]: self.callback_target_pos_left,
            self.end_effectors[1]: self.callback_target_pos_right,
            # self.end_effectors[2]: self.callback_target_pos_head,
        }

        self.target_posistion = {
            self.end_effectors[0]: np.array([0.5, 0.5, 0.5]),
            self.end_effectors[1]: np.array([0.5, 0.5, 0.5]),
        }

        self.target_rotation = {
            self.end_effectors[0]: np.array([0.0, 0.0, 0.0, 1.0]),
            self.end_effectors[1]: np.array([0.0, 0.0, 0.0, 1.0]),
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

        self.target_posistion[self.end_effectors[0]] = pos
        self.target_rotation[self.end_effectors[0]] = rot

    def callback_target_pos_right(self, msg: PoseStamped):
        pos, rot = self.ros_pose_to_pos_rot(msg.pose)

        self.target_posistion[self.end_effectors[1]] = pos
        self.target_rotation[self.end_effectors[1]] = rot

    def callback_target_pos_head(self, msg: PoseStamped):
        pos, rot = self.ros_pose_to_pos_rot(msg.pose)

        self.target_posistion[self.end_effectors[2]] = pos
        self.target_rotation[self.end_effectors[2]] = rot

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
