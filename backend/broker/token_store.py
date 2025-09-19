"""
backend/broker/token_store.py
-----------------------------
Tiny provider-agnostic token store for OAuth access/refresh tokens.

- Works for Alpaca now (paper/live), but is generic so we can add others later.
- Persists to backend/data/broker_tokens.json so it survives restarts.
- Keyed by (user_id, provider, env).

Security notes:
- For beta/dev this is fine. For production, switch to a real DB and encrypt tokens at rest.
"""

from __future__ import annotations
import json, time
from pathlib import Path
from typing import Optional, Dict, Any

# Persist inside the backend/data folder (which already exists in your repo)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
TOKENS_PATH = DATA_DIR / "broker_tokens.json"

def _load() -> Dict[str, Any]:
    """Load the token DB from disk (or empty dict if missing/corrupted)."""
    if TOKENS_PATH.exists():
        try:
            return json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save(db: Dict[str, Any]) -> None:
    """Write the token DB to disk (pretty-printed)."""
    TOKENS_PATH.write_text(json.dumps(db, indent=2), encoding="utf-8")

def _key(user_id: str, provider: str, env_: str) -> str:
    """
    Build a stable key. Examples:
      "murad|alpaca|paper"
      "f8a2...-uuid|alpaca|live"
    """
    return f"{user_id.strip()}|{provider.strip().lower()}|{env_.strip().lower()}"

def set_token(
    user_id: str,
    provider: str,                # e.g., "alpaca"
    env_: str,                    # "paper" | "live"
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_at: Optional[int] = None,  # epoch seconds (None = unknown/no expiry)
    scope: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Create/update a token record for (user_id, provider, env)."""
    db = _load()
    db[_key(user_id, provider, env_)] = {
        "user_id": user_id,
        "provider": provider.lower(),
        "env": env_.lower(),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "scope": scope,
        "extra": extra or {},
        "updated_at": int(time.time()),
    }
    _save(db)

def get_token(user_id: str, provider: str, env_: str) -> Optional[Dict[str, Any]]:
    """Fetch a token record or None if missing."""
    db = _load()
    return db.get(_key(user_id, provider, env_))

def delete_token(user_id: str, provider: str, env_: str) -> bool:
    """Delete a token record. Returns True iff removed."""
    db = _load()
    k = _key(user_id, provider, env_)
    if k in db:
        del db[k]
        _save(db)
        return True
    return False

def list_tokens_for_user(user_id: str) -> Dict[str, Any]:
    """Return all entries for a given user_id (handy for debugging)."""
    db = _load()
    prefix = f"{user_id}|"
    return {k: v for k, v in db.items() if k.startswith(prefix)}

