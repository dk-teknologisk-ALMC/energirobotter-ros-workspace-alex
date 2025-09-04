cmake_minimum_required(VERSION 3.8)
project(kinematics_manager)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)  # allows mixing Python + C++
find_package(rclcpp REQUIRED)
find_package(trac_ik_lib REQUIRED)
find_package(orocos_kdl REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)

# C++ node
add_executable(trac_ik_node src/trac_ik_node.cpp)
ament_target_dependencies(trac_ik_node rclcpp trac_ik_lib orocos_kdl geometry_msgs sensor_msgs)
install(TARGETS trac_ik_node DESTINATION lib/${PROJECT_NAME})

# Python setup
ament_python_install_package(${PROJECT_NAME})
install(PROGRAMS
  kinematics_manager/target_pose_marker.py
  DESTINATION lib/${PROJECT_NAME})

ament_package()
