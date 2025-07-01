# backend/train_all_models.py

"""
This script runs the full training pipeline for all ML models used in MarketPlayground:
1. Belief Tag Classifier
2. Asset Class Predictor
3. Feedback Quality Classifier
4. Strategy Type Classifier from Feedback
5. Multi-Feature Strategy Predictor
"""

import os

# ✅ Import all training functions
from .train_belief_model import train_belief_model
from .train_asset_model import train_asset_model
from .train_smarter_strategy_model import train_strategy_model
from .feedback_trainer import train_feedback_model, train_strategy_classifier_from_feedback

# ✅ Import logger
from backend.utils.logger import write_training_log

def train_all_models():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    belief_input = os.path.join(base_dir, "training_data", "clean_belief_tags.csv")

    log_output = "\n🧠 Starting full model retraining pipeline...\n"

    # === Step 1: Train Belief Tag Classifier ===
    train_belief_model(
        input_file=belief_input,
        model_output_path=base_dir,
        vectorizer_output_path=base_dir
    )
    log_output += "✅ Belief tag model retrained\n"

    # === Step 2: Train Asset Class Predictor ===
    train_asset_model()
    log_output += "✅ Asset class model retrained\n"

    # === Step 3: Train Smart Strategy Model ===
    train_strategy_model()
    log_output += "✅ Smart strategy model retrained\n"

    # === Step 4: Train Feedback Classifier ===
    train_feedback_model()
    log_output += "✅ Feedback quality model retrained\n"

    # === Step 5: Train Strategy Classifier from Feedback History ===
    train_strategy_classifier_from_feedback()
    log_output += "✅ Strategy-from-feedback classifier retrained\n"

    write_training_log(log_output + "\n✅ All models retrained successfully.")

if __name__ == "__main__":
    train_all_models()
