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
        ik_manager_ = std::make_unique<TracIKManager>(this->shared_from_this(), base_link_, tip_link_, "robot_description", KDL::Vector{-0.2, 0.5, 0.0}, true);

        if (!ik_manager_->initialize())
        {
            RCLCPP_FATAL(this->get_logger(), "Failed to initialize TRAC-IK for %s", tip_link_.c_str());
            return;
        }
    }

    void generate_point_cloud()
    {
        if (!ik_manager_)
        {
            RCLCPP_ERROR(this->get_logger(), "IK Manager not initialized!");
            return;
        }

        // Workspace definition (meters)
        double xmin = -0.5, xmax = 0.5;
        double ymin = 0.0, ymax = 1.0;
        double zmin = -0.5, zmax = 0.5;
        double step = 0.10; // 10 cm resolution

        // Write simple PLY header (ASCII point cloud)
        size_t nx = static_cast<size_t>((xmax - xmin) / step) + 1;
        size_t ny = static_cast<size_t>((ymax - ymin) / step) + 1;
        size_t nz = static_cast<size_t>((zmax - zmin) / step) + 1;
        total_points_ = nx * ny * nz;

        RCLCPP_INFO(this->get_logger(), "Sampling a grid of %zu points.", total_points_);

        size_t iter = 0;

        for (double x = xmin; x <= xmax && rclcpp::ok(); x += step)
        {
            for (double y = ymin; y <= ymax && rclcpp::ok(); y += step)
            {
                for (double z = zmin; z <= zmax && rclcpp::ok(); z += step)
                {
                    iter++;

                    // Pose with identity orientation
                    KDL::Frame pose(KDL::Rotation::Identity(), KDL::Vector(x, y, z));

                    KDL::JntArray q_out;

                    if (ik_manager_->compute_ik(pose, q_out))
                    {
                        points_.push_back(Eigen::Vector3f(x, y, z));
                        RCLCPP_INFO(this->get_logger(), "Reachable point nr. %zu!", points_.size());
                    }

                    // Throttled progress log every 10000 ms
                    double progress = 100.0 * static_cast<double>(iter) / total_points_;
                    RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 10000,
                                         "Progress: %.1f%%", progress);
                }
            }
        }

        save_pointcloud();
    }

private:
    std::unique_ptr<TracIKManager> ik_manager_;

    std::string base_link_;
    std::string tip_link_;

    std::vector<Eigen::Vector3f> points_;
    size_t total_points_;

    void save_pointcloud()
    {
        // Write PLY header
        std::ofstream outfile("pointcloud.ply");
        outfile << "ply\nformat ascii 1.0\n";
        outfile << "element vertex " << points_.size() << "\n";
        outfile << "property float x\nproperty float y\nproperty float z\n";
        outfile << "end_header\n";

        // Write the points
        for (const auto &p : points_)
        {
            outfile << p.x() << " " << p.y() << " " << p.z() << "\n";
        }

        outfile.close();

        RCLCPP_INFO(this->get_logger(),
                    "Reachability map written with %zu reachable points (out of %zu sampled).",
                    points_.size(), total_points_);
    }
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
