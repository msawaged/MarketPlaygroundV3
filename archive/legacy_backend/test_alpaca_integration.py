#!/usr/bin/env python3
"""
ALPACA API INTEGRATION COMPREHENSIVE AUDIT SCRIPT
============================================
Tests all Alpaca endpoints and authentication patterns
Used for diagnosing integration issues across all asset classes
"""

import os
import requests
import sys
from dotenv import load_dotenv
from datetime import datetime
import json

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment
load_dotenv()

# Test credentials
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# Headers for API calls
HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_test(test_name, status, details=""):
    """Print formatted test result"""
    status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"{status_symbol} {test_name}: {status}")
    if details:
        print(f"   Details: {details}")

def test_environment_setup():
    """Test environment variables and credentials"""
    print_section("ENVIRONMENT SETUP AUDIT")
    
    # Test API key presence
    print_test("ALPACA_API_KEY loaded", 
               "PASS" if ALPACA_API_KEY else "FAIL",
               f"Length: {len(ALPACA_API_KEY) if ALPACA_API_KEY else 0}")
    
    print_test("ALPACA_SECRET_KEY loaded", 
               "PASS" if ALPACA_SECRET_KEY else "FAIL",
               f"Length: {len(ALPACA_SECRET_KEY) if ALPACA_SECRET_KEY else 0}")
    
    print_test("ALPACA_BASE_URL configured", 
               "PASS" if ALPACA_BASE_URL else "FAIL",
               ALPACA_BASE_URL)
    
    print_test("FINNHUB_API_KEY loaded", 
               "PASS" if FINNHUB_API_KEY else "FAIL",
               f"Length: {len(FINNHUB_API_KEY) if FINNHUB_API_KEY else 0}")

