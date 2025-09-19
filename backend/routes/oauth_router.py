"""
oauth_router.py
---------------
Alpaca Connect (OAuth) stubs with PKCE placeholders.

Beta mode:
- If OAuth env vars are missing, we still let you test by manually seeding a token
  via /oauth/dev/set_token. That uses the token_store from Step 1.

Prod mode (later):
- Fill in PKCE + token exchange against Alpaca's OAuth endpoints and store tokens
  per user (paper/live).
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import os
from backend.broker.token_store import set_token
from backend.broker.providers import ALPACA_OAUTH_CLIENT, ALPACA_HOSTS

router = APIRouter(prefix="/oauth", tags=["OAuth"])

@router.post("/start")
def oauth_start(
    user_id: str,
    env: str = Query("paper", pattern="^(paper|live)$"),
    state: Optional[str] = None,
):
    """
    Returns the Alpaca authorization URL for your frontend to open (popup/new tab).
    NOTE: In beta, this returns 400 if client env vars aren't configured.
    """
    cfg = ALPACA_OAUTH_CLIENT()
    if not (cfg["client_id"] and cfg["redirect_uri"]):
        raise HTTPException(status_code=400, detail="OAuth app not configured (set MP_ALPACA_CLIENT_ID and MP_ALPACA_REDIRECT_URI).")

    hosts = ALPACA_HOSTS(env)
    # TODO: add PKCE code_challenge + real 'state'
    scopes = cfg["scopes"] or "account:read trading data"
    auth_url = (
        f'{hosts["oauth"]}/oauth/authorize?'
        f'client_id={cfg["client_id"]}'
        f'&response_type=code'
        f'&redirect_uri={cfg["redirect_uri"]}'
        f'&scope={scopes.replace(" ","%20")}'
        f'&state={state or user_id}'
    )
    return {"url": auth_url, "env": env, "user_id": user_id}

@router.get("/callback")
def oauth_callback(code: Optional[str] = None, state: Optional[str] = None):
    """
    Placeholder for token exchange:
      POST {oauth_host}/oauth/token with code, client_id, client_secret (or PKCE)
    For now, just returns a friendly message so FE can continue.
    """
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    # TODO: exchange code -> access/refresh, set_token(user_id,...)
    return {"status": "callback_received", "code": code, "state": state}

# ---------- DEV ONLY: seed a token quickly so you can test proxies today ----------
@router.post("/dev/set_token")
def dev_set_token(
    user_id: str,
    access_token: str,
    env: str = Query("paper", pattern="^(paper|live)$"),
    refresh_token: Optional[str] = None,
    expires_at: Optional[int] = None,
    scope: Optional[str] = "account:read trading data",
):
    """
    Dev helper: store a token manually for the given user/env.
    Lets you test /broker/* routes immediately without full OAuth.
    """
    set_token(user_id, "alpaca", env, access_token, refresh_token, expires_at, scope, extra={"source": "dev"})
    return {"ok": True, "user_id": user_id, "env": env}
