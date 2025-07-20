# backend/routes/news_router.py

"""
📡 News Router — Accepts news headlines, converts to belief, runs the AI engine,
submits auto-feedback, and returns the strategy for frontend display.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# ✅ AI and feedback system imports
from backend.ai_engine.ai_engine import run_ai_engine
from backend.feedback_handler import save_feedback_entry

router = APIRouter()

# ✅ Define the expected input schema
class NewsInput(BaseModel):
    title: str
    link: str

# ✅ POST endpoint: /news/ingest
@router.post("/ingest")
def ingest_news(news: NewsInput):
    """
    Accepts a news article, extracts the title as a belief,
    runs it through the AI engine, logs feedback, and returns the strategy.
    """
    try:
        belief = news.title.strip()
        user_id = "news_ingestor"

        # 🧠 Run AI engine on the belief
        strategy_result = run_ai_engine(belief=belief, user_id=user_id)

        # 💾 Submit auto-feedback (positive sentiment)
        save_feedback_entry(
            belief=belief,
            strategy=strategy_result.get("type", "unknown"),
            feedback="positive",  # ✅ Corrected from 'result'
            source="news_router",  # 🪪 Optional: track feedback source
            confidence=strategy_result.get("confidence", 0.5),  # 🧠 Optional: AI-generated
            user_id=user_id
        )

        # ✅ Return message and strategy to frontend
        return {
            "message": f"News ingested successfully: {news.title}",
            "strategy": strategy_result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest news: {str(e)}")
