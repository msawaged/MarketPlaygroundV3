# test_api.py

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

# === 1. Save a new test trade ===
print("🚀 Saving test trade...")
response = requests.post(
    f"{BASE_URL}/save_trade",
    headers={"Content-Type": "application/json"},
    data=json.dumps({
        "user_id": "murad_test",
        "belief": "MSFT will surge after product launch",
        "strategy": {
            "type": "Call Spread",
            "description": "Buy 350c / Sell 360c",
            "risk_level": "medium",
            "suggested_allocation": "40%"
        }
    })
)
print("✅ Save trade response:", response.json())

# === 2. Get portfolio summary ===
print("\n📊 Fetching portfolio summary...")
response = requests.get(f"{BASE_URL}/portfolio_summary/murad_test")
print("✅ Portfolio summary:", response.json())

# === 3. Download CSV ===
print("\n📥 Downloading portfolio CSV...")
csv_response = requests.get(f"{BASE_URL}/export_portfolio/murad_test")
with open("murad_test_portfolio.csv", "wb") as f:
    f.write(csv_response.content)
print("✅ CSV downloaded to murad_test_portfolio.csv")

# === 4. Download PNG chart ===
print("\n📈 Downloading portfolio chart PNG...")
png_response = requests.get(f"{BASE_URL}/portfolio_chart/murad_test")
with open("murad_test_chart.png", "wb") as f:
    f.write(png_response.content)
print("✅ Chart image saved to murad_test_chart.png")
