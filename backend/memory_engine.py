import json
import os
import time
import uuid
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from logger import get_logger

logger = get_logger("MemoryEngine")

class DrPetMemoryEngine:
    def __init__(self):
        # We now use Persistent Qdrant (On-disk)
        self.db_dir = "data/qdrant_db"
        os.makedirs(self.db_dir, exist_ok=True)
        self.client = QdrantClient(path=self.db_dir)
        self.collection_name = "behavior_vectors"
        
        # Initialize the collection if it doesn't exist
        try:
            self.client.get_collection(self.collection_name)
            logger.info(f"Connected to existing continuous Qdrant memory: {self.collection_name}")
        except Exception:
            logger.info(f"Initializing new Qdrant persistent vector memory: {self.collection_name}")
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=5, distance=Distance.EUCLID),
            )
        
        # Profile DB still uses JSON for simplicity
        self.db_path = "data/memory_db.json"
        self._init_db()

    def _init_db(self):
        if not os.path.exists(self.db_path):
            os.makedirs("data", exist_ok=True)
            with open(self.db_path, "w") as f:
                json.dump({
                    "pets": {
                        "Max": {"breed": "Labrador", "age": 5, "weight": "30kg"}
                    }
                }, f)

    def get_pet_profile(self, pet_id="Max"):
        try:
            with open(self.db_path, "r") as f:
                db = json.load(f)
            return db.get("pets", {}).get(pet_id, {"breed": "General", "age": 0})
        except:
            return {"breed": "General", "age": 0}

    def store_event(self, pet_id, behavior_vector, metadata):
        """
        Stores a behavior feature vector in Qdrant Vector DB.
        [Improvement #2: Persistent High-Fidelity Memory]
        """
        try:
            point_id = str(uuid.uuid4())
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=behavior_vector,
                        payload={
                            "pet_id": pet_id,
                            "timestamp": time.time(),
                            **metadata
                        }
                    )
                ]
            )
            print(f"MEMORY ENGINE: Stored vector {point_id} in Qdrant.")
        except Exception as e:
            print(f"Failed to store memory event in Qdrant: {e}")

    def get_similar_events(self, pet_id, current_vector, limit=3):
        """
        True Semantic Search using Vector DB.
        [Improvement #2]
        """
        try:
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=current_vector,
                limit=limit
            )
            
            return [{
                "file_id": hit.payload.get("file_id"),
                "vocal_sentiment": hit.payload.get("vocal_sentiment"),
                "timestamp": hit.payload.get("timestamp"),
                "similarity": round(hit.score, 2)
            } for hit in search_result]
            
        except Exception as e:
            print(f"Qdrant Semantic Search Error: {e}")
            return []

    def detect_anomalies(self, pet_id, current_vector):
        """
        Anomaly detection using historical mean from Vector DB.
        """
        try:
            # For prototype simplicity, we fetch recent points to calculate baseline
            # In production, we'd use a rolling centroid.
            points = self.client.scroll(
                collection_name=self.collection_name,
                limit=10,
                with_payload=True,
                with_vectors=True
            )[0]
            
            history = [p.vector for p in points if p.payload.get("pet_id") == pet_id]
            
            if len(history) < 2:
                return {"is_anomaly": False, "message": "Baseline lookup in progress.", "deviation_score": "0%"}
            
            mean_vector = np.mean(np.array(history), axis=0)
            distance = np.linalg.norm(np.array(current_vector) - mean_vector)
            deviation = min(100.0, float(distance * 40)) 
            is_anomaly = deviation > 30.0

            return {
                "is_anomaly": is_anomaly,
                "deviation_score": f"{round(deviation, 2)}%",
                "message": "Consistent with historical profile." if not is_anomaly else "Behavioral shift detected."
            }
        except Exception as e:
            print(f"Qdrant Anomaly error: {e}")
            return {"is_anomaly": False, "message": "Baseline check skipped.", "deviation_score": "0%"}

    def get_temporal_history(self, pet_id, limit=5):
        try:
             points = self.client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=True
            )[0]
             # Sort by timestamp in payload
             history = [{"vector": p.vector, "payload": p.payload} for p in points]
             history.sort(key=lambda x: x["payload"].get("timestamp", 0), reverse=True)
             return history
        except:
            return []

    def get_rag_context(self, breed="General Pet", behavior_state="Relaxed / Equilibrium"):
        """
        Live Internet RAG Retrieval (duckduckgo_search).
        """
        from duckduckgo_search import DDGS
        
        # Ensure we don't use 'General Pet' in the query if we can help it
        query_breed = breed if "General" not in breed else "dog" # Default to dog for generic animal advice
        
        query = f"veterinary behaviorist advice {query_breed} behavioral markers {behavior_state}"
        if any(s in behavior_state for s in ["Tense", "Defensive", "Reactive"]):
            query = f"{query_breed} muscle rigidity and guarding behavior signals"
        elif any(s in behavior_state for s in ["Anxious", "Distress", "Aroused"]):
            query = f"{query_breed} displacement behaviors or high arousal signs"

        logger.info(f"RAG: Fetching expert context for {query}")
        
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=2))
                if results:
                    context = results[0]['body']
                    return f"Expert Data: {context[:300]}..."
        except Exception as e:
            print(f"RAG lookup failed: {e}")
            
        return f"Local Cache: Typical {breed} behavior indicators for '{behavior_state}' state."
