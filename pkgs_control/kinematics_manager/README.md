# Kinematics Manager

ROS 2 package for managing the kinematics of humanoid robots, including
URDF parsing and inverse kinematics (IK) for the arms.

A reachability-map tool is also included for analysis.

## Nodes

All nodes using TRAC-IK must be passed `robot_description` as a parameter.
The easiest way is from a launch file; see
`launch/reachability_map.launch.py` for an example.

### trac_ik_node

Computes IK solutions for the left and right arm end-effectors using
TRAC-IK. Subscribes to a target-pose topic for each arm and publishes
joint states on `/joint_states` for use by controllers or visualisation
tools.

#### Topics

- **Subscribed:**
  - `/left/target_pose` (`geometry_msgs/PoseStamped`) — target pose for the left hand
  - `/right/target_pose` (`geometry_msgs/PoseStamped`) — target pose for the right hand

- **Published:**
  - `/joint_states` (`sensor_msgs/JointState`) — joint positions for all managed IK chains

#### Parameters

- `base_link` (`string`, default: `"link_torso"`) — base link for kinematics calculations
- `publish_rate` (`double`, default: `30.0`) — publish frequency in Hz

### reachability_map_generator

Generates a reachability map for one arm by sampling a 3D workspace and
checking which points are reachable via TRAC-IK. The result is saved as a
PLY point cloud for visualisation.

#### Parameters

- `base_link` (`string`, default: `"link_torso"`) — base link for kinematics calculations
- `tip_link` (`string`, default: `"link_left_hand"`) — tip link (end-effector) to analyse
- `step_size` (`double`, default: `0.02`) — workspace grid resolution in metres

#### Output

- `pointcloud.ply` — ASCII PLY file listing all reachable points

#### Notes

- Progress is logged as a percentage of points processed.
- The workspace volume and orientation are hard-coded and can be modified
  in the source.
- Each thread uses its own TRAC-IK manager instance for thread safety.
- On Ctrl+C the node saves partial results and overwrites `pointcloud.ply`
  with whatever has been computed so far.

