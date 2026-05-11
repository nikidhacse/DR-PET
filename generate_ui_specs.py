import os
import requests
from bs4 import BeautifulSoup
from google import genai

api_key = "AIzaSyC-34qtLSDjt7bICc8Q1DjtbHunYSQceJw"
client = genai.Client(api_key=api_key)

img1 = r"C:\Users\asus\OneDrive\Desktop\Screenshot 2026-03-09 100700.png"
img2 = r"C:\Users\asus\OneDrive\Desktop\WhatsApp Image 2026-03-09 at 10.05.35 AM.jpeg"
pin_url = "https://pin.it/5sR3bt72E"

img3_path = None
try:
    print(f"Fetching Pinterest URL: {pin_url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(pin_url, headers=headers, allow_redirects=True)
    soup = BeautifulSoup(res.text, 'html.parser')
    og = soup.find("meta", property="og:image")
    if og:
        img_data = requests.get(og["content"]).content
        img3_path = "pin_login.jpg"
        with open(img3_path, "wb") as f:
            f.write(img_data)
        print("Successfully downloaded Pinterest image.")
    else:
        print("Missing og:image in Pinterest HTML.")
except Exception as e:
    print(f"Failed to fetch PIN: {e}")

files = []
for p in [img1, img2, img3_path]:
    if p and os.path.exists(p):
        print(f"Uploading {p}...")
        try:
            files.append(client.files.upload(file=p))
        except Exception as e:
            print(f"Upload failed for {p}: {e}")

prompt = """
You are an elite Frontend Architect. Read the images in the following order:
Image 1: Design language dictating the color tone for the whole website. Extract exact HEX background colors, panel/card colors, text colors, gradients, and accent colors.
Image 2: The exact Analysis UI that must be implemented. Describe the layout structure (grids/flexbox), panel styling, charts, progress bars, typography hierarchy, and any specific visual cues.
Image 3: The login page design. Describe the complete layout (left/right split or centered?), input fields (borders, padding, border-radius, background), buttons, color palette precisely for this section, login specific visual effects (glassmorphism/gradients), and typography.

Return a highly actionable and structured Frontend Technical Spec for recreating this in pure HTML and vanilla CSS. Give me exact HEX values, border radius estimates, padding estimates, and layout recommendations.
"""

print("Generating AI Analysis...")
try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=files + [prompt]
    )
    print("\n--- FRONTEND SPECIFICATION ---")
    with open("ui_specs.md", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("Specs written to ui_specs.md")
except Exception as e:
    print(f"AI Generation Failed: {e}")

for f in files:
    try:
        client.files.delete(name=f.name)
    except: pass
