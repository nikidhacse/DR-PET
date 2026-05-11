from ultralytics import YOLO
import torch

try:
    print("Attempting to load YOLOv8n-pose...")
    model = YOLO("yolov8n-pose.pt")
    print("Model loaded successfully!")
    import numpy as np
    img = np.zeros((640, 640, 3), dtype=np.uint8)
    results = model(img)
    print("Inference successful!")
except Exception as e:
    print(f"Error: {e}")
