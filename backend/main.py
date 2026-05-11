import asyncio
import uvicorn
import shutil
import os
import uuid
import json
import time
import base64
import cv2
import numpy as np

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Header, Request, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

from orchestrator import AnalysisOrchestrator
from logger import get_logger
from auth import (
    init_db, register_user, login_user, get_user_by_token,
    get_user_pets, add_pet, delete_pet, save_analysis, get_analysis_history
)

logger = get_logger("DrPetAPI")

app = FastAPI(title="Dr. PET - Behavior Intelligence System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Global Response Structure & Middleware ────────────────────────────────────

def success_response(data: Any = None):
    return {"status": "success", "data": data, "error": None}

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP {exc.status_code} Error on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "data": None, "error": exc.detail}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "data": None, "error": "Internal Server Error"}
    )

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)")
    return response

# Init DB on startup
init_db()

orchestrator = AnalysisOrchestrator()

UPLOAD_DIR = "data/uploads"
RESULTS_DIR = "data/results"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

live_sessions: Dict[str, Dict] = {}

# ─── Pydantic Models ───────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AddPetRequest(BaseModel):
    name: str
    species: str
    breed: Optional[str] = ""
    age_years: Optional[float] = 0
    weight_kg: Optional[float] = 0
    avatar: Optional[str] = ""
    notes: Optional[str] = ""

class LiveSynthesisRequest(BaseModel):
    session_id: str
    pet_id: Optional[str] = None
    pet_name: Optional[str] = None

# ─── Auth Helper ───────────────────────────────────────────────────────────────

