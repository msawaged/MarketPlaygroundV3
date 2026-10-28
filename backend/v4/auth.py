"""
Accounts: email + password, no extra services.

- Passwords: scrypt (Python standard library) with a random salt per account; never stored or logged.
- Sessions: random 32-byte tokens; only their SHA-256 is stored. Sent as "Authorization: Bearer <token>".
- Identity: every device already has an anonymous id (mp_user_id). An account takes over the id of the
  device it was created on (its `uid`), and logging in on another device moves that device's anonymous
  beliefs into the account, so My calls follows you everywhere.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import db, mailer

SESSION_DAYS = int(os.getenv("MP_SESSION_DAYS", "60"))
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,24}$")
_N, _R, _P = 2 ** 14, 8, 1


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def check_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got, base64.b64decode(dk))
    except Exception:
        return False


def _clean_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not EMAIL.match(e):
        raise AuthError("That doesn't look like an email address.")
    return e


def _check_new_password(pw: str) -> None:
    if len(pw or "") < 8:
        raise AuthError("Use at least 8 characters for your password.")
    if len(pw) > 200:
        raise AuthError("That password is too long.")


def _clean_device(device_id: Optional[str]) -> Optional[str]:
    d = (device_id or "").strip()
    return d if re.fullmatch(r"u-[A-Za-z0-9-]{6,64}", d) else None


def _public(acc: dict) -> dict:
    return {"id": acc["id"], "uid": acc["uid"], "email": acc["email"], "name": acc.get("name") or "",
            "created_at": acc["created_at"]}


def _new_session(account_id: str) -> str:
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO sessions (token_hash, account_id, created_at, expires_at) VALUES (?,?,?,?)",
               (hashlib.sha256(token.encode()).hexdigest(), account_id, _now().isoformat(),
                (_now() + timedelta(days=SESSION_DAYS)).isoformat()))
    return token


def _merge_device(device_id: Optional[str], uid: str) -> int:
    """Move an anonymous device's beliefs and votes into the account."""
    if not device_id or device_id == uid:
        return 0
    n = db.query_one("SELECT COUNT(*) AS n FROM beliefs WHERE user_id = ?", (device_id,))
    db.execute("UPDATE beliefs SET user_id = ? WHERE user_id = ?", (uid, device_id))
    db.execute("UPDATE feedback SET user_id = ? WHERE user_id = ?", (uid, device_id))
    return int(n["n"] if n else 0)


def verification_required() -> bool:
    """On whenever email can be sent (MP_REQUIRE_VERIFY=off turns it off; =on forces it)."""
    v = os.getenv("MP_REQUIRE_VERIFY", "auto").lower()
    if v in ("off", "false", "0"):
        return False
    if v in ("on", "true", "1"):
        return True
    return mailer.configured() or bool(os.getenv("MP_MAIL_TEST_SINK"))


def _site() -> str:
    return os.getenv("MP_SITE_URL", "https://marketplayground-web.onrender.com").rstrip("/")


def _new_email_token(account_id: str, kind: str, hours: int) -> str:
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO email_tokens (token_hash, account_id, kind, created_at, expires_at, used) VALUES (?,?,?,?,?,0)",
               (hashlib.sha256(token.encode()).hexdigest(), account_id, kind, _now().isoformat(),
                (_now() + timedelta(hours=hours)).isoformat()))
    return token


def _use_email_token(token: str, kind: str) -> dict:
    row = db.query_one("SELECT * FROM email_tokens WHERE token_hash = ? AND kind = ?",
                       (hashlib.sha256((token or "").encode()).hexdigest(), kind))
    if not row or row["used"] or row["expires_at"] < _now().isoformat():
        raise AuthError("That link has expired or was already used. Ask for a new one.", 400)
    db.execute("UPDATE email_tokens SET used = 1 WHERE token_hash = ?", (row["token_hash"],))
    acc = db.query_one("SELECT * FROM accounts WHERE id = ?", (row["account_id"],))
    if not acc:
        raise AuthError("That account no longer exists.", 404)
    return acc


