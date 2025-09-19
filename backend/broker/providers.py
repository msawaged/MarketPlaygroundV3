"""
backend/broker/providers.py
---------------------------
Centralizes broker provider metadata + HTTP helpers.

Scope (beta):
- Alpaca only (paper + live). Provider-agnostic structure so we can plug in others later.
- No network calls on import. Pure config + helpers.

Usage (coming next):
- /oauth/start, /oauth/callback will use ALPACA_OAUTH_* values.
- /broker/* proxy routes will:
    1) read user's token from token_store (Step 1),
    2) pick host by env ('paper' or 'live'),
    3) call alpaca_api() helper to hit /v2/* endpoints with the user's token.
"""

from __future__ import annotations
from typing import Dict, Optional, Tuple
import os
import time
import json
import requests

# Local token store (Step 1)
from backend.broker.token_store import get_token, set_token

# ------------------------------
# Provider registry (Alpaca only)
# ------------------------------

def ALPACA_HOSTS(env_: str) -> Dict[str, str]:
    """
    Return base URLs for Alpaca depending on environment.
    env_ : 'paper' | 'live'
    """
    env = (env_ or "paper").lower()
    if env not in ("paper", "live"):
        env = "paper"
    trading = "https://paper-api.alpaca.markets" if env == "paper" else "https://api.alpaca.markets"
    data = "https://data.alpaca.markets"  # same for paper/live
    oauth = "https://app.alpaca.markets"  # OAuth/Connect host (authorization UI)
    return {"trading": trading, "data": data, "oauth": oauth, "env": env}

# These will be set in your environment / dashboard when you register your OAuth app
def ALPACA_OAUTH_CLIENT() -> Dict[str, Optional[str]]:
    """
    Read OAuth client config from env (set these when you register with Alpaca):
      MP_ALPACA_CLIENT_ID
      MP_ALPACA_CLIENT_SECRET      (server only)
      MP_ALPACA_REDIRECT_URI       (e.g., https://your.app/api/oauth/callback)
      MP_ALPACA_SCOPES             (space-separated, e.g., 'account:read trading data')
    """
    return {
        "client_id": os.getenv("MP_ALPACA_CLIENT_ID"),
        "client_secret": os.getenv("MP_ALPACA_CLIENT_SECRET"),
        "redirect_uri": os.getenv("MP_ALPACA_REDIRECT_URI"),
        "scopes": os.getenv("MP_ALPACA_SCOPES", "account:read trading data"),
    }

# ---------------------------------------
# Token helpers (refresh placeholder hook)
# ---------------------------------------

def token_is_expired(token_rec: dict) -> bool:
    """
    Return True if token has an expires_at in the past (with small skew).
    If expires_at is None, assume not expired.
    """
    exp = token_rec.get("expires_at")
    if not exp:
        return False
    # 60s skew safety
    return int(time.time()) >= int(exp) - 60

def refresh_alpaca_token_if_needed(user_id: str, env_: str) -> dict:
    """
    Placeholder for OAuth refresh. For paper Beta, many flows use long-lived tokens.
    If you have refresh_token + client_secret, implement refresh here:
      POST {oauth_host}/oauth/token
        grant_type=refresh_token
        refresh_token=...
        client_id=...
        client_secret=...
    Then set_token(... new access_token, expires_at ...).
    """
    rec = get_token(user_id, "alpaca", env_)
    if not rec:
        raise RuntimeError(f"No Alpaca token for user {user_id} ({env_})")
    if token_is_expired(rec):
        # TODO: implement refresh call once you enable Connect/OAuth officially.
        # For now, just raise so we notice it during beta if it ever occurs.
        raise RuntimeError("Alpaca access token expired; refresh flow not implemented yet.")
    return rec

# ---------------------------------------
# Low-level HTTP to Alpaca (user-scoped)
# ---------------------------------------

def alpaca_api(
    user_id: str,
    env_: str,
    method: str,
    path: str,
    *,
    json_body: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: int = 15,
) -> Tuple[int, dict]:
    """
    User-scoped request to Alpaca TRADING API.

    Priority (multi-user safe):
    1) If THIS user has an OAuth token, try it first (Bearer).
       - If Alpaca replies 401/403, retry ONCE with API key/secret (beta fallback).
    2) If no user token exists at all, short-circuit directly to API key/secret (beta fallback).

    Toggle fallback via env:
      MP_ALLOW_APIKEY_FALLBACK=true|false   (default: true)

    NOTE: This does NOT call a refresh flow in beta. You’ll add that later.
    """
    hosts = ALPACA_HOSTS(env_)
    base = hosts["trading"]
    if not base:
        raise RuntimeError("Alpaca trading host not configured")
    url = f"{base}{path}"

    # ---------- Read THIS user's token (multi-user path) ----------
    rec = get_token(user_id, "alpaca", env_)
    access_token = (rec or {}).get("access_token")

    # ---------- Helper: call with API keys (fallback) ----------
    def _call_with_apikeys() -> Tuple[int, dict]:
        allow_fallback = os.getenv("MP_ALLOW_APIKEY_FALLBACK", "true").lower() == "true"
        if not allow_fallback:
            # Fallback not allowed; pretend unauthorized
            return 401, {"detail": {"message": "fallback disabled (MP_ALLOW_APIKEY_FALLBACK=false)"}}
        key = os.getenv("ALPACA_API_KEY_ID")
        sec = os.getenv("ALPACA_API_SECRET_KEY")
        if not (key and sec):
            return 401, {"detail": {"message": "no API keys set for fallback"}}
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": sec,
        }
        # DEBUG (optional): uncomment to see when fallback is used
        # print("[broker][fallback] Using API keys for", user_id, env_, path)
        r2 = requests.request(method.upper(), url, headers=headers, json=json_body, params=params, timeout=timeout)
        try:
            p2 = r2.json()
        except Exception:
            p2 = {"raw": r2.text}
        return r2.status_code, p2

    # ---------- If NO user token at all → short-circuit straight to API keys ----------
    if not access_token:
        return _call_with_apikeys()

    # ---------- Attempt #1: OAuth Bearer for THIS user ----------
    headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}
    r = requests.request(method.upper(), url, headers=headers, json=json_body, params=params, timeout=timeout)
    try:
        p = r.json()
    except Exception:
        p = {"raw": r.text}

    # If not auth failure, return result
    if r.status_code not in (401, 403):
        return r.status_code, p

    # ---------- Attempt #2: Retry once with API keys (beta fallback) ----------
    return _call_with_apikeys()



def alpaca_data_api(
    user_id: str,
    env_: str,
    path: str,
    *,
    params: Optional[dict] = None,
    timeout: int = 15,
) -> Tuple[int, dict]:
    """
    Make a user-scoped request to Alpaca DATA API with the stored OAuth token.
    Useful for quotes/bars/options data (entitlements required).
    """
    hosts = ALPACA_HOSTS(env_)
    base = hosts["data"]
    rec = refresh_alpaca_token_if_needed(user_id, env_)
    access_token = rec.get("access_token")
    if not access_token:
        raise RuntimeError("Missing access_token in token store")

    url = f"{base}{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    resp = requests.get(url, headers=headers, params=params, timeout=timeout)
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": resp.text}
    return resp.status_code, payload
