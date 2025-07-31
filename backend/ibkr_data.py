# backend/ibkr_data.py

# from ib_insync import IB, Stock
import os
import asyncio

# ✅ IBKR Gateway Config (env override or default to localhost:4002)
IB_GATEWAY_HOST = os.getenv("IB_GATEWAY_HOST", "127.0.0.1")
IB_GATEWAY_PORT = int(os.getenv("IB_GATEWAY_PORT", 4001))  # Paper Trading Port
CLIENT_ID = int(os.getenv("IB_CLIENT_ID", 2))  # Use a different ID from test_connection

def get_ibkr_price(ticker: str) -> float:
    """
    ✅ Fetch real-time price from IBKR Gateway using ib_insync.
    - Handles event loop manually (FastAPI safe)
    - Returns price as float
    - Returns None if error or disconnected
    """
    try:
        # 🧠 Setup asyncio manually (required in FastAPI context)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        ib = IB()
        ib.connect(IB_GATEWAY_HOST, IB_GATEWAY_PORT, clientId=CLIENT_ID, timeout=5)

        if not ib.isConnected():
            print(f"[IBKR] ❌ Could not connect to gateway at {IB_GATEWAY_HOST}:{IB_GATEWAY_PORT}")
            return None

        contract = Stock(ticker, "SMART", "USD")
        ib.qualifyContracts(contract)

        # 🕒 Request real-time market data
        ticker_data = ib.reqMktData(contract, "", False, False)
        ib.sleep(2)  # Wait briefly to allow data to populate

        price = ticker_data.last if ticker_data.last else ticker_data.marketPrice()
        ib.cancelMktData(ticker_data)
        ib.disconnect()

        if price is not None and price > 0:
            print(f"[IBKR] ✅ {ticker} price: {price}")
            return price
        else:
            print(f"[IBKR] ⚠️ No valid price for {ticker}")
            return None

    except Exception as e:
        print(f"[IBKR] 🚨 Error fetching {ticker} price: {e}")
        return None
