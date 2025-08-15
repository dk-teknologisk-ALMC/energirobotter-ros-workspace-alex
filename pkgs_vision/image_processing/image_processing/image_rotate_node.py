#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage
from cv_bridge import CvBridge
import cv2
import numpy as np


class ImageRotateNode(Node):
    def __init__(self):
        super().__init__("image_rotate_node")

        # Parameters
        self.declare_parameter("rotation", 0.0)  # degrees
        self.rotation_deg = (
            self.get_parameter("rotation").get_parameter_value().double_value
        )

        self.declare_parameter("use_compressed", False)
        self.use_compressed = (
            self.get_parameter("use_compressed").get_parameter_value().bool_value
        )

        # Subscriptions
        if self.use_compressed:
            self.subscription = self.create_subscription(
                CompressedImage, "/image", self.image_callback, 10
            )
        else:
            self.subscription = self.create_subscription(
                Image, "/image", self.image_callback, 10
            )

        # Publishers
        if self.use_compressed:
            self.image_pub = self.create_publisher(CompressedImage, "/image_rotated", 1)
        else:
            self.image_pub = self.create_publisher(Image, "/image_rotated", 1)

        self.cv_bridge = CvBridge()

    def image_callback(self, msg):
        # Convert ROS image to OpenCV

        if self.use_compressed:
            cv_image = self.cv_bridge.compressed_imgmsg_to_cv2(
                msg, desired_encoding="rgb8"
            )
        else:
            cv_image = self.cv_bridge.imgmsg_to_cv2(msg, desired_encoding="rgb8")

        h, w = cv_image.shape[:2]

        # Compute rotation matrix
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, self.rotation_deg, 1.0)

        # Compute bounding box after rotation
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))

        # Adjust rotation matrix to keep center
        M[0, 2] += (w / 2) - new_w / 2
        M[1, 2] += (h / 2) - new_h / 2

        # Rotate image
        rotated = cv2.warpAffine(cv_image, M, (new_w, new_h))

        # Crop or resize back to original size
        start_x = (rotated.shape[1] - w) // 2
        start_y = (rotated.shape[0] - h) // 2
        cropped = rotated[start_y : start_y + h, start_x : start_x + w]

        # Convert back to ROS Image and publish
        if self.use_compressed:
            rotated_msg = self.cv_bridge.cv2_to_compressed_imgmsg(cropped)
        else:
            rotated_msg = self.cv_bridge.cv2_to_imgmsg(cropped, encoding="rgb8")

        rotated_msg.header = msg.header
        self.image_pub.publish(rotated_msg)


def main(args=None):
    rclpy.init(args=args)

    node_handle = ImageRotateNode()
    rclpy.spin(node_handle)
    node_handle.destroy_node()

    rclpy.shutdown()


if __name__ == "__main__":
    main()
