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
                msg, desired_encoding="bgr8"
            )
        else:
            cv_image = self.cv_bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

        # Rotate image by multiples of 90 degrees
        match self.rotation_deg:
            case 90:
                rotated = cv2.rotate(cv_image, cv2.ROTATE_90_CLOCKWISE)
            case 180:
                rotated = cv2.rotate(cv_image, cv2.ROTATE_180)
            case 270:
                rotated = cv2.rotate(cv_image, cv2.ROTATE_90_COUNTERCLOCKWISE)
            case _:
                # 0° or unsupported angle, keep original
                rotated = cv_image

        # Convert back to ROS Image and publish
        if self.use_compressed:
            rotated_msg = self.cv_bridge.cv2_to_compressed_imgmsg(rotated)
        else:
            rotated_msg = self.cv_bridge.cv2_to_imgmsg(rotated, encoding="bgr8")

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