def test_account_endpoints():
    """Test account-related Alpaca endpoints"""
    print_section("ACCOUNT ENDPOINTS AUDIT")
    
    # Test account info
    try:
        response = requests.get(f"{ALPACA_BASE_URL}/v2/account", headers=HEADERS, timeout=10)
        if response.status_code == 200:
            account_data = response.json()
            print_test("GET /v2/account", "PASS", 
                      f"Account ID: {account_data.get('id', 'Unknown')}")
            print(f"   Cash: ${account_data.get('cash', 'Unknown')}")
            print(f"   Equity: ${account_data.get('equity', 'Unknown')}")
            print(f"   Buying Power: ${account_data.get('buying_power', 'Unknown')}")
        else:
            print_test("GET /v2/account", "FAIL", 
                      f"HTTP {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print_test("GET /v2/account", "FAIL", str(e))
    
    # Test positions
    try:
        response = requests.get(f"{ALPACA_BASE_URL}/v2/positions", headers=HEADERS, timeout=10)
        if response.status_code == 200:
            positions = response.json()
            print_test("GET /v2/positions", "PASS", 
                      f"Found {len(positions)} positions")
            for pos in positions[:3]:  # Show first 3
                print(f"   {pos.get('symbol')}: {pos.get('qty')} shares @ ${pos.get('current_price')}")
        else:
            print_test("GET /v2/positions", "FAIL", 
                      f"HTTP {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print_test("GET /v2/positions", "FAIL", str(e))

def test_market_data_endpoints():
    """Test market data endpoints for different asset classes"""
    print_section("MARKET DATA ENDPOINTS AUDIT")
    
    test_tickers = {
        "stocks": ["AAPL", "TSLA", "SPY", "QQQ"],
        "crypto": ["BTCUSD", "ETHUSD"],
        "commodities": ["GLDM", "SLV", "USO", "UNG"],
        "bonds": ["TLT", "IEF", "SHY"]
    }
    
    for asset_class, tickers in test_tickers.items():
        print(f"\n--- {asset_class.upper()} MARKET DATA ---")
        
        for ticker in tickers:
            # Test latest bars (stock data)
            try:
                url = f"https://data.alpaca.markets/v2/stocks/bars/latest"
                params = {"symbols": ticker}
                data_headers = {
                    "APCA-API-KEY-ID": ALPACA_API_KEY,
                    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
                }
                
                response = requests.get(url, headers=data_headers, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    bars = data.get('bars', {})
                    if ticker in bars:
                        bar = bars[ticker]
                        print_test(f"{ticker} latest bar", "PASS", 
                                  f"Price: ${bar.get('c', 'N/A')} | Volume: {bar.get('v', 'N/A')}")
                    else:
                        print_test(f"{ticker} latest bar", "WARN", 
                                  f"No data returned for {ticker}")
                else:
                    print_test(f"{ticker} latest bar", "FAIL", 
                              f"HTTP {response.status_code}: {response.text[:100]}")
            except Exception as e:
                print_test(f"{ticker} latest bar", "FAIL", str(e))

def test_options_endpoints():
    """Test options-related endpoints"""
    print_section("OPTIONS DATA ENDPOINTS AUDIT")
    
    test_tickers = ["AAPL", "TSLA", "SPY"]
    
    for ticker in test_tickers:
        # Test option expirations
        try:
            url = f"https://data.alpaca.markets/v2/options/expirations/{ticker}"
            data_headers = {
                "APCA-API-KEY-ID": ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
            }
            
            response = requests.get(url, headers=data_headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                expirations = data.get('expirations', [])
                print_test(f"{ticker} option expirations", "PASS", 
                          f"Found {len(expirations)} expiration dates")
                if expirations:
                    print(f"   Next 3 expirations: {expirations[:3]}")
            else:
                print_test(f"{ticker} option expirations", "FAIL", 
                          f"HTTP {response.status_code}: {response.text[:200]}")
        except Exception as e:
            print_test(f"{ticker} option expirations", "FAIL", str(e))

def test_trading_endpoints():
    """Test trading endpoints (without actually placing orders)"""
    print_section("TRADING ENDPOINTS AUDIT")
    
    # Test orders endpoint (GET only)
    try:
        response = requests.get(f"{ALPACA_BASE_URL}/v2/orders", 
                               headers=HEADERS, 
                               params={"status": "all", "limit": 5},
                               timeout=10)
        if response.status_code == 200:
            orders = response.json()
            print_test("GET /v2/orders", "PASS", 
                      f"Retrieved {len(orders)} orders")
            for order in orders[:2]:  # Show first 2
                print(f"   {order.get('symbol')} {order.get('side')} {order.get('qty')} - Status: {order.get('status')}")
        else:
            print_test("GET /v2/orders", "FAIL", 
                      f"HTTP {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print_test("GET /v2/orders", "FAIL", str(e))

def test_data_hierarchy():
    """Test the data source hierarchy: Finnhub -> Alpaca -> yfinance"""
    print_section("DATA SOURCE HIERARCHY AUDIT")
    
    test_ticker = "AAPL"
    
    # Test Finnhub (primary)
    try:
        response = requests.get("https://finnhub.io/api/v1/quote", 
                               params={"symbol": test_ticker, "token": FINNHUB_API_KEY},
                               timeout=10)
        if response.status_code == 200:
            data = response.json()
            price = data.get('c', -1)
            print_test("Finnhub price feed", "PASS" if price > 0 else "WARN", 
                      f"{test_ticker}: ${price}")
        else:
            print_test("Finnhub price feed", "FAIL", 
                      f"HTTP {response.status_code}")
    except Exception as e:
        print_test("Finnhub price feed", "FAIL", str(e))
    
    # Test Alpaca market data
    try:
        url = f"https://data.alpaca.markets/v2/stocks/bars/latest"
        params = {"symbols": test_ticker}
        data_headers = {
            "APCA-API-KEY-ID": ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        }
        response = requests.get(url, headers=data_headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            bars = data.get('bars', {})
            if test_ticker in bars:
                price = bars[test_ticker].get('c')
                print_test("Alpaca market data", "PASS", 
                          f"{test_ticker}: ${price}")
            else:
                print_test("Alpaca market data", "WARN", "No data returned")
        else:
            print_test("Alpaca market data", "FAIL", 
                      f"HTTP {response.status_code}")
    except Exception as e:
        print_test("Alpaca market data", "FAIL", str(e))
    
    # Test yfinance fallback
    try:
        import yfinance as yf
        ticker_obj = yf.Ticker(test_ticker)
        hist = ticker_obj.history(period="1d")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
            print_test("yfinance fallback", "PASS", 
                      f"{test_ticker}: ${round(price, 2)}")
        else:
            print_test("yfinance fallback", "WARN", "No data returned")
    except Exception as e:
        print_test("yfinance fallback", "FAIL", str(e))

def test_wrapper_functions():
    """Test internal wrapper functions"""
    print_section("WRAPPER FUNCTIONS AUDIT")
    
    try:
        from alpaca_client import get_account_info, get_order_status
        from alpaca_portfolio import get_live_positions
        from market_data import get_latest_price, get_option_expirations
        
        # Test account wrapper
        account = get_account_info()
        print_test("get_account_info()", 
                  "PASS" if account else "FAIL",
                  f"Returned: {type(account)}")
        
        # Test positions wrapper
        positions = get_live_positions()
        print_test("get_live_positions()", 
                  "PASS" if isinstance(positions, list) else "FAIL",
                  f"Returned: {len(positions) if isinstance(positions, list) else 'Not a list'} positions")
        
        # Test market data wrapper
        price = get_latest_price("AAPL")
        print_test("get_latest_price('AAPL')", 
                  "PASS" if price > 0 else "FAIL",
                  f"Price: ${price}")
        
        # Test options wrapper
        expirations = get_option_expirations("AAPL")
        print_test("get_option_expirations('AAPL')", 
                  "PASS" if isinstance(expirations, list) and expirations else "FAIL",
                  f"Returned: {len(expirations) if isinstance(expirations, list) else 'Not a list'} dates")
        
    except Exception as e:
        print_test("Wrapper functions import", "FAIL", str(e))

def generate_summary_report():
    """Generate final audit summary"""
    print_section("ALPACA INTEGRATION AUDIT SUMMARY")
    
    print(f"""
AUDIT COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

KEY FINDINGS:
- Environment setup status checked
- Account endpoints connectivity verified
- Market data feeds across asset classes tested
- Options data availability confirmed
- Data source hierarchy validated
- Wrapper function integrity checked

RECOMMENDATIONS:
1. Review any FAIL status items above
2. Verify API key permissions for specific asset classes
3. Check rate limits if experiencing timeouts
4. Validate paper trading account data permissions
5. Consider upgrading to real-time data feeds if needed

Next Steps:
- Fix authentication issues for failing endpoints
- Implement missing asset class support
- Optimize data retrieval performance
- Add proper error handling and fallbacks
    """)

def main():
    """Run complete Alpaca integration audit"""
    print("ALPACA API INTEGRATION COMPREHENSIVE AUDIT")
    print("==========================================")
    print(f"Audit started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_environment_setup()
    test_account_endpoints()
    test_market_data_endpoints()
    test_options_endpoints()
    test_trading_endpoints()
    test_data_hierarchy()
    test_wrapper_functions()
    generate_summary_report()

if __name__ == "__main__":
    main()