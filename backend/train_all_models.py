# train_all_models.py
# Trains all core models in sequence

from train_model import train_belief_model
from train_multi_asset_model import train_multi_asset_model

def train_all_models():
    print("🚀 Starting full model training...")

    # Belief model
    train_belief_model()

    # Multi-asset strategy model
    train_multi_asset_model()

    print("✅ All models trained successfully.")
