#!/usr/bin/env python3
"""
DIRECT ALPACA CLIENT TESTING
============================
Test the exact functions used by the backend to identify where the problem occurs.
"""

import os
import sys

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
load_dotenv(os.path.join("..", ".env"))  # Try parent directory too

print("=" * 60)
print("🔍 DIRECT ALPACA CLIENT TESTING")
print("=" * 60)

print(f"\n1. ENVIRONMENT SETUP")
print("-" * 30)

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY") 
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL")

print(f"API Key: {'✓ PRESENT' if ALPACA_API_KEY else '❌ MISSING'}")
print(f"Secret Key: {'✓ PRESENT' if ALPACA_SECRET_KEY else '❌ MISSING'}")
print(f"Base URL: {ALPACA_BASE_URL}")

if ALPACA_BASE_URL:
    print(f"URL ends with /v2: {'✓ YES' if ALPACA_BASE_URL.endswith('/v2') else '❌ NO'}")

print(f"\n2. TESTING ALPACA_CLIENT.PY FUNCTIONS")
print("-" * 30)

try:
    print("\nImporting alpaca_client...")
    from backend.alpaca_client import get_account_info, ALPACA_BASE_URL as CLIENT_BASE_URL, HEADERS
    
    print(f"✓ Import successful")
    print(f"Client Base URL: {CLIENT_BASE_URL}")
    print(f"Headers Keys: {list(HEADERS.keys())}")
    
    print(f"\nTesting get_account_info()...")
    account = get_account_info()
    
    if account is None:
        print("❌ get_account_info() returned None")
        print("   This indicates an error occurred in the function")
    else:
        print("✅ get_account_info() returned data:")
        print(f"   Type: {type(account)}")
        if isinstance(account, dict):
            print(f"   Keys: {list(account.keys())}")
            print(f"   Status: {account.get('status', 'N/A')}")
            print(f"   Cash: {account.get('cash', 'N/A')}")
        else:
            print(f"   Value: {account}")
            
except Exception as e:
    print(f"❌ Error importing or testing alpaca_client: {e}")
    import traceback
    traceback.print_exc()

print(f"\n3. TESTING ALPACA_PORTFOLIO.PY FUNCTIONS") 
print("-" * 30)

try:
    print("\nImporting alpaca_portfolio...")
    from backend.alpaca_portfolio import get_live_positions
    
    print(f"✓ Import successful")
    
    print(f"\nTesting get_live_positions()...")
    positions = get_live_positions()
    
    if positions is None:
        print("❌ get_live_positions() returned None")
    elif isinstance(positions, list):
        print(f"✅ get_live_positions() returned list with {len(positions)} positions")
        if positions:
            print(f"   Sample position keys: {list(positions[0].keys())}")
    else:
        print(f"⚠️  get_live_positions() returned: {type(positions)}")
        
except Exception as e:
    print(f"❌ Error importing or testing alpaca_portfolio: {e}")
    import traceback
    traceback.print_exc()

print(f"\n4. TESTING ALPACA_ORDERS.PY FUNCTIONS")
print("-" * 30)

try:
    print("\nImporting alpaca_orders...")
    from backend.alpaca_orders import get_all_orders, get_filled_orders
    
    print(f"✓ Import successful")
    
    print(f"\nTesting get_all_orders()...")
    orders = get_all_orders()
    
    if orders is None:
        print("❌ get_all_orders() returned None")
    elif isinstance(orders, list):
        print(f"✅ get_all_orders() returned list with {len(orders)} orders")
    else:
        print(f"⚠️  get_all_orders() returned: {type(orders)}")
        
    print(f"\nTesting get_filled_orders()...")
    filled = get_filled_orders()
    
    if filled is None:
        print("❌ get_filled_orders() returned None")
    elif isinstance(filled, list):
        print(f"✅ get_filled_orders() returned list with {len(filled)} filled orders")
    else:
        print(f"⚠️  get_filled_orders() returned: {type(filled)}")
        
except Exception as e:
    print(f"❌ Error importing or testing alpaca_orders: {e}")
    import traceback
    traceback.print_exc()

print(f"\n5. MANUAL URL TESTING")
print("-" * 30)

import requests

# Test the exact URL construction from the code
try:
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }
    
    # Current implementation URL
    current_url = f"{ALPACA_BASE_URL}/v2/account"
    print(f"\nTesting current URL: {current_url}")
    
    response = requests.get(current_url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ SUCCESS - Account data retrieved")
        data = response.json()
        print(f"Account Status: {data.get('status', 'N/A')}")
        print(f"Account Cash: {data.get('cash', 'N/A')}")
    else:
        print(f"❌ FAILED - {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
    # Fixed URL 
    fixed_url = f"{ALPACA_BASE_URL.rstrip('/v2')}/v2/account"
    if fixed_url != current_url:
        print(f"\nTesting fixed URL: {fixed_url}")
        
        response = requests.get(fixed_url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS - Account data retrieved with fixed URL")
            data = response.json()
            print(f"Account Status: {data.get('status', 'N/A')}")
            print(f"Account Cash: {data.get('cash', 'N/A')}")
        else:
            print(f"❌ FAILED - {response.status_code}")
            print(f"Response: {response.text[:200]}")
    
except Exception as e:
    print(f"❌ Error in manual testing: {e}")

print(f"\n" + "=" * 60)
print("📊 TESTING COMPLETE")
print("=" * 60)