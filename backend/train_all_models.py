# backend/train_all_models.py

"""
Full ML Model Training Pipeline for MarketPlayground

This script sequentially retrains all machine learning models used in the backend:
1. Belief Tag Classifier
2. Asset Class Predictor
3. Smart Strategy Predictor
4. Feedback Quality Classifier
5. Strategy Classifier trained from Feedback History

Each model training step logs status to the central training log for tracking.
"""

import os
import traceback

# Import individual training functions for modularity and clarity
from .train_belief_model import train_belief_model
from .train_asset_model import train_asset_model
from .train_smarter_strategy_model import train_strategy_model
from .feedback_trainer import train_feedback_model, train_strategy_classifier_from_feedback
from .ai_engine.strategy_training_pipeline import main as train_strategy_pipeline

from backend.utils.logger import write_training_log

def train_all_models():
    """
    Runs the full retraining sequence for all models.
    Logs each step and catches exceptions to continue training others.
    """

    base_dir = os.path.dirname(os.path.abspath(__file__))
    belief_input = os.path.join(base_dir, "training_data", "clean_belief_tags.csv")

    log_output = "\n🧠 Starting full model retraining pipeline...\n"

    # Step 1: Belief Tag Classifier
    try:
        train_belief_model(
            input_file=belief_input,
            model_output_path=base_dir,
            vectorizer_output_path=base_dir
        )
        log_output += "✅ Belief tag model retrained\n"
    except Exception as e:
        log_output += f"❌ Failed to train belief tag model: {e}\n{traceback.format_exc()}\n"

    # Step 2: Asset Class Predictor
    try:
        train_asset_model()
        log_output += "✅ Asset class model retrained\n"
    except Exception as e:
        log_output += f"❌ Failed to train asset class model: {e}\n{traceback.format_exc()}\n"

    # Step 3: Smart Strategy Predictor
    try:
        train_strategy_model()
        log_output += "✅ Smart strategy model retrained\n"
    except Exception as e:
        log_output += f"❌ Failed to train smart strategy model: {e}\n{traceback.format_exc()}\n"

    # Step 4: Feedback Quality Classifier
    try:
        train_feedback_model()
        log_output += "✅ Feedback quality model retrained\n"
    except Exception as e:
        log_output += f"❌ Failed to train feedback quality model: {e}\n{traceback.format_exc()}\n"

    # Step 5: Strategy Classifier from Feedback History
    try:
        train_strategy_classifier_from_feedback()
        log_output += "✅ Strategy-from-feedback classifier retrained\n"
    except Exception as e:
        log_output += f"❌ Failed to train strategy-from-feedback classifier: {e}\n{traceback.format_exc()}\n"

    # ADD THIS ENTIRE BLOCK:
    # Step 6: Strategy Training Pipeline
    try:
        train_strategy_pipeline()
        log_output += "✅ Strategy training pipeline retrained\n"
    except Exception as e:
        log_output += f"❌ Failed to train strategy pipeline: {e}\n{traceback.format_exc()}\n"

    # Write all logs to central training log file


    # Write all logs to central training log file
    write_training_log(log_output + "\n✅ All model training steps completed.")

if __name__ == "__main__":
    train_all_models()
