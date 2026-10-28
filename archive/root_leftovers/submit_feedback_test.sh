#!/bin/bash

# Array of test beliefs
declare -a beliefs=(
  "I believe AAPL will rise sharply next week"
  "TSLA will likely fall due to new regulations"
  "NVDA earnings will beat estimates this quarter"
  "The S&P 500 will rally after Fed announcement"
  "Bitcoin will experience high volatility in the next month"
  "Energy sector stocks will outperform in Q3"
  "Amazon will expand into new international markets soon"
  "The bond market will stabilize after recent turbulence"
  "Gold prices will rise as inflation fears increase"
  "Tech sector will see a correction in the coming weeks"
)

# Corresponding feedback types (positive/negative)
declare -a feedbacks=(
  "positive"
  "negative"
  "positive"
  "positive"
  "negative"
  "positive"
  "positive"
  "negative"
  "positive"
  "negative"
)

# Corresponding confidence values (0.6 - 0.95)
declare -a confidences=(
  0.9
  0.6
  0.85
  0.9
  0.65
  0.8
  0.95
  0.6
  0.88
  0.7
)

echo "Starting batch submission of beliefs and feedback..."

for i in ${!beliefs[@]}
do
  belief="${beliefs[$i]}"
  feedback="${feedbacks[$i]}"
  confidence="${confidences[$i]}"

  echo "Submitting belief #$((i+1)): $belief"

  # Submit belief
  curl -s -X POST "https://marketplayground-backend.onrender.com/process_belief" \
    -H "Content-Type: application/json" \
    -d "{\"belief\": \"$belief\"}"

  echo "Submitted belief #$((i+1))"

  # Prepare feedback JSON (escaped quotes for nested JSON)
  strategy_json="{\"type\":\"test_strategy\",\"description\":\"Auto test strategy for belief #$((i+1))\"}"
  strategy_escaped=$(echo $strategy_json | sed 's/"/\\"/g')

  feedback_payload="{\"user_id\": \"test_user\", \"belief\": \"$belief\", \"strategy\": \"$strategy_escaped\", \"feedback\": \"$feedback\", \"confidence\": $confidence}"

  echo "Submitting feedback #$((i+1)): $feedback with confidence $confidence"

  # Submit feedback
  curl -s -X POST "https://marketplayground-backend.onrender.com/submit_feedback" \
    -H "Content-Type: application/json" \
    -d "$feedback_payload"

  echo "Submitted feedback #$((i+1))"

  # Short delay between requests
  sleep 1
done

echo "Batch submission completed."
