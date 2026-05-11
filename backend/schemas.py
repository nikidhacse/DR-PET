from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class BehavioralState(str, Enum):
    RELAXED = "Relaxed / Content"
    PLAYFUL = "Playful / Excited"
    ANXIOUS = "Anxious / Stressed"
    FEARFUL = "Fearful"
    AGGRESSIVE = "Aggressive / Reactive"
    BORED = "Bored / Understimulated"
    PAIN = "Pain / Discomfort"
    ATTENTION = "Attention-Seeking"
    UNCERTAIN = "UNCERTAIN"

class UrgencyLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"

class VideoAnalysisOutput(BaseModel):
    pet_type: str = Field(default="Unknown")
    detected_behavior: str = Field(default="UNCERTAIN")
    confidence_level: str = Field(default="Low")
    what_happened: str = Field(default="Analysis failed to determine exact events.")
    behavioral_signals_observed: List[str] = Field(default_factory=list)
    why_it_might_be_happening: List[str] = Field(default_factory=list)
    personality_profile: str = Field(default="Not determined")
    social_environmental_fit: str = Field(default="Not determined")
    urgency_level: UrgencyLevel = Field(default=UrgencyLevel.LOW)
    recommended_solution: List[str] = Field(default_factory=list)
    vet_needed: bool = Field(default=False)

class LiveSynthesisOutput(BaseModel):
    detected_behavior: BehavioralState = Field(default=BehavioralState.UNCERTAIN)
    what_happened: str = Field(default="Live observation completed.")
    why_it_might_be_happening: List[str] = Field(default_factory=list)
    urgency_level: UrgencyLevel = Field(default=UrgencyLevel.LOW)
    recommended_solution: List[str] = Field(default_factory=list)
    owner_reassurance: str = Field(default="")

class BreedProfileOutput(BaseModel):
    breed: str
    origin: str = ""
    size: str = ""
    temperament_traits: List[str] = Field(default_factory=list)
    energy_level: str = ""
    known_for: str = ""
    current_situation: str = ""
    owner_advice: str = ""
    source_quality: str = "Local Knowledge"

class CoachingReportOutput(BaseModel):
    state: str = "Unknown"
    message: str = "Analysis generated."
    action: str = "Monitor behavior."
    care_methods: List[str] = Field(default_factory=lambda: ["Monitor", "Rest", "Play", "Vet Check"])
    breed_card: Optional[dict] = None
