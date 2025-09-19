from pathlib import Path

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    OpaqueFunction,
)
from launch.conditions import IfCondition
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

package_name = "energirobotter_bringup"


def launch_setup(context, *args, **kwargs):
    rviz = LaunchConfiguration("rviz")
    interactive_marker = LaunchConfiguration("interactive_marker")
    description_package = LaunchConfiguration("description_package")
    ik_solver = LaunchConfiguration("ik_solver")

    urdf_file = PathJoinSubstitution(
        [FindPackageShare(description_package), "urdf", "phobos_generated.urdf"]
    ).perform(context)

    robot_description = Path(urdf_file).read_text()

    rviz_config_file = PathJoinSubstitution(
        [
            FindPackageShare(package_name),
            "config",
            "rviz",
            "teleoperation.rviz",
        ]
    )

    robot_state_pub_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        arguments=[urdf_file],
        output="screen",
    )

    if ik_solver.perform(context) == "trac_ik":
        ik_node = Node(
            package="kinematics_manager",
            executable="trac_ik_node",
            parameters=[{"robot_description": robot_description}],
            output="screen",
        )
    else:
        ik_node = Node(
            package="elrik_kdl_kinematics",
            executable="elrik_kdl_kinematics_node",
            parameters=[{"robot_description": robot_description}],
            output="screen",
        )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="log",
        arguments=["-d", rviz_config_file],
        condition=IfCondition(rviz),
    )

    interactive_marker_node = Node(
        package="control_utils",
        executable="target_pose_marker",
        output="screen",
        condition=IfCondition(interactive_marker),
    )

    return [
        robot_state_pub_node,
        ik_node,
        rviz_node,
        interactive_marker_node,
    ]


def generate_launch_description():

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "rviz",
                default_value="false",
                description="Start RViz2 automatically with this launch file.",
                choices=["true", "false"],
            ),
            DeclareLaunchArgument(
                "interactive_marker",
                default_value="false",
                description="Enable interactive marker to control IK target pose in RViz.",
                choices=["true", "false"],
            ),
            DeclareLaunchArgument(
                "description_package",
                default_value="wattson_description",
                description="Package in workspace that contains robot URDF description.",
                choices=["elrik_description", "wattson_description"],
            ),
            DeclareLaunchArgument(
                "ik_solver",
                default_value="kdl",
                description="Choose IK solver to use.",
                choices=["kdl", "trac_ik"],
            ),
            OpaqueFunction(function=launch_setup),
        ]
    )
