# feed_belief.py
import csv

def get_user_input():
    print("\n🌱 New Training Example")
    belief = input("Belief text: ").strip()
    direction = input("Direction (bullish / bearish / neutral): ").strip().lower()
    duration = input("Duration (short / medium / long): ").strip().lower()
    volatility = input("Volatility (low / medium / high): ").strip().lower()
    return [belief, direction, duration, volatility]

def append_to_csv(data, path="belief_data.csv"):
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(data)
    print("✅ Saved new belief to training data.")

if __name__ == "__main__":
    while True:
        row = get_user_input()
        append_to_csv(row)
        again = input("Add another? (y/n): ").strip().lower()
        if again != "y":
            break
