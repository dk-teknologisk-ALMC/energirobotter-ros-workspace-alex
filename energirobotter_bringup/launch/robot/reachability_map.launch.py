from pathlib import Path

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
)
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

package_name = "energirobotter_bringup"


def launch_setup(context, *args, **kwargs):
    description_package = LaunchConfiguration("description_package")

    urdf_file = PathJoinSubstitution(
        [FindPackageShare(description_package), "urdf", "phobos_generated.urdf"]
    ).perform(context)

    robot_description = Path(urdf_file).read_text()

    robot_state_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                FindPackageShare(package_name),
                "/launch",
                "/robot",
                "/robot_state_pub.launch.py",
            ]
        ),
    )

    reachability_map_generator = Node(
        package="kinematics_manager",
        executable="reachability_map_generator",
        parameters=[{"robot_description": robot_description}],
        output="screen",
    )

    return [
        # robot_state_launch,
        reachability_map_generator,
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
