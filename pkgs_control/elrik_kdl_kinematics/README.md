# Elrik KDL Kinematics

Forward/inverse kinematics for the Elrik humanoid arms, using KDL.
Forked from Pollen Robotics'
[reachy_kdl_kinematics](https://github.com/pollen-robotics/reachy_2023/tree/develop/reachy_kdl_kinematics).

Loaded automatically by the bringup launch files.

## Kinematics services

- `/r_arm/forward_kinematics` ([GetForwardKinematics.srv](../reachy_msgs/srv/GetForwardKinematics.srv))
  — forward kinematics for the right arm. Expects 7 joint values:
  `r_shoulder_pitch`, `r_shoulder_roll`, `r_arm_yaw`, `r_elbow_pitch`,
  `r_forearm_yaw`, `r_wrist_pitch`, `r_wrist_roll`.
- `/r_arm/inverse_kinematics` ([GetInverseKinematics.srv](../reachy_msgs/srv/GetInverseKinematics.srv))
  — inverse kinematics for the right arm.
- `/l_arm/forward_kinematics` ([GetForwardKinematics.srv](../reachy_msgs/srv/GetForwardKinematics.srv))
  — forward kinematics for the left arm. Expects 7 joint values:
  `l_shoulder_pitch`, `l_shoulder_roll`, `l_arm_yaw`, `l_elbow_pitch`,
  `l_forearm_yaw`, `l_wrist_pitch`, `l_wrist_roll`.
- `/l_arm/inverse_kinematics` ([GetInverseKinematics.srv](../reachy_msgs/srv/GetInverseKinematics.srv))
  — inverse kinematics for the left arm.

## Cartesian control

The node can also act as a Cartesian controller: it listens for Cartesian
targets, solves IK, and publishes the resulting joint commands directly to
the corresponding forward-position controller.

For each arm, two topics are available (right arm shown):

- `/r_arm/target_pose` ([PoseStamped](http://docs.ros.org/en/noetic/api/geometry_msgs/html/msg/PoseStamped.html))
  — solves IK for the given pose and sends the joint solution to the
  forward-position controller.
- `/r_arm/averaged_target_pose` ([PoseStamped](http://docs.ros.org/en/noetic/api/geometry_msgs/html/msg/PoseStamped.html))
  — averages the pose over the last *n* samples, solves IK, clips the
  joint solution to a maximum velocity, then publishes the result. Intended
  for high-frequency use (> 10 Hz).

The left arm exposes the same two topics: `/l_arm/target_pose` and
`/l_arm/averaged_target_pose`.

## Requirements

The node needs `/robot_description` and `/joint_states` to be published.
The specific kinematic chains and corresponding services/topics are
derived from the URDF.

## Install

```
sudo apt install python3-pykdl
```
