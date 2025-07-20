# backend/fix_strategy_column.py

import pandas as pd
import ast

df = pd.read_csv("backend/Training_Strategies_Enhanced.csv")

def extract_strategy(val):
    if isinstance(val, str) and val.startswith("{"):
        try:
            parsed = ast.literal_eval(val)
            return parsed.get("type", "unknown")
        except:
            return "unknown"
    return val.strip().lower()

df["strategy"] = df["strategy"].apply(extract_strategy)

print("✅ Unique strategies after fix:")
print(df["strategy"].value_counts())

# Save cleaned version
df.to_csv("backend/training_data/cleaned_strategies.csv", index=False)
print("✅ Saved to backend/training_data/cleaned_strategies.csv")
