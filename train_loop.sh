#!/bin/bash

# 🚀 Infinite loop to train your ML system every 30 minutes
while true
do
  echo "🚀 [$(date)] Starting MarketPlayground training loop..."

  # Run your belief → strategy → feedback → retrain process
  python run_simulated_training_loop.py >> backend/logs/auto_loop_output.log 2>&1

  echo "🕒 Sleeping for 30 minutes..."
  sleep 1800  # ⏱️ 1800 seconds = 30 minutes
done
