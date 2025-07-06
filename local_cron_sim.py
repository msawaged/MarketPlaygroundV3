# local_cron_sim.py

import time
import subprocess
from datetime import datetime

def run_news_ingestor():
    print(f"\n🕒 Triggered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    result = subprocess.run(
        ["python", "backend/news_ingestor.py"],
        capture_output=True,
        text=True
    )
    print(result.stdout)

if __name__ == "__main__":
    while True:
        run_news_ingestor()
        print("⏳ Sleeping for 3600 seconds (1 hour)...\n")
        time.sleep(3600)  # sleep for 1 hour
