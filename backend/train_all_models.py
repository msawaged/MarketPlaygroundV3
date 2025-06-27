"""
This script runs the full training pipeline for all ML models used in MarketPlayground:
1. Belief Tag Classifier
2. Asset Class (Strategy Type) Predictor
3. Feedback Quality Classifier (Good vs Bad)
4. Strategy Type Classifier (from feedback history)
"""

import os

# ✅ Use absolute imports for cross-module compatibility
from backend.train_belief_model import train_belief_model
from backend.train_multi_asset_model import train_strategy_model
from backend.feedback_trainer import train_feedback_model, train_strategy_classifier_from_feedback

# ✅ Wrap entire pipeline in a callable function
def train_all_models():
    # === Determine base directory dynamically (cross-platform safe) ===
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # === Define paths to training data files ===
    belief_input = os.path.join(base_dir, "training_data", "clean_belief_tags.csv")
    strategy_input = os.path.join(base_dir, "training_data", "clean_belief_asset.csv")

    print("\n✅ Starting full training pipeline...\n")

    # === Step 1: Train Belief Tag Classifier ===
    train_belief_model(
        input_file=belief_input,
        model_output_path=base_dir,
        vectorizer_output_path=base_dir
    )

    # === Step 2: Train Strategy Classifier (Belief → Asset Class) ===
    train_strategy_model(
        input_file=strategy_input,
        model_output_path=base_dir,
        vectorizer_output_path=base_dir
    )

    # === Step 3: Train Feedback Classifier (good vs bad) ===
    train_feedback_model()

    # === Step 4: Train Strategy Type Classifier (from feedback history) ===
    train_strategy_classifier_from_feedback()

    print("\n✅ All models retrained and saved.")


# ✅ Allow running directly from command line
if __name__ == "__main__":
    train_all_models()
