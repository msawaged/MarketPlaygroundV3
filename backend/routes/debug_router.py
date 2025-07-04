# backend/routes/debug_router.py
# ✅ Debug Router: Central hub for inspecting backend AI loop health and logs

import os
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse

router = APIRouter()

# === File paths used by diagnostics ===
LOGS_DIR = os.path.join("backend", "logs")
LAST_JSON_LOG = os.path.join(LOGS_DIR, "last_training_log.json")
LAST_TRAINING_LOG_TXT = os.path.join(LOGS_DIR, "last_training_log.txt")
RETRAIN_LOG_PATH = os.path.join(LOGS_DIR, "retrain_worker.log")
NEWS_LOG_PATH = os.path.join(LOGS_DIR, "news_beliefs.csv")
FEEDBACK_PATH = os.path.join("backend", "feedback_data.json")
STRATEGY_PATH = os.path.join("backend", "strategy_log.json")

# === GET /debug/retrain_log → Summary of last training session ===
@router.get("/debug/retrain_log")
def get_latest_retrain_log():
    if not os.path.exists(LAST_JSON_LOG):
        raise HTTPException(status_code=404, detail="No retraining log found.")
    try:
        with open(LAST_JSON_LOG, "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read retrain log: {str(e)}")

# === GET /debug/last_training_status → Raw TXT (legacy) ===
@router.get("/debug/last_training_status", response_class=PlainTextResponse)
def read_last_training_status():
    if os.path.exists(LAST_TRAINING_LOG_TXT):
        with open(LAST_TRAINING_LOG_TXT, "r") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="No last training log found.")

# === GET /debug/retrain_worker_log → Full retrain log ===
@router.get("/debug/retrain_worker_log", response_class=PlainTextResponse)
def read_retrain_worker_log():
    if os.path.exists(RETRAIN_LOG_PATH):
        with open(RETRAIN_LOG_PATH, "r") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="No retrain log found.")

# === GET /last_training_log → Legacy alias ===
@router.get("/last_training_log", response_class=PlainTextResponse)
def view_last_training_log():
    if os.path.exists(LAST_TRAINING_LOG_TXT):
        with open(LAST_TRAINING_LOG_TXT, "r") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="Training log not found.")

# === GET /debug/ingested_news → Returns last N news beliefs ===
@router.get("/debug/ingested_news")
def get_ingested_news(limit: int = 10):
    if not os.path.exists(NEWS_LOG_PATH):
        raise HTTPException(status_code=404, detail="news_beliefs.csv not found.")
    try:
        with open(NEWS_LOG_PATH, "r", encoding="utf-8") as f:
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

# === GET /debug/feedback_count → Total feedback entries ===
@router.get("/debug/feedback_count")
def get_feedback_count():
    if not os.path.exists(FEEDBACK_PATH):
        raise HTTPException(status_code=404, detail="feedback_data.json not found.")
    try:
        with open(FEEDBACK_PATH, "r") as f:
            data = json.load(f)
        return {"feedback_count": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read feedback data: {str(e)}")

# === GET /debug/last_strategy_log → Recent strategy info ===
@router.get("/debug/last_strategy_log")
def get_last_strategy_log():
    if not os.path.exists(STRATEGY_PATH):
        raise HTTPException(status_code=404, detail="strategy_log.json not found.")
    try:
        with open(STRATEGY_PATH, "r") as f:
            data = json.load(f)
        return {
            "total_strategies": len(data),
            "last_entry": data[-1] if data else {}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read strategy log: {str(e)}")

# === ✅ NEW: GET /debug/logs/recent → Generic log viewer ===
@router.get("/logs/recent", response_class=PlainTextResponse)
def get_recent_logs(lines: int = 50):
    """
    Returns the last N lines of retrain_worker.log for quick frontend preview.
    """
    if not os.path.exists(RETRAIN_LOG_PATH):
        raise HTTPException(status_code=404, detail="Log file not found.")
    try:
        with open(RETRAIN_LOG_PATH, "r") as f:
            content = f.readlines()
            return "".join(content[-lines:])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")

# === GET /debug/ai_loop_status → Unified backend dashboard ===
@router.get("/debug/ai_loop_status")
def get_ai_loop_status():
    """
    🧠 Master dashboard:
    - Last strategy
    - Feedback count
    - News ingestion count
    - Last retraining log
    """
    status = {}

    # Strategy info
    try:
        if os.path.exists(STRATEGY_PATH):
            with open(STRATEGY_PATH, "r") as f:
                data = json.load(f)
                status["last_strategy"] = data[-1] if data else {}
        else:
            status["last_strategy"] = "Not available"
    except Exception as e:
        status["last_strategy"] = f"Error: {str(e)}"

    # Feedback total
    try:
        if os.path.exists(FEEDBACK_PATH):
            with open(FEEDBACK_PATH, "r") as f:
                status["feedback_count"] = len(json.load(f))
        else:
            status["feedback_count"] = 0
    except Exception as e:
        status["feedback_count"] = f"Error: {str(e)}"

    # News count
    try:
        if os.path.exists(NEWS_LOG_PATH):
            with open(NEWS_LOG_PATH, "r", encoding="utf-8") as f:
                status["news_beliefs_ingested"] = len(f.readlines())
        else:
            status["news_beliefs_ingested"] = 0
    except Exception as e:
        status["news_beliefs_ingested"] = f"Error: {str(e)}"

    # Retrain summary
    try:
        if os.path.exists(LAST_JSON_LOG):
            with open(LAST_JSON_LOG, "r") as f:
                status["last_retrain"] = json.load(f)
        else:
            status["last_retrain"] = "Not available"
    except Exception as e:
        status["last_retrain"] = f"Error: {str(e)}"

    return status
