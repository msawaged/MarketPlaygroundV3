# scripts/generate_asset_training_data.py

"""
This script creates a clean training dataset for the asset class prediction model
by extracting only 'belief' and 'asset_class' from the main strategy training file.
"""

import pandas as pd

# Load the full labeled strategy data
df = pd.read_csv("backend/training_data/cleaned_strategies.csv")

# Extract only the columns we need
df_clean = df[["belief", "asset_class"]].dropna()

# Drop duplicate belief/asset_class pairs
df_clean = df_clean.drop_duplicates()

# Save the clean output
output_path = "backend/training_data/final_belief_asset_training.csv"
df_clean.to_csv(output_path, index=False)

print(f"✅ Saved clean training data to: {output_path}")
print(df_clean.head())
