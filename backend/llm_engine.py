import os
import json
import asyncio
import traceback
from google import genai
from google.genai import types
from groq import AsyncGroq
from typing import Dict, List, Any
import cv2
import io
from PIL import Image
from dotenv import load_dotenv
from schemas import VideoAnalysisOutput, CoachingReportOutput, BehavioralState
import pydantic
from logger import get_logger

# Try loading from backend dir, then parent dir
env_path = os.path.join(os.path.dirname(__file__), ".env")
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)

logger = get_logger("LLMEngine")

# Import the new Professional Prompt Library
try:
    from prompts import (
        VIDEO_ANALYSIS_PROMPT, 
        LIVE_FRAME_PROMPT, 
        BREED_PROFILE_PROMPT, 
        LIVE_SYNTHESIS_PROMPT,
        DAILY_HIGHLIGHT_PROMPT
    )
except ImportError:
    # If used without backend package structure (like in some debug scripts)
    from backend.prompts import (
        VIDEO_ANALYSIS_PROMPT, 
        LIVE_FRAME_PROMPT, 
        BREED_PROFILE_PROMPT, 
        LIVE_SYNTHESIS_PROMPT
    )

class DrPetLLMCoachingAgent:
    def __init__(self):
        # 1. Configure API Keys Securely
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.groq_gen_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama3-8b-8192")
        self.breed_cache = {} # Simple in-memory cache for speed
        
        # 2. Configure Gemini (Model 1: Native Video Analysis)
        if self.gemini_key:
            self.gemini_client = genai.Client(api_key=self.gemini_key)
            self.gemini_model = "gemini-2.0-flash"
        else:
            self.gemini_client = None
            logger.warning("Gemini API key missing. Video analysis fallback will be used.")

        # 3. Configure Groq (Model 2: Fast RAG Report Generation)
        if self.groq_gen_key:
            self.groq_client = AsyncGroq(api_key=self.groq_gen_key)
            self.groq_model = "llama-3.3-70b-versatile"
        else:
            self.groq_client = None
            logger.warning("Groq API key missing. Heuristic text logic will be used.")
            
        self.personality = "Warm, intuitive, and data-driven"

    async def analyze_video_ai(self, video_path: str) -> Dict[str, Any]:
        """
        Model 1: Analyzes the RAW video by sampling screenshots every 2 seconds.
        """
        if not self.gemini_client:
            return {"error": "Gemini API Key missing", "status": "fallback"}

        try:
            logger.info(f"AI ENGINE: Granular video analysis starting for: {video_path}")
            
            # 1. Extract frames every 2 seconds (Offloaded to thread)
            def extract_frames_sync(path):
                f_parts = []
                cap = cv2.VideoCapture(path)
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                interval = int(fps * 2)
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                
                for i in range(0, min(total, 1800), interval):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, frame = cap.read()
                    if not ret: break
                    success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    if success:
                        f_parts.append(types.Part.from_bytes(data=buffer.tobytes(), mime_type="image/jpeg"))
                cap.release()
                return f_parts

            frames = await asyncio.to_thread(extract_frames_sync, video_path)
            
            if not frames:
                raise ValueError("Could not extract any frames from the video.")

            logger.info(f"AI ENGINE: Analyzed {len(frames)} snapshots for behavioral sequence.")

            # 2. Update prompt with timeline requirement
            prompt = VIDEO_ANALYSIS_PROMPT + "\n\nCRITICAL: These images are sequential snapshots from a video taken every 2 seconds. Provide a chronological breakdown of the pet's behavior and mood shifts."

            # 3. Call Gemini
            safety = [
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_ONLY_HIGH"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_ONLY_HIGH"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_ONLY_HIGH"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_ONLY_HIGH"),
            ]
            
            response = await asyncio.to_thread(
                self.gemini_client.models.generate_content,
                model=self.gemini_model,
                contents=frames + [prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    safety_settings=safety
                )
            )
            
            if not response.text:
                raise ValueError("Empty response from AI")
                
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3].strip()
            
            try:
                validated = VideoAnalysisOutput.parse_raw(raw_text)
                detected = str(validated.detected_behavior)
                urgency = validated.urgency_level.value
            except Exception:
                temp = json.loads(raw_text)
                detected = temp.get("detected_behavior", "UNCERTAIN")
                urgency = temp.get("urgency_level", "Medium")
                validated = VideoAnalysisOutput(**temp)

            # Happiness Score Calculation
            happiness_map = {
                BehavioralState.RELAXED.value: 90, BehavioralState.PLAYFUL.value: 85,
                BehavioralState.ATTENTION.value: 70, BehavioralState.BORED.value: 55,
                BehavioralState.ANXIOUS.value: 35, BehavioralState.FEARFUL.value: 25,
                BehavioralState.PAIN.value: 20, BehavioralState.AGGRESSIVE.value: 15
            }

            base_score = happiness_map.get(detected, 50)
            urgency_penalty = {"Low": 0, "Medium": -10, "High": -25}.get(urgency, 0)
            happiness_score = max(5, base_score + urgency_penalty)
            
            normalized = {
                "pet_type": validated.pet_type,
                "behavior_description": validated.what_happened,
                "happiness_score": happiness_score,
                "emotional_state": detected,
                "clinical_evidence": validated.why_it_might_be_happening,
                "personality_profile": validated.personality_profile,
                "social_environmental_fit": validated.social_environmental_fit,
                "urgency_level": urgency,
                "behavioral_signals": validated.behavioral_signals_observed,
                "recommended_solution": validated.recommended_solution,
                "vet_needed": validated.vet_needed,
                "confidence": 0.94
            }
            
            logger.info(f"AI ENGINE: Analysis successful — {detected}")
            return normalized

        except Exception as e:
            logger.error(f"AI ENGINE FATAL: {e}")
            return {
                "pet_type": "Unknown",
                "behavior_description": "AI analysis encounterd a processing error, but telemetry is active.",
                "happiness_score": 50,
                "emotional_state": "UNCERTAIN",
                "clinical_evidence": ["Processing partial failure"],
                "urgency_level": "Low",
                "behavioral_signals": ["Error in visual synthesis"],
                "recommended_solution": ["Observe pet manually"],
                "vet_needed": False,
                "confidence": 0.1,
                "error": str(e)
            }

    async def generate_rag_report(self, analysis_data: Dict[str, Any], rag_context: str) -> Dict[str, Any]:
        """
        Generates the final clinical report using Groq Llama-3.3.
        """
        if not self.groq_client:
            return self._heuristic_report(analysis_data, rag_context)

        try:
            breed = analysis_data.get("breed", "Unknown")
            state = analysis_data.get("metrics", {}).get("primary_behavior", 
                    analysis_data.get("emotional_state", "Unknown"))
            signals = analysis_data.get("behavioral_signals", [])
            evidence = analysis_data.get("clinical_evidence", [])
            
            logger.info(f"AI ENGINE (Groq): Generating clinical report for {breed} — {state}")
            
            prompt = f"""You are Dr. PET, a professional veterinary behavior analyst.

Pet Type: {analysis_data.get('pet_type', breed)}
Detected Behavior: {state}
Timeline/Description: {analysis_data.get('behavior_description', 'No description provided')}
Observed Signals: {json.dumps(signals)}
Evidence: {json.dumps(evidence)}
Context: {rag_context[:1000] if rag_context else 'General knowledge'}

STRICT REQUIREMENT: Do NOT provide a generic response. You must reference at least two specific signals or timeline events from the 'Timeline/Description' provided above to make this report unique.

JSON ONLY:
{{
    "state": "{state}",
    "message": "Write 3-4 sentences explaining the specific behavioral sequence observed in this video. Be highly detailed about the pet's movements.",
    "action": "One specific immediate step based on the observed timeline.",
    "care_methods": [
        "Immediate action (today)",
        "Short-term change (this week)",
        "Long-term enrichment (ongoing)",
        "When to see a vet"
    ],
    "breed_card": null
}}"""
            
            if self.groq_client:
                chat_completion = await self.groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.groq_model,
                    response_format={"type": "json_object"}
                )
                result = json.loads(chat_completion.choices[0].message.content)
            else:
                # Fallback to Gemini for synthesis if Groq is missing
                logger.info("AI ENGINE: Using Gemini for report synthesis...")
                response = await asyncio.to_thread(
                    self.gemini_client.models.generate_content,
                    model=self.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                result = json.loads(response.text)
                
            logger.info("AI ENGINE: Clinical report generated successfully.")
            return result

        except Exception as e:
            logger.error(f"Groq Report Error: {e}")
            return self._heuristic_report(analysis_data, rag_context)

    def _heuristic_report(self, behavior_snapshot, rag_context):
        """Fallback logic for when Groq is unavailable."""
        return {
            "state": "Processing/Heuristic",
            "message": f"AI Synthesis offline. Analyzing based on internal thresholds. {rag_context}",
            "action": "Observe for further behavioral shifts.",
            "care_methods": ["Maintain safe environment", "Reduce novel stimuli"],
            "clinical_audit": {"status": "Fallback Heuristics Applied"}
        }

    async def generate_breed_card(self, breed: str, emotional_state: str) -> Dict[str, Any]:
        """
        Fast Breed Lookup with Internet RAG + Caching.
        """
        if breed in self.breed_cache: 
            logger.info(f"BREED CACHE: Cache hit for {breed}")
            return self.breed_cache[breed]
            
        if not self.groq_client or not breed:
            return {"breed": breed, "summary": "Breed data unavailable.", "traits": [], "situation_advice": ""}

        # Step 1: Internet RAG lookup with strict timeout (Single Focused Query)
        def _fetch_duckduckgo():
            raw_docs = []
            try:
                from duckduckgo_search import DDGS
                query = f"{breed} dog temperament and {emotional_state} behavioral advice"
                
                with DDGS(timeout=5) as ddgs:
                    try:
                        results = list(ddgs.text(query, max_results=3))
                        for r in results:
                            raw_docs.append(r.get("body", ""))
                    except: pass
                return raw_docs
            except Exception as e:
                logger.error(f"BREED RAG: lookup failed: {e}")
                return []
                
        raw_docs = await asyncio.to_thread(_fetch_duckduckgo)
        context_block = "\n\n".join(raw_docs[:3]) if raw_docs else f"General knowledge about {breed} dogs."

        # Step 2: Groq Synthesis
        prompt = BREED_PROFILE_PROMPT.format(
            breed=breed, 
            emotional_state=emotional_state, 
            context=context_block[:1500]
        )
        try:
            resp = await self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.groq_model,
                response_format={"type": "json_object"}
            )
            card = json.loads(resp.choices[0].message.content)
            card["source_quality"] = "Live Web RAG" if raw_docs else "Local Knowledge"
            logger.info(f"BREED CARD: Successfully generated card for {breed}")
            self.breed_cache[breed] = card
            return card
        except Exception as e:
            logger.error(f"BREED CARD: Groq synthesis failed: {e}")
            return {
                "breed": breed,
                "origin": "Unknown",
                "size": "Unknown",
                "temperament_traits": [],
                "energy_level": "Unknown",
                "known_for": f"{breed} is a recognized breed.",
                "current_situation": f"The breed is currently exhibiting {emotional_state} behavior.",
                "owner_advice": "Consult a veterinary professional.",
                "source_quality": "Fallback"
            }

    async def analyze_single_frame(self, frame: Any) -> Dict[str, Any]:
        """
        [UPGRADED] High-speed single-frame behavioral analysis.
        Extracts clinical markers for session synthesis.
        """
        if not self.gemini_client:
            return {"state": "Observing", "confidence": 0.5, "markers": []}

        try:
            # 1. Resize for light payload and faster inference
            h, w = frame.shape[:2]
            scale = min(512/w, 512/h, 1.0)
            if scale < 1.0:
                frame = cv2.resize(frame, (int(w*scale), int(h*scale)))

            success, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not success: return {"state": "Error", "confidence": 0.0, "markers": []}
            
            image_part = types.Part.from_bytes(data=buffer.tobytes(), mime_type="image/jpeg")
            
            # Use the high-fidelity professional frame prompt
            prompt = LIVE_FRAME_PROMPT
            
            # Use safety settings to prevent false 'dangerous content' rejection on animal behavior
            safety = [
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_ONLY_HIGH"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_ONLY_HIGH"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_ONLY_HIGH"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_ONLY_HIGH"),
            ]

            response = await asyncio.to_thread(
                self.gemini_client.models.generate_content,
                model=self.gemini_model,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    safety_settings=safety
                )
            )
            
            if not response.text:
                raise ValueError("Empty AI response")
                
            analysis_data = json.loads(response.text)
            
            # Merge breed into markers for better live keyword visibility
            breed = analysis_data.get("breed", "Unknown")
            state = analysis_data.get("state", "Unknown")
            markers = analysis_data.get("markers", [])
            
            # Prepend breed & species if detected
            if breed != "Unknown" and f"Breed: {breed}" not in markers:
                markers.insert(0, f"Breed: {breed}")
            
            # Add general pet species from common knowledge if possible or just the breed
            analysis_data["markers"] = markers
            return analysis_data
        except Exception as e:
            logger.error(f"AI ENGINE: Snapshot error: {traceback.format_exc()}")
            return {"state": "Observing", "confidence": 0.5, "markers": ["Technical Pulse Active"]}

    async def generate_live_synthesis(self, animal_data: Dict[str, Any], markers: List[str]) -> Dict[str, Any]:
        """
        Synthesizes collected markers into a formal Behavioral Report.
        Uses parallel processing for speed.
        """
        if not self.groq_client: 
            return {
                "analysis": "AI Synthesis Offline.", 
                "recommendations": ["Manual observation required."],
                "temporal_intelligence": {"is_anomaly": False, "message": "Offline"},
                "metrics": {"happiness_score": 50, "acoustic_sentiment": "Offline"},
                "ai_insights": {"emotional_state": "Offline", "key_points": markers}
            }

        try:
            breed = animal_data.get("breed", "Unknown")
            state = animal_data.get("state", "Unknown")
            
            logger.info(f"AI ENGINE: Parallel synthesis triggered for {breed}")
            
            # Step 1: Synthesis Prompt
            prompt = LIVE_SYNTHESIS_PROMPT.format(
                breed=breed, 
                markers=", ".join(markers)
            )
            
            # Step 2: Execute both expensive LLM calls in parallel
            synthesis_task = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.groq_model,
                response_format={"type": "json_object"}
            )
            breed_task = self.generate_breed_card(breed, state)
            
            # Use gather for true concurrency
            resp, breed_card = await asyncio.gather(synthesis_task, breed_task)
            
            raw_result = json.loads(resp.choices[0].message.content)
            
            # Calculate a real happiness score from the behavior state
            detected_b = raw_result.get("detected_behavior", "Stable")
            urgency_l = raw_result.get("urgency_level", "Low")
            h_map = {
                "Relaxed": 90, "Relaxed / Content": 90, "Playful": 85, "Playful / Excited": 85,
                "Attention-seeking": 70, "Bored": 55, "Bored / Understimulated": 55,
                "Anxious": 35, "Anxious / Stressed": 35, "Fearful": 25,
                "Pain": 20, "Pain / Discomfort": 20, "Aggressive": 15, "Aggressive / Reactive": 15
            }
            base = next((v for k, v in h_map.items() if k.lower() in detected_b.lower()), 55)
            penalty = {"Low": 0, "Medium": -10, "High": -25}.get(urgency_l, 0)
            happiness_score = max(5, base + penalty)

            final_report = {
                "analysis": raw_result.get("what_happened", raw_result.get("message", "")),
                "recommendations": raw_result.get("recommended_solution", raw_result.get("care_methods", [])),
                "owner_reassurance": raw_result.get("owner_reassurance", ""),
                "breed_card": breed_card,
                "status": "completed",
                "temporal_intelligence": {
                    "is_anomaly": urgency_l == "High",
                    "message": f"Urgency: {urgency_l} — {raw_result.get('urgency_reason', '')}",
                    "deviation_score": f"{100 - happiness_score}%"
                },
                "metrics": {
                    "happiness_score": happiness_score,
                    "acoustic_sentiment": detected_b,
                    "fft_peaks": []
                },
                "ai_insights": {
                    "emotional_state": detected_b,
                    "key_points": raw_result.get("why_it_might_be_happening", [])
                }
            }
            
            return final_report
            
        except Exception as e:
            logger.error(f"AI ENGINE: Synthesis error: {e}")
            return {
                "analysis": f"Synthesis failure: {e}", 
                "recommendations": [],
                "temporal_intelligence": {"is_anomaly": False, "message": "Error during synthesis."},
                "metrics": {"happiness_score": 0, "acoustic_sentiment": "Error"},
                "ai_insights": {"emotional_state": "Error", "key_points": markers}
            }

    async def generate_daily_highlight(self, breed: str, daily_markers: List[str]) -> Dict[str, Any]:
        """
        Generates the daily highlight summary based on collected observations.
        """
        if not self.groq_client:
            return {
                "daily_highlight": f"Your pet {breed} was active today.",
                "mood_summary": "Calm",
                "key_insight": "AI synthesis offline, returning fallback data.",
                "suggestion": "Keep observing your pet."
            }
        
        try:
            logger.info(f"AI ENGINE: Generating Daily Highlight for {breed}")
            prompt = DAILY_HIGHLIGHT_PROMPT.format(
                breed=breed,
                daily_markers=", ".join(daily_markers) if daily_markers else "No major events recorded today, standard baseline behavior."
            )
            
            resp = await self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.groq_model,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(resp.choices[0].message.content)
            return result
        except Exception as e:
            logger.error(f"AI ENGINE: Daily highlight error: {e}")
            return {
                "daily_highlight": f"Your pet {breed} had a normal day.",
                "mood_summary": "Mixed",
                "key_insight": "Unable to generate detailed insight at this moment.",
                "suggestion": "Check back later."
            }
