#!/usr/bin/env python3
"""
ALPACA AUTHENTICATION DIAGNOSTIC TOOL
=====================================

This script performs comprehensive testing of Alpaca API authentication
to identify the exact root cause of authentication failures.

TESTING SCENARIOS:
1. Environment variable loading verification
2. URL construction analysis  
3. Header authentication format validation
4. Direct API endpoint testing
5. Comparison of working vs failing endpoints
6. Request/response debugging with detailed error capture
"""

import os
import requests
import json
from dotenv import load_dotenv
from pprint import pprint

# Load environment variables
print("=" * 60)
print("🔍 ALPACA AUTHENTICATION DIAGNOSTICS")
print("=" * 60)

# Test different .env loading approaches
print("\n1. ENVIRONMENT VARIABLE LOADING TEST")
print("-" * 40)

# Try loading from current directory
load_dotenv()
print("✓ Loaded .env from current directory")

# Try loading from parent directory
parent_env = os.path.join("..", ".env")
if os.path.exists(parent_env):
    load_dotenv(parent_env)
    print("✓ Loaded .env from parent directory")

# Extract credentials
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

print(f"API Key: {'✓ PRESENT' if ALPACA_API_KEY else '❌ MISSING'}")
print(f"Secret Key: {'✓ PRESENT' if ALPACA_SECRET_KEY else '❌ MISSING'}")
print(f"Base URL: {ALPACA_BASE_URL}")

if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
    print("❌ CRITICAL: Missing API credentials. Cannot continue.")
    exit(1)

print(f"API Key (masked): {ALPACA_API_KEY[:8]}...")
print(f"Secret Key (masked): {ALPACA_SECRET_KEY[:8]}...")

# Test header construction
print("\n2. HEADER CONSTRUCTION TEST")
print("-" * 40)

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

print("Headers constructed:")
for key, value in HEADERS.items():
    print(f"  {key}: {value[:8] if value else 'MISSING'}...")

# URL Analysis
print("\n3. URL CONSTRUCTION ANALYSIS")
print("-" * 40)

print(f"Base URL from .env: {ALPACA_BASE_URL}")

# Test different URL patterns
test_urls = {
    "Account (current code)": f"{ALPACA_BASE_URL}/v2/account",
    "Account (fixed)": f"{ALPACA_BASE_URL.rstrip('/v2')}/v2/account",
    "Positions (current code)": f"{ALPACA_BASE_URL}/v2/positions", 
    "Positions (fixed)": f"{ALPACA_BASE_URL.rstrip('/v2')}/v2/positions",
    "Orders (current code)": f"{ALPACA_BASE_URL}/v2/orders",
    "Orders (fixed)": f"{ALPACA_BASE_URL.rstrip('/v2')}/v2/orders",
    "Market Data (working)": f"https://data.alpaca.markets/v2/options/expirations/AAPL"
}

for name, url in test_urls.items():
    print(f"  {name}: {url}")

# Direct API Testing
print("\n4. DIRECT API ENDPOINT TESTING")
print("-" * 40)

def test_endpoint(name, url, headers, expected_success=True):
    """Test an API endpoint and return detailed results."""
    print(f"\n🔍 Testing: {name}")
    print(f"   URL: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   ✓ SUCCESS: Response received")
                if isinstance(data, dict) and len(data) < 5:
                    pprint(data)
                else:
                    print(f"   Data type: {type(data)}, length: {len(data) if hasattr(data, '__len__') else 'N/A'}")
                return True
            except json.JSONDecodeError:
                print(f"   ⚠️  SUCCESS but invalid JSON: {response.text[:200]}")
                return True
        else:
            print(f"   ❌ FAILED: {response.status_code}")
            print(f"   Error: {response.text[:500]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ REQUEST FAILED: {e}")
        return False

# Test the current problematic URLs
print("\n🧪 TESTING CURRENT IMPLEMENTATION URLS:")
current_base = ALPACA_BASE_URL
test_endpoint("Account Info (Current)", f"{current_base}/v2/account", HEADERS)
test_endpoint("Positions (Current)", f"{current_base}/v2/positions", HEADERS)
test_endpoint("Orders (Current)", f"{current_base}/v2/orders", HEADERS)

# Test fixed URLs
print("\n🧪 TESTING CORRECTED URLS:")
fixed_base = ALPACA_BASE_URL.rstrip('/v2')
test_endpoint("Account Info (Fixed)", f"{fixed_base}/v2/account", HEADERS)
test_endpoint("Positions (Fixed)", f"{fixed_base}/v2/positions", HEADERS)
test_endpoint("Orders (Fixed)", f"{fixed_base}/v2/orders", HEADERS)

# Test market data endpoint that works
print("\n🧪 TESTING WORKING MARKET DATA ENDPOINT:")
market_headers = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}
test_endpoint("Market Data Options (Working)", "https://data.alpaca.markets/v2/options/expirations/AAPL", market_headers)

# Authentication Format Testing
print("\n5. AUTHENTICATION FORMAT VERIFICATION")
print("-" * 40)

def test_auth_variations():
    """Test different authentication header formats."""
    
    variations = [
        {
            "name": "Standard Format (Current)",
            "headers": {
                "APCA-API-KEY-ID": ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
            }
        },
        {
            "name": "With Content-Type",
            "headers": {
                "APCA-API-KEY-ID": ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
                "Content-Type": "application/json",
            }
        },
        {
            "name": "With User-Agent",
            "headers": {
                "APCA-API-KEY-ID": ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
                "User-Agent": "MarketPlayground/1.0",
            }
        }
    ]
    
    test_url = f"{ALPACA_BASE_URL.rstrip('/v2')}/v2/account"
    
    for variant in variations:
        print(f"\n🔐 Testing auth format: {variant['name']}")
        success = test_endpoint(f"Account with {variant['name']}", test_url, variant['headers'])
        if success:
            print("   ✅ This authentication format WORKS!")
        else:
            print("   ❌ This authentication format FAILED")

test_auth_variations()

# Summary and Recommendations
print("\n" + "=" * 60)
print("📊 DIAGNOSTIC SUMMARY & RECOMMENDATIONS")
print("=" * 60)

print("\n🔍 KEY FINDINGS:")
print(f"1. Base URL in .env: {ALPACA_BASE_URL}")
print(f"2. Current code constructs URLs like: {ALPACA_BASE_URL}/v2/account")
print(f"3. This creates malformed URLs if base URL already contains /v2")

print("\n💡 PROBABLE ROOT CAUSE:")
if ALPACA_BASE_URL.endswith('/v2'):
    print("❌ IDENTIFIED: Base URL ends with '/v2', causing double /v2/v2/ in API calls")
    print("   Current: https://paper-api.alpaca.markets/v2/v2/account (WRONG)")
    print("   Should be: https://paper-api.alpaca.markets/v2/account (CORRECT)")
else:
    print("✓ Base URL format appears correct")

print("\n🔧 RECOMMENDED FIXES:")
print("1. Update .env: Remove '/v2' from ALPACA_BASE_URL")
print("2. OR: Update code to strip '/v2' before appending endpoints")
print("3. Add URL validation and logging to all Alpaca API calls")
print("4. Implement proper error handling with detailed response logging")

print("\n📝 NEXT STEPS:")
print("1. Fix the URL construction issue")
print("2. Add comprehensive logging to all API calls")  
print("3. Implement retry logic with exponential backoff")
print("4. Add environment validation on application startup")

print("\n" + "=" * 60)
print("✅ DIAGNOSTICS COMPLETE")
print("=" * 60)