#include <memory>
#include <vector>
#include <mutex>

#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <sensor_msgs/msg/joint_state.hpp>

#include "kinematics_manager/trac_ik_manager.hpp"

class TracIKNode : public rclcpp::Node
{
public:
  TracIKNode() : Node("trac_ik_node") {}

  void init()
  {
    // Parameters
    base_link_ = this->declare_parameter<std::string>("base_link", "link_torso");
    tip_link_ = this->declare_parameter<std::string>("tip_link", "link_left_hand");
    double timeout = this->declare_parameter<double>("timeout", 0.005);
    double eps = this->declare_parameter<double>("eps", 1e-5);
    double publish_rate = this->declare_parameter<double>("publish_rate", 30.0);

    // Initialize TRAC-IK manager
    ik_manager_ = std::make_unique<TracIKManager>(
        this->shared_from_this(),
        base_link_,
        tip_link_,
        "robot_description",
        KDL::Vector{-0.2, 0.5, 0.0},
        timeout,
        eps,
        TRAC_IK::SolveType::Distance);

    if (!ik_manager_->initialize())
    {
      RCLCPP_FATAL(this->get_logger(), "Failed to initialize TRAC-IK manager");
      return;
    }

    // Subscribers
    sub_ = this->create_subscription<geometry_msgs::msg::PoseStamped>(
        "/left/target_pose",
        10,
        std::bind(&TracIKNode::pose_callback, this, std::placeholders::_1));

    // Publishers
    pub_ = this->create_publisher<sensor_msgs::msg::JointState>("/joint_states", 10);

    // Timers
    timer_ = this->create_wall_timer(
        std::chrono::duration<double>(1.0 / publish_rate),
        std::bind(&TracIKNode::publish_ik_solution, this));
  }

private:
  void pose_callback(const geometry_msgs::msg::PoseStamped::SharedPtr msg)
  {
    std::lock_guard<std::mutex> lock(pose_mutex_);
    latest_pose_ = msg->pose;
  }

  void publish_ik_solution()
  {
    geometry_msgs::msg::Pose pose;
    {
      std::lock_guard<std::mutex> lock(pose_mutex_);
      pose = latest_pose_;
    }

    KDL::Vector target_pos(
        pose.position.x,
        pose.position.y,
        pose.position.z);

    KDL::Rotation target_rot = KDL::Rotation::Quaternion(
        pose.orientation.x,
        pose.orientation.y,
        pose.orientation.z,
        pose.orientation.w);

    KDL::Frame target(target_rot, target_pos);

    KDL::JntArray q_out;
    bool success = ik_manager_->compute_ik(target, q_out);

    if (success)
    {
      RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 1000, "IK solution found");
    }

    // Publish JointState
    sensor_msgs::msg::JointState js_msg;
    js_msg.header.stamp = this->now();
    js_msg.name = ik_manager_->get_joint_names();
    js_msg.position.resize(q_out.rows());
    for (unsigned int i = 0; i < q_out.rows(); i++)
      js_msg.position[i] = q_out(i);

    pub_->publish(js_msg);
  }

  std::unique_ptr<TracIKManager> ik_manager_;
  rclcpp::Publisher<sensor_msgs::msg::JointState>::SharedPtr pub_;
  rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr sub_;
  rclcpp::TimerBase::SharedPtr timer_;

  std::mutex pose_mutex_;
  geometry_msgs::msg::Pose latest_pose_;

  std::string base_link_;
  std::string tip_link_;
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);

  auto node = std::make_shared<TracIKNode>();
  node->init();

  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
