# backend/schemas.py

from pydantic import BaseModel

# This model defines the expected input schema for the /process_belief endpoint
class BeliefRequest(BaseModel):
    belief: str  # Natural language market belief, e.g., "TSLA will go up this week"

    class FeedbackInput(BaseModel):
    belief: str
    strategy: str
    result: str  # e.g., "positive", "negative", "missed"
