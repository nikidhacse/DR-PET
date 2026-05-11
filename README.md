# Dr. PET (Prototype) - Multi-Modal Behavior Intelligence

![Dr. PET Vision Demo](dr_pet_vision_demo.png)

This is a prototype implementation of the **Vision Pipeline** for Dr. PET, focusing on extracting behavior metrics (like tail-wag frequency) from video clips using YOLOv8-pose architecture.


## 🚀 Getting Started

### 1. Backend Setup (FastAPI)
Navigate to the root directory and install dependencies:
```bash
pip install -r requirements.txt
```

Run the FastAPI server:
```bash
python backend/main.py
```
The backend will be available at `http://localhost:8000`.

### 2. Frontend Setup
Simply open `frontend/index.html` in any modern web browser. 

The frontend provides:
- **Video Upload**: Deep integration for behavior analysis.
- **Glassmorphism UI**: A premium, data-rich dashboard.
- **Real-time Metrics**: Behavioral state classification, Happiness scores, and Tail-wag frequency charts.

## 🧠 Architecture Highlights
- **Computer Vision**: Uses YOLOv8 (specifically `yolov8n-pose.pt` as base) to track pet posture.
- **Micro-Agentic Pipeline**: Backend processes video in background tasks, allowing for low-latency user response.
- **Heuristic Engine**: Converts raw spatial coordinates into behavioral tokens (e.g., oscillating tail tip -> Happiness Score).

## 🐾 Next Steps
1. **Model Fine-Tuning**: Train on the Stanford Dogs Pose dataset for higher precision.
2. **Audio Integration**: Add the Acoustic Intelligence layer using AST (Audio Spectrogram Transformer).
3. **Vet Integration**: Map the results to structured JSON for practice management systems.
