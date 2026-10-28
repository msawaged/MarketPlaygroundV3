# backend/visualize_strategy_distribution.py

import pandas as pd
import matplotlib.pyplot as plt

# Load cleaned strategy data
df = pd.read_csv("backend/training_data/cleaned_strategies.csv")

# Count frequency
counts = df['strategy_cleaned'].value_counts()

# Plot
plt.figure(figsize=(10, 5))
counts.plot(kind='bar')
plt.title("Strategy Distribution")
plt.ylabel("Count")
plt.xticks(rotation=45)
plt.tight_layout()

# Save to file
plt.savefig("backend/strategy_distribution.png")
print("✅ Strategy distribution saved as backend/strategy_distribution.png")
