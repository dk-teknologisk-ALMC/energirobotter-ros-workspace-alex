import open3d as o3d
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
import sensor_msgs_py.point_cloud2 as pc2


class PointCloudPublisher(Node):
    def __init__(self, ply_file: str):
        super().__init__("pointcloud_publisher")
        self.publisher_ = self.create_publisher(PointCloud2, "reachability_cloud", 10)

        # Load PLY with Open3D
        pcd = o3d.io.read_point_cloud(ply_file)
        points = np.asarray(pcd.points, dtype=np.float32)

        # Convert to PointCloud2
        from std_msgs.msg import Header

        header = Header()
        header.stamp = self.get_clock().now().to_msg()
        header.frame_id = "map"
        msg = pc2.create_cloud_xyz32(header, points.tolist())

        self.publisher_.publish(msg)
        self.get_logger().info(f"Published point cloud with {len(points)} points")


def main(args=None):
    rclpy.init(args=args)
    node = PointCloudPublisher("cube_corners.ply")
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()