def _send_verify(acc: dict) -> bool:
    url = f"{_site()}/verify?token={_new_email_token(acc['id'], 'verify', 48)}"
    hi = f"Hi {acc.get('name')}," if acc.get("name") else "Hi,"
    try:
        mailer.send(acc["email"], "Confirm your MarketPlayground account",
                    f"{hi}\n\nTap to confirm your email and finish creating your account:\n{url}\n\nThe link works for 48 hours. "
                    "If you didn't sign up, ignore this email.\n\nMarketPlayground",
                    mailer.button_html("Confirm your email", f"{hi} tap below to finish creating your MarketPlayground account.",
                                       url, "Confirm my email", "The link works for 48 hours. If you didn't sign up, ignore this email."))
        return True
    except Exception as e:
        print(f"[auth] verification email failed: {e}")
        return False


def signup(email: str, password: str, name: str = "", device_id: Optional[str] = None) -> dict:
    e = _clean_email(email)
    _check_new_password(password)
    if db.query_one("SELECT id FROM accounts WHERE email = ?", (e,)):
        raise AuthError("There's already an account with that email. Try logging in.", 409)
    dev = _clean_device(device_id)
    uid = dev if dev and not db.query_one("SELECT id FROM accounts WHERE uid = ?", (dev,)) else f"u-{uuid.uuid4()}"
    acc = {"id": f"a-{uuid.uuid4().hex[:16]}", "uid": uid, "email": e, "name": (name or "").strip()[:60],
           "created_at": _now().isoformat()}
    must_verify = verification_required()
    db.execute("INSERT INTO accounts (id, uid, email, name, pw_hash, created_at, last_login, verified) VALUES (?,?,?,?,?,?,?,?)",
               (acc["id"], uid, e, acc["name"], hash_password(password), acc["created_at"], acc["created_at"], 0 if must_verify else 1))
    moved = _merge_device(dev, uid)
    if must_verify:
        sent = _send_verify(acc)
        return {"needs_verification": True, "email": e, "sent": sent, "moved_beliefs": moved}
    return {"token": _new_session(acc["id"]), "account": _public(acc), "moved_beliefs": moved}


def login(email: str, password: str, device_id: Optional[str] = None) -> dict:
    e = (email or "").strip().lower()
    acc = db.query_one("SELECT * FROM accounts WHERE email = ?", (e,))
    if not acc or not check_password(password or "", acc["pw_hash"]):
        raise AuthError("Email or password is wrong.", 401)
    if verification_required() and not acc.get("verified", 1):
        raise AuthError("Please confirm your email first. Check your inbox for the link from MarketPlayground.", 403)
    db.execute("UPDATE accounts SET last_login = ? WHERE id = ?", (_now().isoformat(), acc["id"]))
    moved = _merge_device(_clean_device(device_id), acc["uid"])
    return {"token": _new_session(acc["id"]), "account": _public(acc), "moved_beliefs": moved}


def account_for_token(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    s = db.query_one("SELECT account_id, expires_at FROM sessions WHERE token_hash = ?",
                     (hashlib.sha256(token.encode()).hexdigest(),))
    if not s or s["expires_at"] < _now().isoformat():
        return None
    acc = db.query_one("SELECT * FROM accounts WHERE id = ?", (s["account_id"],))
    return acc


def require(token: Optional[str]) -> dict:
    acc = account_for_token(token)
    if not acc:
        raise AuthError("Please log in again.", 401)
    return acc


def logout(token: Optional[str]) -> None:
    if token:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))


def update_profile(token: Optional[str], name: str) -> dict:
    acc = require(token)
    db.execute("UPDATE accounts SET name = ? WHERE id = ?", ((name or "").strip()[:60], acc["id"]))
    acc["name"] = (name or "").strip()[:60]
    return _public(acc)


