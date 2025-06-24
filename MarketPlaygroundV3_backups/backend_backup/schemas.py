# backend/schemas.py
# ✅ Defines data models used for request validation across the app

from pydantic import BaseModel
from typing import Optional

# --- User Authentication ---
class UserAuth(BaseModel):
    username: str
    password: str

# --- Belief Input ---
class BeliefRequest(BaseModel):
    belief: str
    user_id: Optional[str] = None  # Optional field for identifying user sessions

# --- Feedback Submission ---
class FeedbackRequest(BaseModel):
    belief: str
    strategy: str
    feedback: str
    user_id: Optional[str] = None  # Optional field for personalized feedback
