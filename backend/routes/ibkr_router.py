# backend/routes/ibkr_router.py

from fastapi import APIRouter
from ib_insync import IB
import os
import asyncio

router = APIRouter()

# ✅ IB Gateway connection details (default to port 4002 if not overridden)
IB_GATEWAY_HOST = os.getenv("IB_GATEWAY_HOST", "127.0.0.1")
IB_GATEWAY_PORT = int(os.getenv("IB_GATEWAY_PORT", 4002))  # 4002 = default for IB Gateway
CLIENT_ID = int(os.getenv("IB_CLIENT_ID", 1))


@router.get("/test_connection")
def test_ibkr_connection():
    """
    ✅ Connects to IBKR Gateway using ib_insync.
    - Handles FastAPI event loop properly
    - Returns account summary if successful
    """
    try:
        # 🛠 Fix FastAPI thread: set manual asyncio event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        ib = IB()
        ib.connect(IB_GATEWAY_HOST, IB_GATEWAY_PORT, clientId=CLIENT_ID, timeout=5)

        if not ib.isConnected():
            return {
                "status": "failed ❌",
                "error": f"Could not connect to IBKR Gateway at {IB_GATEWAY_HOST}:{IB_GATEWAY_PORT}"
            }

        # ✅ Fetch account summary
        account_summary = ib.accountSummary()
        summary_dict = {item.tag: item.value for item in account_summary}

        ib.disconnect()

        return {
            "status": "connected ✅",
            "account_summary": summary_dict
        }

    except Exception as e:
        return {
            "status": "failed ❌",
            "error": str(e)
        }