def change_password(token: Optional[str], current: str, new: str) -> None:
    acc = require(token)
    if not check_password(current or "", acc["pw_hash"]):
        raise AuthError("Your current password is wrong.", 401)
    _check_new_password(new)
    db.execute("UPDATE accounts SET pw_hash = ? WHERE id = ?", (hash_password(new), acc["id"]))
    # sign out everywhere else
    keep = hashlib.sha256(token.encode()).hexdigest()
    db.execute("DELETE FROM sessions WHERE account_id = ? AND token_hash != ?", (acc["id"], keep))


def delete_account(token: Optional[str], password: str) -> None:
    acc = require(token)
    if not check_password(password or "", acc["pw_hash"]):
        raise AuthError("Password is wrong.", 401)
    db.execute("DELETE FROM sessions WHERE account_id = ?", (acc["id"],))
    db.execute("DELETE FROM broker_links WHERE account_id = ?", (acc["id"],))
    db.execute("DELETE FROM accounts WHERE id = ?", (acc["id"],))
    # Beliefs stay (anonymous) so the shared learning keeps them; they're no longer tied to an email.
    db.execute("UPDATE beliefs SET user_id = ? WHERE user_id = ?", (f"deleted-{uuid.uuid4().hex[:8]}", acc["uid"]))


def admin_reset_password(email: str) -> str:
    """Beta 'forgot password': the admin generates a temporary password and sends it to the person."""
    e = (email or "").strip().lower()
    acc = db.query_one("SELECT id FROM accounts WHERE email = ?", (e,))
    if not acc:
        raise AuthError("No account with that email.", 404)
    temp = secrets.token_urlsafe(9)
    db.execute("UPDATE accounts SET pw_hash = ? WHERE id = ?", (hash_password(temp), acc["id"]))
    db.execute("DELETE FROM sessions WHERE account_id = ?", (acc["id"],))
    return temp


def verify_email(token: str, device_id: Optional[str] = None) -> dict:
    acc = _use_email_token(token, "verify")
    db.execute("UPDATE accounts SET verified = 1, last_login = ? WHERE id = ?", (_now().isoformat(), acc["id"]))
    moved = _merge_device(_clean_device(device_id), acc["uid"])
    return {"token": _new_session(acc["id"]), "account": _public(acc), "moved_beliefs": moved}


def resend_verification(email: str) -> None:
    """Always answers the same way, so nobody can test which emails have accounts."""
    acc = db.query_one("SELECT * FROM accounts WHERE email = ?", ((email or "").strip().lower(),))
    if acc and not acc.get("verified", 1):
        _send_verify(acc)


def forgot_password(email: str) -> None:
    acc = db.query_one("SELECT * FROM accounts WHERE email = ?", ((email or "").strip().lower(),))
    if not acc:
        return
    url = f"{_site()}/reset?token={_new_email_token(acc['id'], 'reset', 1)}"
    try:
        mailer.send(acc["email"], "Reset your MarketPlayground password",
                    f"Tap to choose a new password:\n{url}\n\nThe link works for 1 hour. If you didn't ask for this, ignore this email.",
                    mailer.button_html("Reset your password", "Tap below to choose a new password.", url, "Choose a new password",
                                       "The link works for 1 hour. If you didn't ask for this, ignore this email."))
    except Exception as e:
        print(f"[auth] reset email failed: {e}")


def reset_password(token: str, new: str) -> dict:
    _check_new_password(new)
    acc = _use_email_token(token, "reset")
    db.execute("UPDATE accounts SET pw_hash = ?, verified = 1 WHERE id = ?", (hash_password(new), acc["id"]))
    db.execute("DELETE FROM sessions WHERE account_id = ?", (acc["id"],))
    return {"token": _new_session(acc["id"]), "account": _public(acc)}

