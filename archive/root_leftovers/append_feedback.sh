#!/bin/bash

# 📌 BATCH: Appends predefined reinforcement examples to feedback_data.json
echo "🔄 Generating batch.json with fresh timestamps..."
cat <<EOF > batch.json
[
  { "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "user_id": "murad_test", "ip": "127.0.0.1", "belief": "AAPL looks poised to breakout after earnings", "strategy": "Call Option", "feedback": "good", "risk_profile": "aggressive" },
  { "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "user_id": "murad_test", "ip": "127.0.0.1", "belief": "If NVDA beats estimates, it's going to pop", "strategy": "Call Option", "feedback": "good", "risk_profile": "aggressive" },
  { "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "user_id": "murad_test", "ip": "127.0.0.1", "belief": "GOOG might rip next week with positive AI news", "strategy": "Call Option", "feedback": "good", "risk_profile": "aggressive" }
]
EOF

echo "📦 Merging batch.json into backend/feedback_data.json..."
jq -s '.[0] + .[1]' backend/feedback_data.json batch.json > tmp.json && mv tmp.json backend/feedback_data.json && rm batch.json

echo "✅ Done. Current feedback entry count:"
jq length backend/feedback_data.json
