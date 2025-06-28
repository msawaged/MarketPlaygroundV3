# backend/generate_enhanced_training_data.py

import csv
from belief_parser import detect_ticker, detect_direction, detect_confidence

INPUT_FILE = "backend/Training_Strategies.csv"
OUTPUT_FILE = "backend/Training_Strategies_Enhanced.csv"

def enhance_training_data():
    with open(INPUT_FILE, mode="r", encoding="utf-8") as infile, \
         open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as outfile:

        reader = csv.DictReader(infile)
        fieldnames = ['belief', 'ticker', 'direction', 'confidence', 'asset_class', 'strategy']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            belief = row['belief']
            strategy = row['strategy']
            asset_class = row['asset_class']

            # Auto-enhance features
            ticker = detect_ticker(belief)
            direction = detect_direction(belief)
            confidence = detect_confidence(belief)

            writer.writerow({
                'belief': belief,
                'ticker': ticker,
                'direction': direction,
                'confidence': round(confidence, 4),
                'asset_class': asset_class,
                'strategy': strategy
            })

    print(f"✅ Enhanced training data saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    enhance_training_data()
