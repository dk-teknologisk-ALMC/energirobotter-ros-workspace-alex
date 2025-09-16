#include <rclcpp/rclcpp.hpp>
#include "kinematics_manager/trac_ik_manager.hpp"

#include <fstream>
#include <iostream>

class ReachabilityMapGenerator : public rclcpp::Node
{
public:
    ReachabilityMapGenerator() : Node("reachability_map_generator")
    {
        base_link_ = this->declare_parameter<std::string>("base_link", "link_torso");
        tip_link_ = this->declare_parameter<std::string>("tip_link", "link_left_hand");
    }

    void init()
    {
        auto ik_manager_ = std::make_unique<TracIKManager>(this->shared_from_this(), base_link_, tip_link_, "robot_description", KDL::Vector{-0.2, 0.5, 0.0});

        if (!ik_manager_->initialize())
        {
            RCLCPP_FATAL(this->get_logger(), "Failed to initialize TRAC-IK for %s", tip_link_.c_str());
            return;
        }
    }

    void generate_point_cloud()
    {
        // Workspace definition (meters)
        double xmin = -0.5, xmax = 0.5;
        double ymin = 0.0, ymax = 1.0;
        double zmin = -0.5, zmax = 0.5;
        double step = 0.10; // 10 cm resolution

        std::ofstream outfile("reachability_arm.ply");

        // Write simple PLY header (ASCII point cloud)
        outfile << "ply\nformat ascii 1.0\n";
        size_t approx_points = static_cast<size_t>(
            ((xmax - xmin) / step) * ((ymax - ymin) / step) * ((zmax - zmin) / step));
        outfile << "element vertex " << approx_points << "\n";
        outfile << "property float x\nproperty float y\nproperty float z\nend_header\n";

        size_t count = 0;
        for (double x = xmin; x <= xmax; x += step)
        {
            for (double y = ymin; y <= ymax; y += step)
            {
                for (double z = zmin; z <= zmax; z += step)
                {
                    // Pose with identity orientation
                    KDL::Frame pose(KDL::Rotation::Identity(), KDL::Vector(x, y, z));

                    KDL::JntArray q_out;
                    if (ik_manager_->compute_ik(pose, q_out))
                    {
                        outfile << x << " " << y << " " << z << "\n";
                        count++;
                    }
                }
            }
        }

        outfile.close();
        RCLCPP_INFO(this->get_logger(), "Reachability map written with %zu points.", count);
    }

private:
    std::unique_ptr<TracIKManager> ik_manager_;

    std::string base_link_;
    std::string tip_link_;
};

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);

    auto node = std::make_shared<ReachabilityMapGenerator>();
    node->init();

    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
