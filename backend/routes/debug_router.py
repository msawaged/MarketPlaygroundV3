# backend/routes/debug_router.py

"""
Debug Router: Exposes diagnostic endpoints for internal training logs.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
import os

router = APIRouter()

# Path to the background worker training log
RETRAIN_LOG_PATH = os.path.join("backend", "logs", "retrain_worker.log")

# Path to the last news ingestor training summary
LAST_TRAINING_LOG = os.path.join("backend", "logs", "last_training_log.txt")

@router.get("/debug/last_training_status", response_class=PlainTextResponse)
def read_last_training_status():
    """
    Returns the contents of the latest training summary from the news ingestor.
    """
    if os.path.exists(LAST_TRAINING_LOG):
        with open(LAST_TRAINING_LOG, "r") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="No last training log found.")

@router.get("/debug/retrain_log", response_class=PlainTextResponse)
def read_retrain_worker_log():
    """
    Returns the full retrain_worker.log contents from background retraining.
    """
    if os.path.exists(RETRAIN_LOG_PATH):
        with open(RETRAIN_LOG_PATH, "r") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="No retraining log found.")