def get_current_user(authorization: str = Header(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user

# ─── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def root():
    return {"message": "Dr. PET Multi-Modal API", "status": "healthy"}

# ─── Auth Routes ───────────────────────────────────────────────────────────────

@app.post("/api/auth/register")
async def register(body: RegisterRequest):
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    result = register_user(body.name, body.email, body.password)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return success_response(result)

@app.post("/api/auth/login")
async def login(body: LoginRequest):
    result = login_user(body.email, body.password)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return success_response(result)

@app.get("/api/auth/me")
async def get_me(authorization: str = Header(None)):
    user = get_current_user(authorization)
    return user

# ─── Pet Routes ────────────────────────────────────────────────────────────────

@app.get("/api/pets")
async def list_pets(authorization: str = Header(None)):
    user = get_current_user(authorization)
    return success_response(get_user_pets(user["id"]))

@app.post("/api/pets")
async def create_pet(body: AddPetRequest, authorization: str = Header(None)):
    user = get_current_user(authorization)
    pet = add_pet(
        user_id=user["id"],
        name=body.name,
        species=body.species,
        breed=body.breed,
        age_years=body.age_years,
        weight_kg=body.weight_kg,
        avatar=body.avatar,
        notes=body.notes
    )
    return success_response(pet)

@app.delete("/api/pets/{pet_id}")
async def remove_pet(pet_id: str, authorization: str = Header(None)):
    user = get_current_user(authorization)
    success = delete_pet(user["id"], pet_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pet not found.")
    return success_response({"deleted": True})

# ─── History Routes ────────────────────────────────────────────────────────────

@app.get("/api/history")
async def get_history(authorization: str = Header(None)):
    user = get_current_user(authorization)
    history = get_analysis_history(user["id"])
    return success_response(history)

# ─── Analysis Routes ───────────────────────────────────────────────────────────

@app.post("/analyze/video")
async def analyze_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    authorization: str = Header(None),
    pet_id: Optional[str] = Form(None),
    pet_name: Optional[str] = Form("Unknown Pet")
):
    try:
        user = get_current_user(authorization)
    except HTTPException:
        user = {"id": None, "name": "Anonymous"}

    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    logger.info(f"Accepted upload {file.filename} -> assigned ID {file_id} for user {user.get('name')}")
    background_tasks.add_task(
        orchestrator.run_analysis_pipeline, file_path, file_id,
        user_id=user.get("id"), pet_id=pet_id, pet_name=pet_name
    )
    return success_response({"status": "processing", "file_id": file_id})

@app.get("/results/{file_id}")
async def get_results(file_id: str):
    result_path = os.path.join(RESULTS_DIR, f"{file_id}.json")
    if os.path.exists(result_path):
        with open(result_path, "r") as f:
            data = json.load(f)
        return success_response(data)
    return success_response({"status": "processing", "message": "Pipeline in progress..."})

# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket, node_id: str = "anonymous"):
    await websocket.accept()
    session_id = node_id
    
    if session_id not in live_sessions or not live_sessions[session_id].get("markers"):
        live_sessions[session_id] = {
            "markers": [],
            "last_snapshot": 0,
            "last_detection_time": 0,
            "last_known_type": "pet",
            "pet_breed": "Unknown",
            "primary_state": "Searching",
            "marker_threshold": 8
        }
    
    async def run_snapshot_analysis(frame_data, sess_id):
        try:
            # ROI extraction before sending to LLM for better focus
            target_img = frame_data
            sess = live_sessions.get(sess_id)
            if not sess: return
            
            snapshot = await orchestrator.llm_agent.analyze_single_frame(target_img)
            clean_markers = [m for m in snapshot.get("markers", []) if "Technical Pulse" not in m]
            
            sess["markers"].extend(clean_markers)
            sess["pet_breed"] = snapshot.get("breed", sess["pet_breed"])
            sess["primary_state"] = snapshot.get("state", "Active")
            
            # Send an out-of-band heartbeat update
            hb_payload = {
                "type": "live_update",
                "payload": {
                    "status": "active",
                    "session_id": sess_id,
                    "live_metrics": {"pet_detected": True, "type": sess["last_known_type"], "behavior": sess["primary_state"], "confidence": snapshot.get("confidence", 0.9)},
                    "heartbeat": {
                        "markers": clean_markers,
                        "is_ready": len(sess["markers"]) >= sess["marker_threshold"]
                    }
                }
            }
            await websocket.send_json(hb_payload)
        except Exception as e:
            logger.error(f"Async Snapshot Error: {e}")

    try:
        frame_count = 0
        while True:
            data = await websocket.receive_bytes()
            frame_count += 1
            
            # Skip frames for YOLO efficiency (process 1 in 2)
            if frame_count % 2 != 0:
                continue

            frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                live_update = orchestrator.vision_engine.process_frame(frame)
                current_time = time.time()
                session = live_sessions.get(session_id)
                if not session: continue

                if live_update.get("pet_detected"):
                    session["last_detection_time"] = current_time
                    session["last_known_type"] = live_update["type"]
                elif current_time - session.get("last_detection_time", 0) < 3.0:
                    live_update["pet_detected"] = True
                    live_update["type"] = session.get("last_known_type", "pet")
                    live_update["status"] = "PERSISTED-TRACKING"

                # Trigger Expensive AI in background task (every ~4s for responsive intelligence)
                if live_update.get("pet_detected") and (current_time - session["last_snapshot"] > 4):
                    session["last_snapshot"] = current_time
                    # FIRE AND FORGET - Don't await it here!
                    asyncio.create_task(run_snapshot_analysis(frame, session_id))

                # Immediate feedback from YOLO
                live_update["behavior"] = session["primary_state"]
                payload = {
                    "type": "live_update",
                    "payload": {
                        "status": "active",
                        "session_id": session_id,
                        "live_metrics": live_update,
                        "heartbeat": None # Markers come via async task
                    }
                }
                await websocket.send_json(payload)
                
    except WebSocketDisconnect:
        logger.info(f"Session {session_id} disconnected.")
    except Exception as e:
        logger.error(f"WS Error: {e}")

# ─── Live Synthesis ───────────────────────────────────────────────────────────

@app.post("/api/live/synthesis")
async def perform_synthesis(request: LiveSynthesisRequest, authorization: str = Header(None)):
    # Auth optional for remote mode
    user = None
    if authorization and authorization.startswith("Bearer "):
        user = get_user_by_token(authorization[7:])

    session = live_sessions.get(request.session_id)
    if not session or not session["markers"]:
        raise HTTPException(status_code=404, detail="No session data found.")
    
    try:
        report = await orchestrator.llm_agent.generate_live_synthesis(
            animal_data={"breed": session["pet_breed"], "state": session["primary_state"]},
            markers=list(set(session["markers"]))
        )
        
        # Save to history if authenticated
        if user:
            save_analysis(
                user_id=user["id"],
                pet_id=request.pet_id or "",
                pet_name=request.pet_name or session["pet_breed"],
                analysis_type="live",
                emotional_state=report.get("ai_insights", {}).get("emotional_state", "Unknown"),
                happiness_score=report.get("metrics", {}).get("happiness_score", 50),
                summary=report.get("analysis", ""),
                recommendations=report.get("recommendations", [])
            )
        
        try:
            from pdf_export import DrPetClinicalAudit
            pdf_engine = DrPetClinicalAudit()
            pdf_payload = {
                "timestamp": time.time(),
                "metrics": report.get("metrics", {}),
                "ai_insights": report.get("ai_insights", {}),
                "coaching_plan": {"message": report.get("analysis", ""), "care_methods": report.get("recommendations", [])},
                "data_fidelity": "Live Session Intelligence"
            }
            await asyncio.to_thread(pdf_engine.generate_pdf, request.session_id, pdf_payload)
            report["clinical_audit_url"] = f"/download/report/{request.session_id}"
        except Exception as pdf_e:
            logger.error(f"PDF Generation failed: {pdf_e}")

        if request.session_id in live_sessions:
            del live_sessions[request.session_id]
        return report
    except Exception as e:
        logger.error(f"SYNTHESIS Fatal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/live/status/{session_id}")
async def get_live_status(session_id: str):
    session = live_sessions.get(session_id)
    if not session:
        return {"status": "inactive"}
    return {
        "status": "active",
        "markers_count": len(session.get("markers", [])),
        "primary_state": session.get("primary_state", "Searching"),
        "last_detection": session.get("last_detection_time", 0)
    }

@app.get("/download/report/{file_id}")
async def download_report(file_id: str):
    pdf_path = os.path.join(RESULTS_DIR, f"DR_PET_Audit_{file_id}.pdf")
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, filename=f"DrPet_Audit_{file_id}.pdf")
    return {"error": "Report not found."}

@app.get("/api/highlight")
async def get_daily_highlight(pet_type: str = "pet", authorization: str = Header(None)):
    """Generates a personalized daily highlight based on recent history."""
    recent_observations = ["No observations recorded today. Standard baseline."]
    
    if authorization and authorization.startswith("Bearer "):
        user = get_user_by_token(authorization[7:])
        if user:
            history = get_analysis_history(user["id"], limit=5)
            if history:
                recent_observations = [h.get("summary", "") for h in history if h.get("summary")]
    
    try:
        report = await orchestrator.llm_agent.generate_daily_highlight(pet_type, recent_observations)
        return report
    except Exception as e:
        logger.error(f"Failed to generate highlight: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate daily highlight.")

class ConsultationRequest(BaseModel):
    message: str
    pet_context: Optional[dict] = None

@app.post("/api/ai-vet/consult")
async def ai_vet_consult(request: ConsultationRequest):
    try:
        # Use Groq for faster and more structured vet reasoning
        if not orchestrator.llm_agent.groq_client:
            raise Exception("Groq client not initialized")
            
        system_prompt = "You are Dr. PET AI, a professional veterinary assistant based in Coimbatore. Provide empathetic, medically-grounded advice. Always recommend JP Pet Speciality Hospital or SKS Veterinary Hospital for emergencies. Keep responses concise and helpful."
        
        chat_completion = await orchestrator.llm_agent.groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message}
            ],
            model=orchestrator.llm_agent.groq_model,
            max_tokens=500,
            temperature=0.7
        )
        
        ai_response = chat_completion.choices[0].message.content
        logger.info(f"AI VET CONSULT: {request.message} -> {ai_response[:50]}...")
        
        return {"response": ai_response}
        
    except Exception as e:
        logger.error(f"AI Vet Consult Error: {e}")
        # Fallback to a simple heuristic if API fails
        return {"response": "I apologize, but I'm having trouble connecting to my knowledge base. For urgent issues like chocolate ingestion, please contact JP Pet Speciality Hospital (+91 9600623980) immediately."}

@app.post("/feedback")
async def store_feedback(feedback: dict):
    logger.info(f"USER FEEDBACK RECORDED: {feedback}")
    return {"status": "success"}

# Serve Frontend
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    logger.warning(f"Frontend directory not found at {frontend_dir}")

if __name__ == "__main__":
    logger.info("Booting Dr. PET backend...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
