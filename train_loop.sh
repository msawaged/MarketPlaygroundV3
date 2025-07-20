#!/bin/bash

# ✅ Infinite loop to automatically retrain the model from new feedback
# Logs go to backend/logs/auto_loop_output.log

LOG_FILE="backend/logs/auto_loop_output.log"

# Ensure the log directory exists
mkdir -p backend/logs

while true
do
  echo "🚀 [$(date)] Starting MarketPlayground auto-retrain check..." | tee -a $LOG_FILE

  # ✅ Activate virtual environment
  source venv/bin/activate

  # ✅ Run retraining script (only retrains if new feedback exists)
  python backend/auto_retrain.py >> $LOG_FILE 2>&1

  echo "🕒 Sleeping for 30 minutes..." | tee -a $LOG_FILE
  sleep 1800  # 30 minutes
done
