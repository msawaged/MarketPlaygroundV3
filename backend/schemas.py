# backend/schemas.py
# ✅ Defines data models used for request validation across the app

from pydantic import BaseModel, validator
from typing import Optional

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
    strategy: str                    # Strategy returned by the AI
    feedback: str                    # Accepts: "good", "bad", "positive", or "negative" (mapped internally)
    user_id: Optional[str] = None    # Who submitted the feedback (manual or auto-ingested)
    source: Optional[str] = None     # e.g. "news_ingestor", "manual", "user"
    confidence: Optional[float] = None  # Model's confidence in the strategy (0.0 to 1.0)
    risk_profile: Optional[str] = "moderate"  # ✅ Add this line

    @validator("feedback")
    def normalize_feedback(cls, value):
        """
        Accepts flexible feedback input and normalizes it to 'good' or 'bad'.
        """
        val = value.lower().strip()
        if val in ["good", "positive"]:
            return "good"
        if val in ["bad", "negative"]:
            return "bad"
        raise ValueError("Feedback must be one of: 'good', 'bad', 'positive', or 'negative'")
