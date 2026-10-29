"""
Face ID / Touch ID sign-in (passkeys, WebAuthn).

A passkey belongs to one web address (the "relying party"), taken from MP_SITE_URL, so moving the site to a new
domain is a settings change; passkeys made on the old address simply stop matching and people turn Face ID on
again (passwords keep working throughout). Challenges live in kv_cache for 5 minutes and are single use.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

from . import auth, db
from .auth import AuthError

CHALLENGE_TTL = timedelta(minutes=5)


def _origins() -> list[str]:
    site = (os.getenv("MP_SITE_URL") or "https://marketplayground-web.onrender.com").rstrip("/")
    extra = [o.strip().rstrip("/") for o in os.getenv("MP_PASSKEY_ORIGINS", "").split(",") if o.strip()]
    return [site] + extra


def _rp_id(origin: Optional[str] = None) -> str:
    """The site's host. A request from an extra allowed origin (local testing) uses that origin's host."""
    allowed = _origins()
    o = (origin or "").rstrip("/")
    return urlparse(o if o in allowed else allowed[0]).hostname or "localhost"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _put_challenge(key: str, challenge: bytes, extra: Optional[dict] = None) -> None:
    db.execute("DELETE FROM kv_cache WHERE k = ?", (key,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)",
               (key, json.dumps({"c": challenge.hex(), **(extra or {})}), _now().isoformat()))


def _take_challenge(key: str) -> dict:
    row = db.query_one("SELECT v, created_at FROM kv_cache WHERE k = ?", (key,))
    db.execute("DELETE FROM kv_cache WHERE k = ?", (key,))  # single use
    if not row or _now() - datetime.fromisoformat(row["created_at"]) > CHALLENGE_TTL:
        raise AuthError("That took too long. Please try again.", 400)
    return json.loads(row["v"])


def register_options(token: Optional[str], origin: Optional[str] = None) -> dict:
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
                                          ResidentKeyRequirement, UserVerificationRequirement)
    from webauthn.helpers import base64url_to_bytes
    acc = auth.require(token)
    have = db.query("SELECT credential_id FROM passkeys WHERE account_id = ?", (acc["id"],))
    opts = generate_registration_options(
        rp_id=_rp_id(origin), rp_name="MarketPlayground",
        user_id=acc["id"].encode(), user_name=acc["email"], user_display_name=acc.get("name") or acc["email"],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED, user_verification=UserVerificationRequirement.REQUIRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(r["credential_id"])) for r in have],
    )
    _put_challenge(f"pk_reg:{acc['id']}", opts.challenge)
    return json.loads(options_to_json(opts))


def register_verify(token: Optional[str], credential: dict, origin: Optional[str] = None, label: str = "") -> dict:
    from webauthn import verify_registration_response
    from webauthn.helpers import bytes_to_base64url
    acc = auth.require(token)
    ch = _take_challenge(f"pk_reg:{acc['id']}")
    try:
        v = verify_registration_response(credential=credential, expected_challenge=bytes.fromhex(ch["c"]),
                                         expected_rp_id=_rp_id(origin), expected_origin=_origins(),
                                         require_user_verification=True)
    except Exception as e:
        raise AuthError("Face ID setup didn't go through. Please try again.", 400) from e
    cid = bytes_to_base64url(v.credential_id)
    db.execute("DELETE FROM passkeys WHERE credential_id = ?", (cid,))
    db.execute("INSERT INTO passkeys (credential_id, account_id, public_key, sign_count, created_at, label) VALUES (?,?,?,?,?,?)",
               (cid, acc["id"], bytes_to_base64url(v.credential_public_key), int(v.sign_count), _now().isoformat(),
                (label or "")[:60]))
    return {"ok": True}


def login_options(origin: Optional[str] = None) -> dict:
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers.structs import UserVerificationRequirement
    opts = generate_authentication_options(rp_id=_rp_id(origin), user_verification=UserVerificationRequirement.REQUIRED)
    cid = secrets.token_urlsafe(16)
    _put_challenge(f"pk_auth:{cid}", opts.challenge)
    return {"challenge_id": cid, "options": json.loads(options_to_json(opts))}


def login_verify(challenge_id: str, credential: dict, device_id: Optional[str] = None,
                 origin: Optional[str] = None) -> dict:
    from webauthn import verify_authentication_response
    from webauthn.helpers import base64url_to_bytes
    ch = _take_challenge(f"pk_auth:{challenge_id}")
    cid = str((credential or {}).get("id") or "")
    pk = db.query_one("SELECT * FROM passkeys WHERE credential_id = ?", (cid,))
    if not pk:
        raise AuthError("This Face ID isn't set up for MarketPlayground yet. Log in with your password, then turn it on.", 401)
    try:
        v = verify_authentication_response(credential=credential, expected_challenge=bytes.fromhex(ch["c"]),
                                           expected_rp_id=_rp_id(origin), expected_origin=_origins(),
                                           credential_public_key=base64url_to_bytes(pk["public_key"]),
                                           credential_current_sign_count=int(pk["sign_count"] or 0),
                                           require_user_verification=True)
    except Exception as e:
        raise AuthError("Face ID sign-in didn't go through. Please try again or use your password.", 401) from e
    db.execute("UPDATE passkeys SET sign_count = ?, last_used = ? WHERE credential_id = ?",
               (int(v.new_sign_count), _now().isoformat(), cid))
    acc = db.query_one("SELECT * FROM accounts WHERE id = ?", (pk["account_id"],))
    if not acc:
        raise AuthError("That account no longer exists.", 401)
    db.execute("UPDATE accounts SET last_login = ? WHERE id = ?", (_now().isoformat(), acc["id"]))
    moved = auth._merge_device(auth._clean_device(device_id), acc["uid"])
    return {"token": auth._new_session(acc["id"]), "account": auth._public(acc), "moved_beliefs": moved}


def status(token: Optional[str]) -> dict:
    acc = auth.require(token)
    n = db.query_one("SELECT COUNT(*) AS n FROM passkeys WHERE account_id = ?", (acc["id"],))
    return {"passkeys": int(n["n"] if n else 0)}


def remove_all(token: Optional[str]) -> dict:
    acc = auth.require(token)
    db.execute("DELETE FROM passkeys WHERE account_id = ?", (acc["id"],))
    return {"ok": True}
