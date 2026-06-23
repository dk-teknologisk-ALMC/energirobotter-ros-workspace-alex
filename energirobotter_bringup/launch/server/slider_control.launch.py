import subprocess
from pathlib import Path
from urllib.parse import quote

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    OpaqueFunction,
)
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


package_name = "energirobotter_bringup"


def launch_setup(context, *args, **kwargs):
    description_package = LaunchConfiguration("description_package").perform(context)

    pkg_share = FindPackageShare(description_package).perform(context)
    urdf_file = str(Path(pkg_share) / "urdf" / "phobos_generated.urdf")

    # Run xacro as an argv list (no shell) so paths containing spaces work.
    # urdf_launch's display.launch.py uses Command(['xacro ', path]) which
    # joins+shell-splits and breaks on workspace paths like "Humanoid build".
    robot_description_xml = subprocess.check_output(
        ["xacro", urdf_file], text=True
    )

    # RViz's resource_retriever expands package:// via ament_index, which
    # returns the absolute install path. When the workspace lives under a
    # path with spaces (e.g. "Humanoid build/"), the resulting file:// URL
    # contains literal spaces and RViz fails to load every STL mesh. We
    # pre-resolve package:// to a percent-encoded file:// URL so RViz never
    # sees a raw space.
    pkg_share_url = "file://" + quote(pkg_share, safe="/")
    robot_description_xml = robot_description_xml.replace(
        f"package://{description_package}/",
        f"{pkg_share_url}/",
    )

    rviz_config_file = str(
        Path(FindPackageShare(package_name).perform(context))
        / "config"
        / "rviz"
        / "teleoperation.rviz"
    )

    return [
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            parameters=[{"robot_description": robot_description_xml}],
        ),
        Node(
            package="joint_state_publisher_gui",
            executable="joint_state_publisher_gui",
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2",
            arguments=["-d", rviz_config_file],
        ),
    ]


def generate_launch_description():

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "description_package",
                default_value="wattson_description",
                description="Package in workspace that contains robot URDF description.",
                choices=["elrik_description", "wattson_description"],
            ),
            OpaqueFunction(function=launch_setup),
        ]
    )
