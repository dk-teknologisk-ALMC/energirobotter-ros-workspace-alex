# Object Detection

Object detection with YOLO from `/camera` topic. 

Download object detection model, and move it the model into the `models/` directory. 

**NOTE:** This package is not finished, and multiple features are missing: 
- Choosing model with ROS parameter
- Choosing inference method (Yolo or TensorRT) with ROS parameter
- Inference with TensorRT (optimised for Jetson. unfinished class for this in the `src/` folder)
- Dependency on `pycuda`
- Easy face detection, to eventually replace the `face_detection` package (which uses a specialised model, faster for faces, where this currently uses a more general model)
- Launch file in bringup


