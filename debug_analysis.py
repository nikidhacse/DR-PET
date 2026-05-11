import sys
import os
import asyncio

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from vision_engine import DrPetVisionEngine
from acoustic_engine import DrPetAcousticEngine
from memory_engine import DrPetMemoryEngine

async def debug():
    vision = DrPetVisionEngine()
    acoustic = DrPetAcousticEngine()
    
    video_dir = "data/uploads"
    videos = [f for f in os.listdir(video_dir) if f.endswith(".mp4")]
    
    if not videos:
        print("No videos found in data/uploads")
        return
        
    test_video = os.path.join(video_dir, videos[0])
    print(f"DEBUG: Analyzing {test_video}")
    
    print("\n--- VISION ANALYSIS ---")
    v_results = vision.process_video(test_video, "debug_id")
    print(v_results)
    
    print("\n--- ACOUSTIC ANALYSIS ---")
    a_results = acoustic.analyze_audio(test_video)
    print(a_results)

if __name__ == "__main__":
    asyncio.run(debug())
