#!/usr/bin/env python3
"""
BACKEND ALPACA ROUTE TESTING
============================

Tests the actual MarketPlayground backend API routes that call Alpaca
to verify which ones are working vs failing, and capture exact error responses.
"""

import requests
import json
from urllib.parse import urljoin

# Backend base URL
BACKEND_BASE = "http://localhost:8000"  # Adjust if different

def test_backend_route(endpoint, method="GET", data=None):
    """Test a backend API route and capture detailed response."""
    url = urljoin(BACKEND_BASE, endpoint)
    
    print(f"\n🔍 Testing: {method} {endpoint}")
    print(f"   Full URL: {url}")
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            print(f"   ⚠️  Unsupported method: {method}")
            return False
            
        print(f"   Status: {response.status_code}")
        print(f"   Response time: {response.elapsed.total_seconds():.2f}s")
        
        if response.status_code == 200:
            try:
                resp_data = response.json()
                print(f"   ✅ SUCCESS: Response received")
                
                # Print relevant data based on endpoint
                if 'account' in resp_data:
                    account = resp_data['account']
                    if account:
                        print(f"   Account Status: {account.get('status')}")
                        print(f"   Buying Power: ${account.get('buying_power', 'N/A')}")
                        print(f"   Cash: ${account.get('cash', 'N/A')}")
                    else:
                        print(f"   ❌ Account data is None/empty")
                elif 'positions' in resp_data:
                    positions = resp_data['positions']
                    print(f"   Positions count: {len(positions) if positions else 0}")
                elif 'orders' in resp_data:
                    orders = resp_data['orders']
                    print(f"   Orders count: {len(orders) if orders else 0}")
                else:
                    print(f"   Response keys: {list(resp_data.keys()) if isinstance(resp_data, dict) else 'Not a dict'}")
                
                return True
                
            except json.JSONDecodeError:
                print(f"   ✅ SUCCESS but non-JSON response: {response.text[:200]}")
                return True
        else:
            print(f"   ❌ FAILED: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error response: {json.dumps(error_data, indent=2)}")
            except:
                print(f"   Error text: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ CONNECTION FAILED: Backend not running at {BACKEND_BASE}")
        return False
    except requests.exceptions.Timeout:
        print(f"   ❌ TIMEOUT: Request took too long")
        return False
    except Exception as e:
        print(f"   ❌ EXCEPTION: {e}")
        return False

def main():
    """Run comprehensive backend route testing."""
    
    print("=" * 60)
    print("🧪 BACKEND ALPACA ROUTE TESTING")
    print("=" * 60)
    
    print(f"\n🎯 Testing backend at: {BACKEND_BASE}")
    
    # Test basic health check first
    print(f"\n1. BASIC CONNECTIVITY TEST")
    print("-" * 30)
    
    try:
        response = requests.get(f"{BACKEND_BASE}/", timeout=5)
        print(f"✅ Backend is running (Status: {response.status_code})")
    except:
        print(f"❌ Backend is not accessible at {BACKEND_BASE}")
        print("   Make sure the backend is running with: python app.py")
        return
    
    # Test Alpaca-related routes
    print(f"\n2. ALPACA API ROUTES")
    print("-" * 30)
    
    alpaca_routes = [
        "/alpaca/account",
        "/alpaca/live_positions", 
        "/alpaca/orders",
        "/alpaca/orders/filled",
    ]
    
    results = {}
    
    for route in alpaca_routes:
        success = test_backend_route(route)
        results[route] = success
    
    # Test market data routes that use Alpaca
    print(f"\n3. MARKET DATA ROUTES (ALPACA-DEPENDENT)")
    print("-" * 30)
    
    market_routes = [
        "/market/expirations/AAPL",
        "/market/expirations/TSLA",
    ]
    
    for route in market_routes:
        success = test_backend_route(route)
        results[route] = success
    
    # Summary
    print(f"\n" + "=" * 60)
    print("📊 BACKEND ROUTE TEST SUMMARY")
    print("=" * 60)
    
    working_routes = [route for route, success in results.items() if success]
    failing_routes = [route for route, success in results.items() if not success]
    
    print(f"\n✅ WORKING ROUTES ({len(working_routes)}):")
    for route in working_routes:
        print(f"   {route}")
    
    print(f"\n❌ FAILING ROUTES ({len(failing_routes)}):")
    for route in failing_routes:
        print(f"   {route}")
    
    if failing_routes:
        print(f"\n💡 DIAGNOSIS:")
        print(f"   All failing routes likely have the same URL construction issue")
        print(f"   identified in the direct API testing (double /v2/v2/ problem)")
    
    success_rate = len(working_routes) / len(results) * 100
    print(f"\n📈 Success Rate: {success_rate:.1f}% ({len(working_routes)}/{len(results)})")
    
    print(f"\n🔧 NEXT STEPS:")
    if failing_routes:
        print(f"   1. Fix URL construction in Alpaca client files")
        print(f"   2. Update .env to remove /v2 from ALPACA_BASE_URL")
        print(f"   3. Test all routes again to verify fixes")
    else:
        print(f"   All routes working! Alpaca integration is healthy.")

if __name__ == "__main__":
    main()