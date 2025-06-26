# run_simulated_training_loop.py

"""
Main loop for AI/ML continuous training:
- Pulls beliefs from real news or generates synthetic ones
- Feeds them into the AI engine for strategy generation
- Simulates good/bad feedback
- Logs the feedback for training
- Retrains all models in one cycle
"""

import random
import time
import subprocess
from backend.ai_engine.ai_engine import run_ai_engine
from backend.feedback_trainer import append_feedback_entry
from backend.news_scraper import fetch_news_beliefs  # ⬅️ Use working version

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
    """
    Randomly select a belief from templates
    Returns: Tuple of (belief text, tone type)
    """
    tone = random.choice(list(belief_templates.keys()))
    belief = random.choice(belief_templates[tone])
    return belief, tone

def simulate_feedback(result):
    """
    Fake feedback generator based on whether a strategy was produced.
    Replace with real user data later.
    """
    if result and result.get("strategy") and result.get("asset_class"):
        return "good" if random.random() > 0.3 else "bad"
    return "bad"

def run_loop(n=25, include_news=True):
    """
    Run the full belief-to-feedback-to-training loop.
    Params:
    - n: total number of beliefs to run
    - include_news: whether to include real financial news beliefs
    """
    beliefs = []

    # ✅ Use real news beliefs
    if include_news:
        news_data = fetch_news_beliefs()
        news_beliefs = [b["belief"] for b in news_data][:n // 2]
        beliefs += [(b, "news") for b in news_beliefs]

    # ✅ Fill in with synthetic beliefs
    for _ in range(n - len(beliefs)):
        beliefs.append(generate_synthetic_belief())

    # ✅ Shuffle to mix types
    random.shuffle(beliefs)

    # 🚀 Run each belief through AI
    for i, (belief, tone) in enumerate(beliefs):
        print(f"\n🧠 [{i+1}/{n}] Belief: {belief} (Tone: {tone})")

        try:
            result = run_ai_engine(belief)
            label = simulate_feedback(result)
            append_feedback_entry(belief, result, label)
            print(f"✅ Logged belief as {label.upper()}")
        except Exception as e:
            print(f"❌ Error: {e}")

        time.sleep(1)

    # 🔁 Final step: retrain all models
    print("\n🔁 Retraining models after simulation...\n")
    subprocess.run(["python", "backend/train_all_models.py"])

if __name__ == "__main__":
    run_loop(25)
