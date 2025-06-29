# backend/utils/feature_utils.py

"""
Feature combination utilities for AI/ML models.
Combines structured and text-based fields into a single input for vectorization.
"""

import pandas as pd
from typing import Union

def combine_features(X_df: pd.DataFrame) -> Union[pd.Series, list[str]]:
    """
    Combines belief, ticker, direction, confidence, and asset_class into a single string per row.

    Args:
        X_df (pd.DataFrame): Input features with the following expected columns:
            - 'belief'
            - 'ticker'
            - 'direction'
            - 'confidence'
            - 'asset_class'

    Returns:
        pd.Series or list[str]: Combined text features per row for model vectorization.
    """

    # Ensure required columns are present
    required_columns = ['belief', 'ticker', 'direction', 'confidence', 'asset_class']
    for col in required_columns:
        if col not in X_df.columns:
            raise ValueError(f"Missing required column: '{col}' in input DataFrame")

    # Combine columns into a single string per row
    return (
        X_df['belief'].fillna('').astype(str).str.strip() + ' ' +
        X_df['ticker'].fillna('').astype(str).str.strip() + ' ' +
        X_df['direction'].fillna('').astype(str).str.strip() + ' ' +
        X_df['confidence'].fillna('').astype(str).str.strip() + ' ' +
        X_df['asset_class'].fillna('').astype(str).str.strip()
    )
