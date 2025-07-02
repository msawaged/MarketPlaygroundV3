# backend/routes/debug_router.py
# ✅ Debug Router: Exposes diagnostic endpoints for training logs

import os
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter()

# === Paths to log files ===
LOGS_DIR = os.path.join("backend", "logs")
LAST_JSON_LOG = os.path.join(LOGS_DIR, "last_training_log.json")
LAST_TRAINING_LOG_TXT = os.path.join(LOGS_DIR, "last_training_log.txt")
RETRAIN_LOG_PATH = os.path.join(LOGS_DIR, "retrain_worker.log")
NEWS_LOG_PATH = os.path.join(LOGS_DIR, "news_beliefs.csv")

# === Modern: JSON summary for retrain log ===
@router.get("/debug/retrain_log")
def get_latest_retrain_log():
    """
    ✅ Preferred route for frontend: Returns latest training summary from JSON.
    Written by logger.py → used by background worker.
    """
    if not os.path.exists(LAST_JSON_LOG):
        raise HTTPException(status_code=404, detail="No retraining log found.")
    try:
        with open(LAST_JSON_LOG, "r") as f:
            log = json.load(f)
        return log
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read retrain log: {str(e)}")

# === Legacy: Plain text (used by news ingestor or test) ===
@router.get("/debug/last_training_status", response_class=PlainTextResponse)
def read_last_training_status():
    """
    Legacy fallback — reads last_training_log.txt for debug visibility.
    """
    if os.path.exists(LAST_TRAINING_LOG_TXT):
        with open(LAST_TRAINING_LOG_TXT, "r") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="No last training log found.")

# === Full retrain_worker.log view ===
@router.get("/debug/retrain_worker_log", response_class=PlainTextResponse)
def read_retrain_worker_log():
    """
    Returns full contents of retrain_worker.log (rolling history).
    """
    if os.path.exists(RETRAIN_LOG_PATH):
        with open(RETRAIN_LOG_PATH, "r") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="No retrain log found.")

# === Duplicate alias route ===
@router.get("/last_training_log", response_class=PlainTextResponse)
def view_last_training_log():
    """
    Also returns last_training_log.txt — for compatibility with legacy tools.
    """
    if os.path.exists(LAST_TRAINING_LOG_TXT):
        with open(LAST_TRAINING_LOG_TXT, "r") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="Training log not found.")

# === Recent beliefs ingested from news ===
@router.get("/debug/ingested_news")
def get_ingested_news(limit: int = 10):
    """
    Returns the most recent beliefs ingested from news_beliefs.csv.
    """
    if not os.path.exists(NEWS_LOG_PATH):
        raise HTTPException(status_code=404, detail="news_beliefs.csv not found.")

    try:
        with open(NEWS_LOG_PATH, mode="r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
            parsed = []
            for line in lines:
                parts = line.strip().split(",")
                if len(parts) >= 4:
                    parsed.append({
                        "timestamp": parts[0],
                        "title": parts[1],
                        "summary": parts[2],
                        "belief": parts[3]
                    })
        return {"entries": parsed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read news log: {str(e)}")
