import cv2
import numpy as np
import os
import time
from ultralytics import YOLO

class DrPetVisionEngine:
    def __init__(self, model_path="yolov8n.pt"):
        """
        Loads the standard YOLOv8 model for high-confidence pet detection.
        Classes: 16 (dog), 17 (cat), 18 (bird).
        """
        try:
            self.model = YOLO(model_path)
            print("Vision Engine successfully loaded YOLOv8 model for pet detection.")
        except Exception as e:
            print(f"Vision Engine failed to load model: {e}.")
            self.model = None

    def process_video(self, video_path, file_id):
        """
        Multi-Modal Behavioral Pipeline (Vision Hub):
        Analyzes video to extract movement vigor, tail-wag frequency, and pose tension.
        """
        if not os.path.exists(video_path):
            return {"error": "File not found"}

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return {"error": "Could not open video file"}

            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # --- STAGE 1: DETECTION & ROI TRACKING ---
            detected_pets = {} # pet_track_id -> {metadata}

            # Sample frames to find all pets
            sample_rate = 10 
            frames_processed = 0
            
            for i in range(0, min(total_frames, 900), sample_rate): # Process up to 900 frames (30s @ 30fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                if not ret: break
                frames_processed += 1

                if self.model:
                    results = self.model.predict(frame, classes=[0, 14, 15, 16], verbose=False)
                    for box in results[0].boxes:
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        
                        center = ((x1+x2)//2, (y1+y2)//2)
                        matched = False
                        for pid, pdata in detected_pets.items():
                            px, py = pdata["center"]
                            dist = ((px-center[0])**2 + (py-center[1])**2)**0.5
                            if dist < 150:
                                pdata["confs"].append(conf)
                                pdata["boxes"].append((x1, y1, x2, y2))
                                matched = True
                                break
                        
                        if not matched:
                            new_id = f"pet_{len(detected_pets)+1}"
                            detected_pets[new_id] = {
                                "type": "dog" if cls == 16 else "cat" if cls == 15 else "bird" if cls == 14 else "pet",
                                "confs": [conf],
                                "boxes": [(x1, y1, x2, y2)],
                                "center": center,
                                "tail_signal": [] # Horizontal flow in tail region
                            }

            # --- STAGE 2: MOTION TELEMETRY (Tail Wag & Vigor) ---
            # We revisit the video to extract high-frequency motion signals for each detected pet
            for pid, pdata in detected_pets.items():
                if not pdata["boxes"]: continue
                
                # Use the 'best' bounding box (median coordinates to avoid outliers)
                bboxes = np.array(pdata["boxes"])
                best_box = np.median(bboxes, axis=0).astype(int)
                x1, y1, x2, y2 = best_box
                
                # Heuristic: Tail is likely in the back 35% of the animal's bounding box
                # We assume standard horizontal camera view for now
                roi_w = x2 - x1
                roi_h = y2 - y1
                
                # Tail region candidates (left 35% or right 35%)
                tail_roi_left = (x1, y1, x1 + int(roi_w * 0.35), y2)
                tail_roi_right = (x2 - int(roi_w * 0.35), y1, x2, y2)
                
                signals_l = []
                signals_r = []
                
                prev_gray = None
                
                # Short analysis window (60 frames / 2 seconds) for motion extraction
                step = 1
                for i in range(0, min(total_frames, 300), step): # Analyze up to 10 seconds of motion
                    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, frame = cap.read()
                    if not ret: break
                    
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    if prev_gray is not None:
                        # Calculate Optical Flow in the whole ROI
                        roi_gray = gray[y1:y2, x1:x2]
                        prev_roi_gray = prev_gray[y1:y2, x1:x2]
                        
                        if roi_gray.shape == prev_roi_gray.shape:
                            flow = cv2.calcOpticalFlowFarneback(prev_roi_gray, roi_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                            
                            # Analyze horizontal motion (wagging) in tail candidates
                            # Side A (Left part of ROI)
                            flow_l = flow[:, :int(roi_w * 0.35), 0]
                            signals_l.append(np.mean(np.abs(flow_l)))
                            
                            # Side B (Right part of ROI)
                            flow_r = flow[:, -int(roi_w * 0.35):, 0]
                            signals_r.append(np.mean(np.abs(flow_r)))
                            
                    prev_gray = gray

                # Determine which side is the tail based on movement variance (wagging)
                var_l = np.var(signals_l) if signals_l else 0
                var_r = np.var(signals_r) if signals_r else 0
                
                active_signal = signals_l if var_l > var_r else signals_r
                
                # Calculate Frequency (Hz) using Zero-Crossing Rate as a robust proxy for short clips
                # A wag cycle is two crossings of the mean
                if len(active_signal) > 10:
                    mean_val = np.mean(active_signal)
                    zero_crossings = np.where(np.diff(np.sign(np.array(active_signal) - mean_val)))[0]
                    wag_freq = (len(zero_crossings) / 2.0) / (len(active_signal) / fps)
                else:
                    wag_freq = 0.0

                pdata["wag_frequency"] = round(min(wag_freq, 12.0), 1) # Cap at 12Hz for realism
                pdata["vigor"] = round(np.mean(active_signal), 2) if active_signal else 0

            cap.release()
            
            # --- STAGE 3: OUTPUT AGGREGATION & HEURISTICS ---
            results_payload = []
            for pid, pdata in detected_pets.items():
                vigor = pdata["vigor"]
                wag = pdata["wag_frequency"]
                
                # Deterministic Vision Heuristics
                # High vigor + Wagging = Affiliative/Playful
                # High vigor + No/Low Wagging = Hyper-Aroused or Defensive
                # Low vigor + No Wagging = Relaxed or Suppressed
                
                vision_state = "UNCERTAIN"
                if vigor > 3.0:
                    vision_state = "Hyper-Aroused / Anxious"
                elif vigor > 1.2:
                    vision_state = "Affiliative / Playful" if wag > 1.5 else "Hyper-Aroused"
                elif vigor < 0.2:
                    vision_state = "Relaxed / Equilibrium"
                else:
                    vision_state = "Stable / Observing"

                # Debug Logging for Vision
                print(f"DEBUG [VISION]: {pid} ({pdata['type']}) | Vigor: {vigor} | Wag: {wag}Hz | State: {vision_state}")

                results_payload.append({
                    "pet_id": pid,
                    "animal": pdata["type"],
                    "vision_state": vision_state,
                    "behavior": vision_state,
                    "confidence": round(float(np.mean(pdata["confs"])), 2),
                    "metrics": {
                        "tail_wag_frequency": f"{wag} Hz",
                        "motion_vigor": vigor,
                        "raw_vigor": vigor,
                        "raw_wag": wag
                    }
                })

            if not results_payload:
                return self._honest_error("No pets detected.")

            return {
                "pets": results_payload,
                "summary": {
                    "total_pets": len(results_payload),
                    "processing_time": f"{time.time()}s",
                    "status": "Telemetry Extraction Complete"
                }
            }

        except Exception as e:
            return self._honest_error(str(e))

    def process_frame(self, frame):
        """
        High-speed live inference with ROI extraction.
        """
        if self.model:
            results = self.model.predict(frame, classes=[0, 14, 15, 16], conf=0.15, verbose=False)
            if len(results[0].boxes) > 0:
                box = results[0].boxes[0]
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                label = "dog" if cls == 16 else "cat" if cls == 15 else "bird" if cls == 14 else "pet"
                
                return {
                    "pet_detected": True, 
                    "confidence": round(conf, 2), 
                    "type": label,
                    "behavior": "Observing",
                    "status": "LIVE-IDENTIFIED",
                    "bbox": (x1, y1, x2, y2)
                }
        return {"pet_detected": False, "confidence": 0.0, "type": "none", "behavior": "None", "bbox": None}

    def _honest_error(self, reason):
        return {"pets": [], "error": reason, "status": "Failed"}

