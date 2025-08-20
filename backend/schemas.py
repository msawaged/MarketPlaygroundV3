# backend/schemas.py
# ✅ Defines data models used for request validation across the app

from pydantic import BaseModel, validator
from typing import Optional
from typing import Union

# --- 🔐 User Authentication ---
class UserAuth(BaseModel):
    username: str
    password: str

# --- 💭 Belief Input (used for strategy generation) ---
class BeliefRequest(BaseModel):
    belief: str
    user_id: Optional[str] = None  # Optional field for identifying user sessions or sources

# --- 🧠 Feedback Submission (used for model retraining) ---
class FeedbackRequest(BaseModel):
    belief: str                      # Original belief statement
    strategy: Union[str, dict]       # ✅ Accepts both raw strings and structured strategy dicts
    feedback: str                    # Accepts: "good", "bad", "positive", or "negative"
    user_id: Optional[str] = None    # Who submitted the feedback (manual or auto-ingested)
    source: Optional[str] = None     # e.g. "news_ingestor", "manual", "user"
    confidence: Optional[float] = None
    risk_profile: Optional[str] = "moderate"

    @validator("feedback")
    def normalize_feedback(cls, value):
        val = value.lower().strip()
        if val in ["good", "positive"]:
            return "good"
        if val in ["bad", "negative"]:
            return "bad"
        raise ValueError("Feedback must be one of: 'good', 'bad', 'positive', or 'negative'")