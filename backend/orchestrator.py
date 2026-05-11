import os
import json
import time
import asyncio
from logger import get_logger
from vision_engine import DrPetVisionEngine
from acoustic_engine import DrPetAcousticEngine
from memory_engine import DrPetMemoryEngine
from llm_engine import DrPetLLMCoachingAgent
from pdf_export import DrPetClinicalAudit

logger = get_logger("Orchestrator")

class AnalysisOrchestrator:
    def __init__(self):
        # Initialize engines cleanly
        self.vision_engine = DrPetVisionEngine()
        self.acoustic_engine = DrPetAcousticEngine()
        self.memory_engine = DrPetMemoryEngine()
        self.llm_agent = DrPetLLMCoachingAgent()
        
        self.results_dir = "data/results"
        os.makedirs(self.results_dir, exist_ok=True)

    async def run_analysis_pipeline(self, file_path: str, file_id: str, 
                                     user_id: str = None, pet_id: str = None, pet_name: str = "Unknown Pet"):
        """
        Orchestrates the full multi-modal AI pipeline.
        """
        result_file = os.path.join(self.results_dir, f"{file_id}.json")
        try:
            logger.info(f"Starting Pipeline for file {file_id} | Pet: {pet_name}")
            start_time = time.time()
            
            # --- STAGE 1 & 2: CONCURRENT MULTI-MODAL INFERENCE ---
            loop = asyncio.get_event_loop()
            
            # 1. Vision Hub (Multi-Pet detection + track initialization)
            vision_task = asyncio.to_thread(self.vision_engine.process_video, file_path, file_id)
            
            # 2. Acoustic Hub (Localizes vocal sentiment for the scene)
            acoustic_task = asyncio.to_thread(self.acoustic_engine.analyze_audio, file_path)
            
            # 3. LLM Vision (Global scene understanding / Narrative)
            ai_task = self.llm_agent.analyze_video_ai(file_path)
            
            vision_results, acoustic_results, ai_analysis = await asyncio.gather(
                vision_task, acoustic_task, ai_task
            )

            if "error" in vision_results:
                logger.error(f"Vision error in pipeline: {vision_results['error']}")
                return

            detected_pets = vision_results.get("pets", [])
            vocal_sentiment = acoustic_results.get("vocal_sentiment", "Stable")
            vocal_conf = acoustic_results.get("confidence", 0.0)

            # --- STAGE 3: INDIVIDUAL PET PROCESSING LOOP (Deterministic Fusion) ---
            pet_summaries = []
            
            # Fetch global insights
            global_ai_state = ai_analysis.get("emotional_state", "UNCERTAIN")
            global_ai_breed = ai_analysis.get("pet_type", "General Pet")
            
            for pet in detected_pets:
                pid = pet["pet_id"]
                yolo_type = pet["animal"]
                
                # --- SENSORY FUSION INPUTS ---
                v_state = pet.get("vision_state", "UNCERTAIN")
                v_vigor = pet["metrics"]["motion_vigor"]
                a_state = vocal_sentiment
                l_state = global_ai_state
                
                # --- SENSORY FUSION LOGIC (WEIGHTED CONSENSUS) ---
                # Weighting: LLM(0.4), Vision(0.3), Audio(0.3)
                final_state = "UNCERTAIN"
                
                # Rule 1: High-Confidence Dissonance Check
                # If audio is aggressive but vision/LLM is happy, we default to defensive for safety.
                if "Defensive" in a_state and ("Affiliative" in l_state or "Relaxed" in l_state):
                    final_state = "Potential DANGER / Stress Conflict"
                    logger.warning(f"FUSION DISSONANCE for {pid}: Audio reports aggression, LLM reports calm.")
                
                # Rule 2: Consensus Scoring
                score_map = {
                    "Relaxed": 0,
                    "Playful": 0,
                    "Anxious": 0,
                    "Defensive": 0,
                    "Pain": 0
                }
                
                # Apply weights
                weights = {"LLM": 0.4, "Vision": 0.3, "Audio": 0.3}
                for component, state, weight in [("LLM", l_state, weights["LLM"]), ("Vision", v_state, weights["Vision"]), ("Audio", a_state, weights["Audio"])]:
                    # Map the raw state string into our 5 core buckets
                    core_bucket = None
                    s_lower = state.lower()
                    if "relax" in s_lower or "content" in s_lower or "stable" in s_lower: core_bucket = "Relaxed"
                    elif "playful" in s_lower or "excit" in s_lower or "affiliative" in s_lower: core_bucket = "Playful"
                    elif "anxious" in s_lower or "stress" in s_lower or "aroused" in s_lower or "fear" in s_lower: core_bucket = "Anxious"
                    elif "aggress" in s_lower or "react" in s_lower or "defensive" in s_lower: core_bucket = "Defensive"
                    elif "pain" in s_lower or "discomfort" in s_lower or "suppress" in s_lower or "sick" in s_lower: core_bucket = "Pain"
                    
                    if core_bucket:
                        score_map[core_bucket] += weight
                
                # Winner takes all
                if max(score_map.values()) >= 0.3:
                    final_state = max(score_map, key=score_map.get)
                else:
                    # If no clear winner, use LLM or mark insecure
                    final_state = l_state if l_state != "UNCERTAIN" else "OBSERVE - LOW CONFIDENCE"

                # Debug Logging for Fusion
                print(f"DEBUG [FUSION]: {pid} Decision:")
                print(f"  -> Vision: {v_state}")
                print(f"  -> Audio: {a_state}")
                print(f"  -> LLM: {l_state}")
                print(f"  -> FINAL DECISION: {final_state}")

                # Enrichment via Memory & RAG
                rag_context = await asyncio.to_thread(self.memory_engine.get_rag_context, breed=global_ai_breed, behavior_state=final_state)
                
                behavior_snapshot = {
                    "pet_id": pid,
                    "animal": yolo_type,
                    "breed": global_ai_breed,
                    "behavior_description": ai_analysis.get("behavior_description", ""),
                    "behavioral_signals": ai_analysis.get("behavioral_signals", []),
                    "clinical_evidence": ai_analysis.get("clinical_evidence", []),
                    "metrics": {
                        "primary_behavior": final_state,
                        "confidence_score": pet["confidence"],
                        "vocal_context": vocal_sentiment,
                        "fusion_reasoning": f"Consensus score: {max(score_map.values()):.2f}",
                        "tail_wag": pet["metrics"]["tail_wag_frequency"]
                    },
                    "rag_insight": rag_context
                }

                # Generate Per-Pet Coaching Strategies
                coaching_plan = await self.llm_agent.generate_rag_report(behavior_snapshot, rag_context)
                
                pet_summaries.append({
                    "pet_data": behavior_snapshot,
                    "coaching_plan": coaching_plan
                })

            # --- STAGE 4: AGGREGATION & REPORT GENERATION ---
            primary_pet = pet_summaries[0] if pet_summaries else None
            
            final_output = {
                "file_id": file_id,
                "timestamp": time.time(),
                "scene_summary": ai_analysis.get("behavior_description", "Complete."),
                "vocal_data": acoustic_results,
                "individual_pets": pet_summaries,
                "breed_card": primary_pet["coaching_plan"].get("breed_card") if primary_pet else None,
                "total_animals_detected": len(pet_summaries),
                "data_fidelity": "Scientific (Detect-Crop-Classify)",
                "status": "completed",
                # Lift primary results to root for frontend JS compatibility
                "analysis": primary_pet["coaching_plan"]["message"] if primary_pet else "No subjects identified.",
                "recommendations": primary_pet["coaching_plan"]["care_methods"] if primary_pet else [],
                "temporal_intelligence": {"is_anomaly": False, "message": "Baseline lookup in progress.", "deviation_score": "0%"},
                "metrics": {
                    "happiness_score": ai_analysis.get("happiness_score", 65) if primary_pet else 0,
                    "tail_wag_frequency": primary_pet["pet_data"]["metrics"]["tail_wag"] if primary_pet else "0 Hz",
                    "acoustic_sentiment": vocal_sentiment,
                    "fft_peaks": acoustic_results.get("fft_peaks", [])
                },
                "ai_insights": {
                    "emotional_state": primary_pet["coaching_plan"]["state"] if primary_pet else "None",
                    "key_points": ai_analysis.get("clinical_evidence", []) if primary_pet else []
                }
            }

            # Generate consolidated Clinical Audit (PDF)
            pdf_engine = DrPetClinicalAudit()
            await asyncio.to_thread(pdf_engine.generate_pdf, file_id, final_output)
            final_output["clinical_audit_url"] = f"/download/report/{file_id}"

            # Persist results
            with open(result_file, "w") as f:
                json.dump(final_output, f)

            logger.info(f"Pipeline completed for {file_id} — {len(pet_summaries)} subjects detected.")

            # Save to user history if authenticated
            if user_id:
                try:
                    from auth import save_analysis
                    save_analysis(
                        user_id=user_id,
                        pet_id=pet_id or "",
                        pet_name=pet_name,
                        analysis_type="video",
                        emotional_state=final_output.get("ai_insights", {}).get("emotional_state", "Unknown"),
                        happiness_score=final_output.get("metrics", {}).get("happiness_score", 50),
                        summary=final_output.get("analysis", ""),
                        recommendations=final_output.get("recommendations", [])
                    )
                    logger.info(f"Analysis saved to history for user {user_id}")
                except Exception as hist_e:
                    logger.error(f"History save failed: {hist_e}")

            # Privacy cleanup
            try:
                os.remove(file_path)
            except: pass

        except Exception as e:
            logger.error(f"CRITICAL PIPELINE FAILURE for {file_id}: {e}", exc_info=True)
            # Write error result so the frontend polling stops instead of looping forever
            error_output = {
                "file_id": file_id,
                "status": "error",
                "analysis": "Analysis failed. Please try again with a clearer video.",
                "recommendations": ["Ensure good lighting", "Keep pet in frame", "Use a 10-30 second clip"],
                "metrics": {"happiness_score": 0, "acoustic_sentiment": "Error", "fft_peaks": []},
                "ai_insights": {"emotional_state": "Analysis Error", "key_points": [str(e)]},
                "temporal_intelligence": {"is_anomaly": False, "message": "Error"}
            }
            try:
                with open(result_file, "w") as f:
                    json.dump(error_output, f)
            except: pass

