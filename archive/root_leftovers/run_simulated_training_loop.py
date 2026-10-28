# run_simulated_training_loop.py

"""
🔁 AI/ML Continuous Training Loop
- Pulls real or synthetic beliefs
- Feeds them into the AI engine
- Simulates feedback
- Logs results
- Retrains models in one cycle
"""

import random
import time
import subprocess
import argparse
import json
from datetime import datetime
from backend.ai_engine.ai_engine import run_ai_engine
from backend.feedback_trainer import append_feedback_entry
from backend.news_scraper import fetch_news_beliefs

# === Templates for synthetic belief generation ===
belief_templates = {
    "aggressive": [
        "I want to 5x my money fast",
        "Go all in on crypto this week",
        "Short tech hard, it's about to crash"
    ],
    "neutral": [
        "Diversify into energy and healthcare",
        "Slow and steady with dividend stocks",
        "What’s a stable ETF for retirement?"
    ],
    "imaginative": [
        "Bet big if Elon tweets anything about Mars",
        "If gold and bitcoin rise together, what happens?",
        "What if AAPL merges with Netflix next year?"
    ]
}

def generate_synthetic_belief():
    tone = random.choice(list(belief_templates.keys()))
    belief = random.choice(belief_templates[tone])
    return belief, tone

def simulate_feedback(result):
    if result and result.get("strategy") and result.get("asset_class"):
        return "good" if random.random() > 0.3 else "bad"
    return "bad"

def run_loop(n=25, include_news=True, retrain=True, log_output=True):
    beliefs = []

    if include_news:
        news_data = fetch_news_beliefs()
        news_beliefs = [b["belief"] for b in news_data][:n // 2]
        beliefs += [(b, "news") for b in news_beliefs]

    for _ in range(n - len(beliefs)):
        beliefs.append(generate_synthetic_belief())

    random.shuffle(beliefs)
    results = []

    for i, (belief, tone) in enumerate(beliefs):
        print(f"\n🧠 [{i+1}/{n}] Belief: {belief} (Tone: {tone})")
        try:
            result = run_ai_engine(belief)
            label = simulate_feedback(result)
            append_feedback_entry(belief, result, label)
            print(f"✅ Logged belief as {label.upper()}")
            results.append({
                "belief": belief,
                "tone": tone,
                "strategy": result,
                "feedback": label
            })
        except Exception as e:
            print(f"❌ Error: {e}")

        time.sleep(1)

    if log_output:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        with open(f"backend/logs/simulation_{timestamp}.json", "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n📁 Saved simulation log: simulation_{timestamp}.json")

    if retrain:
        print("\n🔁 Retraining models after simulation...\n")
        subprocess.run(["python", "-m", "backend.train_all_models"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run simulated belief training loop.")
    parser.add_argument("--n", type=int, default=25, help="Number of beliefs to simulate")
    parser.add_argument("--include_news", action="store_true", help="Include real news beliefs")
    parser.add_argument("--no_retrain", action="store_true", help="Skip model retraining")
    parser.add_argument("--no_log", action="store_true", help="Skip saving output log")
    args = parser.parse_args()

    run_loop(
        n=args.n,
        include_news=args.include_news,
        retrain=not args.no_retrain,
        log_output=not args.no_log
    )
