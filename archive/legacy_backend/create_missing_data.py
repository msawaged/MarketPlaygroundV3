# FILE: backend/create_missing_data.py
# PURPOSE: Generate the missing cleaned_strategies.csv file from existing data
# This file is needed for the smart strategy model training

import pandas as pd
import os

# Check if the training_data directory exists, create if not
training_dir = "training_data"
if not os.path.exists(training_dir):
    os.makedirs(training_dir)
    print(f"Created directory: {training_dir}")

# Load existing strategy outcomes data
# This file contains historical strategy performance data
try:
    df = pd.read_csv('strategy_outcomes.csv')
    print(f"Loaded {len(df)} rows from strategy_outcomes.csv")
except FileNotFoundError:
    print("Error: strategy_outcomes.csv not found")
    exit(1)

# Extract relevant columns for strategy training
# belief: user's market belief text
# strategy: the strategy type that was generated
# result: outcome (win/loss/pending)
if all(col in df.columns for col in ['belief', 'strategy', 'result']):
    cleaned_df = df[['belief', 'strategy', 'result']].copy()
    
    # Remove any rows with missing data
    cleaned_df = cleaned_df.dropna()
    
    # Save to the expected location
    output_path = os.path.join(training_dir, 'cleaned_strategies.csv')
    cleaned_df.to_csv(output_path, index=False)
    print(f"Created {output_path} with {len(cleaned_df)} clean records")
else:
    print("Error: Required columns not found in strategy_outcomes.csv")
    print(f"Available columns: {df.columns.tolist()}")
    