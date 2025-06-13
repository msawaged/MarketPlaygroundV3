# run_continuous_learning.py
# Auto-generates new beliefs, appends to dataset, retrains model

import time
import subprocess

while True:
    print("\n🚀 [Step 1] Generating 50 new beliefs...")
    subprocess.run(["python", "auto_generate_beliefs.py"])

    print("\n🧠 [Step 2] Retraining the belief model...")
    subprocess.run(["python", "train_belief_model.py"])

    print("\n✅ Cycle complete. Waiting 10 seconds before next round...\n")
    time.sleep(10)  # Delay before next round
