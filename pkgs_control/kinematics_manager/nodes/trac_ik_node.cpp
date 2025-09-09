#include <memory>
#include <vector>
#include <mutex>

#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <sensor_msgs/msg/joint_state.hpp>

#include <trac_ik/trac_ik.hpp>
#include <kdl/chain.hpp>
#include <kdl/jntarray.hpp>

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
    double publish_rate = this->declare_parameter<double>("publish_rate", 30.0); // Hz

    // Create TRAC-IK solver
    solver_ = std::make_unique<TRAC_IK::TRAC_IK>(
        this->shared_from_this(),
        base_link_,
        tip_link_,
        "robot_description",
        timeout,
        eps,
        TRAC_IK::SolveType::Distance);

    // Verify KDL chain and get joint names
    KDL::Chain chain;
    if (!solver_->getKDLChain(chain))
    {
      RCLCPP_FATAL(this->get_logger(), "Could not fetch KDL chain");
      return;
    }

    // Get joint limits
    if (!solver_->getKDLLimits(min_limits_, max_limits_))
    {
      RCLCPP_FATAL(this->get_logger(), "Could not fetch KDL joint limits");
      return;
    }

    q_out_.resize(chain.getNrOfJoints());
    joint_names_.resize(chain.getNrOfJoints());
    q_last_valid_.resize(chain.getNrOfJoints());

    // Initialize all joints to 0
    for (size_t i = 0; i < chain.getNrOfJoints(); i++)
    {
      joint_names_[i] = chain.getSegment(i).getJoint().getName();
      q_out_(i) = 0.0;
      q_last_valid_(i) = 0.0;
    }

    RCLCPP_INFO(this->get_logger(), "TRAC-IK initialized with %d joints", chain.getNrOfJoints());

    // Subscriber for target PoseStamped
    sub_ = this->create_subscription<geometry_msgs::msg::PoseStamped>(
        "/left/target_pose",
        10,
        std::bind(&TracIKNode::pose_callback, this, std::placeholders::_1));

    // Publisher for JointState
    pub_ = this->create_publisher<sensor_msgs::msg::JointState>("/joint_states", 10);

    // Timer for periodic IK computation and publishing
    timer_ = this->create_wall_timer(
        std::chrono::duration<double>(1.0 / publish_rate),
        std::bind(&TracIKNode::publish_ik_solution, this));
  }

private:
  KDL::JntArray findBoundaryBisection(const KDL::JntArray &nominal, const KDL::Frame &target_out_of_bounds, KDL::JntArray &q_out, double epsilon = 1e-5)
  {
    KDL::Vector p_low = target_pos_center_;      // last inside point
    KDL::Vector p_high = target_out_of_bounds.p; // first outside point
    KDL::Rotation target_rot = target_out_of_bounds.M;

    // Bisection loop
    while ((p_high - p_low).Norm() > epsilon)
    {
      KDL::Vector p_mid = 0.5 * (p_low + p_high);
      KDL::Frame target(target_rot, p_mid);

      int rc = solver_->CartToJnt(nominal, target, q_out);

      if (rc >= 0)
      {
        p_low = p_mid; // move low up
      }
      else
      {
        p_high = p_mid; // move high down
      }
    }
    return q_out;
  }

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

    KDL::Rotation target_rot(KDL::Rotation::Quaternion(
        pose.orientation.x,
        pose.orientation.y,
        pose.orientation.z,
        pose.orientation.w));

    KDL::Frame target(target_rot, target_pos);

    // Nominal joint positions
    KDL::JntArray nominal(q_out_.rows());
    for (unsigned int i = 0; i < nominal.rows(); i++)
      nominal(i) = q_last_valid_(i); // use last valid solution as nominal

    int rc = solver_->CartToJnt(nominal, target, q_out_);

    if (rc < 0)
    {
      findBoundaryBisection(nominal, target, q_out_);
      RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 1000, "Approximating IK solution...");
    }

    q_last_valid_ = q_out_; // update last valid solution

    RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 1000, "IK solution found");

    // --- Joint limit check ---
    double threshold = 1e-3; // rad
    for (unsigned int i = 0; i < q_out_.rows(); i++)
    {
      double val = q_out_(i);
      double lower = min_limits_(i);
      double upper = max_limits_(i);

      if (val <= lower + threshold)
      {
        RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 2000,
                             "Joint %s near LOWER limit: %.3f (limit = %.3f)",
                             joint_names_[i].c_str(), val, lower);
      }
      else if (val >= upper - threshold)
      {
        RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 2000,
                             "Joint %s near UPPER limit: %.3f (limit = %.3f)",
                             joint_names_[i].c_str(), val, upper);
      }
    }

    // Publish JointState
    sensor_msgs::msg::JointState js_msg;
    js_msg.header.stamp = this->now();
    js_msg.name = joint_names_;
    js_msg.position.resize(q_out_.rows());
    for (unsigned int i = 0; i < q_out_.rows(); i++)
      js_msg.position[i] = q_out_(i);

    pub_->publish(js_msg);
  }

  std::unique_ptr<TRAC_IK::TRAC_IK> solver_;
  KDL::Vector target_pos_last_valid_;
  KDL::JntArray q_out_;
  KDL::JntArray q_last_valid_;
  KDL::JntArray min_limits_;
  KDL::JntArray max_limits_;
  std::vector<std::string> joint_names_;

  KDL::Vector target_pos_center_{-0.2, 0.5, 0.0};

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
