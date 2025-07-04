# backend/news_ingestor_loop.py

"""
This script runs news_ingestor.py every 3600 seconds (1 hour).
It replaces the watchdog loop to be time-based instead.
Used as Render worker.
"""

import time
import subprocess
from datetime import datetime

def run_news_ingestor():
    print(f"\n🕒 [{datetime.utcnow()}] Running news_ingestor.py...\n")
    result = subprocess.run(
        ["python", "backend/news_ingestor.py"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.stderr:
        print(f"⚠️ STDERR:\n{result.stderr}")

# Main infinite loop
while True:
    run_news_ingestor()
    time.sleep(3600)  # Wait 1 hour
