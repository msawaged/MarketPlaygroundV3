"""Shared access checks."""
import os
from typing import Optional

from fastapi import Header, HTTPException


def admin_only(x_admin_token: Optional[str] = Header(None)) -> None:
    """Owner-only routes: leftovers from the earlier app (debug, logs, the company Alpaca account,
    legacy analytics, legacy live trading). The current app doesn't use them."""
    expected = os.getenv("MP_ADMIN_TOKEN")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=403, detail="admin only")
