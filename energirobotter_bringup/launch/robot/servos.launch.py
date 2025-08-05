from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    OpaqueFunction,
)
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

package_name = "energirobotter_bringup"


def launch_setup(context, *args, **kwargs):
    config_folder_path = LaunchConfiguration("config_folder_path")
    finger_mapping_enabled = LaunchConfiguration("finger_mapping_enabled")

    # Servo Driver
    servo_manager_node = Node(
        package="servo_control",
        executable="wattson_servo_manager_node",
        output="screen",
        parameters=[
            {
                "config_folder_path": config_folder_path,
                "finger_mapping_enabled": finger_mapping_enabled,
            },
        ],
    )

    return [
        servo_manager_node,
    ]


def generate_launch_description():

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "config_folder_path",
                default_value="install/wattson_description/share/wattson_description/servo_configs",
                description="Folder containing servo configs.",
            ),
            DeclareLaunchArgument(
                "finger_mapping_enabled",
                default_value="True",
                description="Map finger tracking to full range of servos.",
            ),
            OpaqueFunction(function=launch_setup),
        ]
    )
