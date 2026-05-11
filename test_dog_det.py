from ultralytics import YOLO
import cv2

model = YOLO("yolov8n.pt") # Standard detection model
results = model.predict(source="https://ultralytics.com/images/bus.jpg", classes=[16]) # 16 is dog in COCO
print(f"Detected {len(results[0].boxes)} dogs")
