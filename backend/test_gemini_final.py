import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
import traceback

load_dotenv()

def test():
    key = os.getenv("GEMINI_API_KEY")
    print(f"Testing key: {key[:5]}...{key[-5:]}")
    
    client = genai.Client(api_key=key)
    model_name = "gemini-2.5-flash"
    
    try:
        print("Sending simple prompt to Gemini...")
        response = client.models.generate_content(
            model=model_name,
            contents="Say 'System Online' if you can hear me.",
            config=types.GenerateContentConfig(
                temperature=0.1
            )
        )
        print(f"Gemini Response: {response.text}")
        
        # Test safety settings construction
        print("Testing safety settings construction...")
        safety = [
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_ONLY_HIGH")
        ]
        print("Safety settings constructed successfully.")
        
    except Exception as e:
        print("FAILED!")
        print(traceback.format_exc())

if __name__ == "__main__":
    test()
