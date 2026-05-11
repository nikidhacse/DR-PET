import sqlite3
import hashlib
import hmac
import os
import json
import time
import uuid
from typing import Optional, Dict, Any
from logger import get_logger

logger = get_logger("Auth")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "drpet.db")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS pets (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            species TEXT NOT NULL,
            breed TEXT,
            age_years REAL,
            weight_kg REAL,
            avatar TEXT,
            notes TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at REAL NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS analysis_history (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            pet_id TEXT,
            pet_name TEXT,
            analysis_type TEXT,
            emotional_state TEXT,
            happiness_score REAL,
            summary TEXT,
            recommendations TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized.")

def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hashed = stored_hash.split(":")
        return hmac.compare_digest(
            hashlib.sha256((salt + password).encode()).hexdigest(),
            hashed
        )
    except:
        return False

def create_token(user_id: str) -> str:
    token = str(uuid.uuid4())
    expires_at = time.time() + (7 * 24 * 3600)  # 7 days
    conn = get_db()
    conn.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
                 (token, user_id, expires_at))
    conn.commit()
    conn.close()
    return token

def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    conn = get_db()
    row = conn.execute(
        "SELECT s.user_id, s.expires_at, u.name, u.email FROM sessions s "
        "JOIN users u ON s.user_id = u.id WHERE s.token = ?", (token,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    if row["expires_at"] < time.time():
        return None
    return {"id": row["user_id"], "name": row["name"], "email": row["email"]}

def register_user(name: str, email: str, password: str) -> Dict[str, Any]:
    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email.lower(),)).fetchone()
    if existing:
        conn.close()
        return {"error": "Email already registered."}
    
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)
    conn.execute(
        "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, name, email.lower(), password_hash, time.time())
    )
    conn.commit()
    conn.close()
    
    token = create_token(user_id)
    return {"token": token, "user": {"id": user_id, "name": name, "email": email.lower()}}

def login_user(email: str, password: str) -> Dict[str, Any]:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
    conn.close()
    
    if not row:
        return {"error": "Invalid email or password."}
    if not verify_password(password, row["password_hash"]):
        return {"error": "Invalid email or password."}
    
    token = create_token(row["id"])
    return {"token": token, "user": {"id": row["id"], "name": row["name"], "email": row["email"]}}

def get_user_pets(user_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM pets WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_pet(user_id: str, name: str, species: str, breed: str = "", 
            age_years: float = 0, weight_kg: float = 0, avatar: str = "", notes: str = "") -> Dict:
    pet_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        "INSERT INTO pets (id, user_id, name, species, breed, age_years, weight_kg, avatar, notes, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (pet_id, user_id, name, species, breed, age_years, weight_kg, avatar, notes, time.time())
    )
    conn.commit()
    conn.close()
    return {"id": pet_id, "name": name, "species": species, "breed": breed,
            "age_years": age_years, "weight_kg": weight_kg, "avatar": avatar, "notes": notes}

def delete_pet(user_id: str, pet_id: str) -> bool:
    conn = get_db()
    result = conn.execute("DELETE FROM pets WHERE id = ? AND user_id = ?", (pet_id, user_id))
    conn.commit()
    conn.close()
    return result.rowcount > 0

def save_analysis(user_id: str, pet_id: str, pet_name: str, analysis_type: str,
                  emotional_state: str, happiness_score: float, summary: str, recommendations: list):
    record_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        "INSERT INTO analysis_history (id, user_id, pet_id, pet_name, analysis_type, emotional_state, "
        "happiness_score, summary, recommendations, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (record_id, user_id, pet_id, pet_name, analysis_type, emotional_state,
         happiness_score, summary, json.dumps(recommendations), time.time())
    )
    conn.commit()
    conn.close()
    return record_id

def get_analysis_history(user_id: str, limit: int = 20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM analysis_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["recommendations"] = json.loads(d["recommendations"])
        except:
            d["recommendations"] = []
        result.append(d)
    return result
