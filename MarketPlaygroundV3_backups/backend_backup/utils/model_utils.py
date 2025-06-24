# backend/utils/model_utils.py

"""
Utility functions for model loading to work across both local and cloud environments.
"""

import os
import joblib

def dynamic_model_path(filename: str) -> str:
    """
    Get the full absolute path to a model file whether running locally or in Render.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, filename)

def load_model(filename: str):
    """
    Load a joblib model from a filename with full dynamic path support.
    """
    full_path = dynamic_model_path(filename)
    return joblib.load(full_path)
