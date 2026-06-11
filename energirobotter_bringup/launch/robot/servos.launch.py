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
    control_frequency = LaunchConfiguration("control_frequency")

    # Servo Driver
    servo_manager_node = Node(
        package="servo_control",
        executable="wattson_servo_manager_node",
        output="screen",
        parameters=[
            {
                "config_folder_path": config_folder_path,
                "finger_mapping_enabled": finger_mapping_enabled,
                "control_frequency": control_frequency,
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
            # control_frequency er hard-coded til 10.0 i
            # wattson_servo_manager_node. Driverens update_feedback()
            # laver sync-read fra hver servo paa bussen og er den reelle
            # flaskehals; med ~14 servos pr. bus er en fuld cycle nemt
            # 70-150 ms. 50 Hz testet og fundet at vaere katastrofalt
            # (timer-overrun + jitter). Lader default'en staa, men
            # eksponerer den som launch-arg saa man kan eksperimentere.
            DeclareLaunchArgument(
                "control_frequency",
                default_value="10.0",
                description="Servo command/feedback loop frequency [Hz]. "
                "10 Hz er nuvaerende safe default; hoejere vaerdier kan "
                "give timer-overrun pga. sync-read latency paa bussen.",
            ),
            OpaqueFunction(function=launch_setup),
        ]
    )
