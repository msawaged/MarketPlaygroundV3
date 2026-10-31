"""v4 API routes (mounted at /v4)."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from . import auth, brokerage, db, engine, grader, interpreter, market, movers, nn, notify, passkeys, brain

router = APIRouter()


class BeliefIn(BaseModel):
    belief: str
    user_id: str = "anonymous"
    risk_profile: str = "moderate"
    prefs: Optional[dict] = None


class WaitlistIn(BaseModel):
    email: str
    belief: Optional[str] = None
    source: Optional[str] = None
    website: Optional[str] = None  # honeypot: real people never fill this in


_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,24}$")


class FeedbackIn(BaseModel):
    belief_id: str
    kind: str  # up | down | executed
    user_id: str = "anonymous"
    pick_id: Optional[str] = None


def _check_admin(token: Optional[str]) -> None:
    expected = os.getenv("MP_ADMIN_TOKEN")
    if not expected or token != expected:
        raise HTTPException(status_code=403, detail="admin token required (set MP_ADMIN_TOKEN)")


async def run_belief(belief: str, user_id: str, risk_profile: str, prefs: Optional[dict] = None) -> dict:
    try:
        return await run_in_threadpool(lambda: engine.process_belief(belief, user_id, risk_profile, prefs=prefs))
    except engine.BudgetError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except engine.BeliefError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except interpreter.InterpreterError as e:
        print(f"[v4] interpreter failed: {e}")
        raise HTTPException(status_code=502, detail="The AI had trouble reading that one. Please try again in a moment.")
    except market.MarketDataError as e:
        print(f"[v4] market data failed: {e}")
        raise HTTPException(status_code=502, detail="Market prices are unavailable right now. Please try again in a moment.")


@router.post("/belief")
async def post_belief(body: BeliefIn):
    return await run_belief(body.belief, body.user_id, body.risk_profile, body.prefs)


@router.post("/feedback")
async def post_feedback(body: FeedbackIn):
    try:
        return await run_in_threadpool(engine.record_feedback, body.belief_id, body.kind, body.user_id, body.pick_id)
    except engine.BeliefError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/belief/{belief_id}")
async def get_belief(belief_id: str):
    b = await run_in_threadpool(engine.get_belief, belief_id)
    if not b:
        raise HTTPException(status_code=404, detail="not found")
    return b


@router.get("/trending")
async def get_trending(days: int = 14, limit: int = 8):
    return await run_in_threadpool(engine.trending, max(1, min(days, 90)), max(1, min(limit, 20)))


@router.get("/stats")
async def get_stats():
    return await run_in_threadpool(engine.stats)


# ---------------- accounts ----------------

class SignupIn(BaseModel):
    email: str
    password: str
    name: Optional[str] = ""
    device_id: Optional[str] = None


class LoginIn(BaseModel):
    email: str
    password: str
    device_id: Optional[str] = None


class ProfileIn(BaseModel):
    name: str = ""


class PasswordIn(BaseModel):
    current: str
    new: str


class DeleteIn(BaseModel):
    password: str


def _token(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def _auth_call(fn, *args):
    try:
        return await run_in_threadpool(fn, *args)
    except auth.AuthError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


@router.post("/auth/signup")
async def auth_signup(body: SignupIn):
    return await _auth_call(auth.signup, body.email, body.password, body.name or "", body.device_id)


@router.post("/auth/login")
async def auth_login(body: LoginIn):
    return await _auth_call(auth.login, body.email, body.password, body.device_id)


@router.get("/auth/me")
async def auth_me(authorization: Optional[str] = Header(None)):
    acc = await _auth_call(auth.require, _token(authorization))
    return {"account": auth._public(acc)}


@router.post("/auth/logout")
async def auth_logout(authorization: Optional[str] = Header(None)):
    await _auth_call(auth.logout, _token(authorization))
    return {"ok": True}


@router.post("/auth/profile")
async def auth_profile(body: ProfileIn, authorization: Optional[str] = Header(None)):
    return {"account": await _auth_call(auth.update_profile, _token(authorization), body.name)}


@router.post("/auth/password")
async def auth_password(body: PasswordIn, authorization: Optional[str] = Header(None)):
    await _auth_call(auth.change_password, _token(authorization), body.current, body.new)
    return {"ok": True}


@router.post("/auth/delete")
async def auth_delete(body: DeleteIn, authorization: Optional[str] = Header(None)):
    await _auth_call(auth.delete_account, _token(authorization), body.password)
    return {"ok": True}


class PasskeyIn(BaseModel):
    credential: dict
    label: Optional[str] = ""


class PasskeyLoginIn(BaseModel):
    challenge_id: str
    credential: dict
    device_id: Optional[str] = None


@router.post("/auth/passkey/register/options")
async def passkey_reg_options(authorization: Optional[str] = Header(None), origin: Optional[str] = Header(None)):
    return await _auth_call(passkeys.register_options, _token(authorization), origin)


@router.post("/auth/passkey/register/verify")
async def passkey_reg_verify(body: PasskeyIn, authorization: Optional[str] = Header(None), origin: Optional[str] = Header(None)):
    return await _auth_call(passkeys.register_verify, _token(authorization), body.credential, origin, body.label or "")


@router.post("/auth/passkey/login/options")
async def passkey_login_options(origin: Optional[str] = Header(None)):
    return await _auth_call(passkeys.login_options, origin)


@router.post("/auth/passkey/login/verify")
async def passkey_login_verify(body: PasskeyLoginIn, origin: Optional[str] = Header(None)):
    return await _auth_call(passkeys.login_verify, body.challenge_id, body.credential, body.device_id, origin)


@router.get("/auth/passkey/status")
async def passkey_status(authorization: Optional[str] = Header(None)):
    return await _auth_call(passkeys.status, _token(authorization))


@router.post("/auth/passkey/remove")
async def passkey_remove(authorization: Optional[str] = Header(None)):
    return await _auth_call(passkeys.remove_all, _token(authorization))


class TokenIn(BaseModel):
    token: str
    device_id: Optional[str] = None


class EmailIn(BaseModel):
    email: str


class NewPasswordIn(BaseModel):
    token: str
    password: str


@router.post("/auth/verify")
async def auth_verify(body: TokenIn):
    return await _auth_call(auth.verify_email, body.token, body.device_id)


@router.post("/auth/resend")
async def auth_resend(body: EmailIn):
    await _auth_call(auth.resend_verification, body.email)
    return {"ok": True}


@router.post("/auth/forgot")
async def auth_forgot(body: EmailIn):
    await _auth_call(auth.forgot_password, body.email)
    return {"ok": True}


@router.post("/auth/reset")
async def auth_reset(body: NewPasswordIn):
    return await _auth_call(auth.reset_password, body.token, body.password)


class ResetIn(BaseModel):
    email: str


@router.post("/admin/reset_password")
async def admin_reset(body: ResetIn, x_admin_token: Optional[str] = Header(None)):
    _check_admin(x_admin_token)
    return {"temporary_password": await _auth_call(auth.admin_reset_password, body.email)}


@router.get("/admin/accounts")
async def admin_accounts(x_admin_token: Optional[str] = Header(None)):
    _check_admin(x_admin_token)
    rows = await run_in_threadpool(db.query, "SELECT email, name, created_at, last_login FROM accounts ORDER BY created_at DESC")
    return {"count": len(rows), "accounts": rows}


# ---------------- real money (switched off until MP_REAL_MONEY=on) ----------------

class PreviewIn(BaseModel):
    ticker: str
    side: str = "buy"
    amount_usd: float
    belief_id: Optional[str] = None
    pick_id: Optional[str] = None


class PlaceIn(BaseModel):
    preview_id: str
    confirm: bool = False


async def _broker_call(fn, *args):
    try:
        return await run_in_threadpool(fn, *args)
    except brokerage.BrokerError as e:
        raise HTTPException(status_code=e.status, detail=str(e))
    except auth.AuthError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


@router.get("/broker/status")
async def broker_status(authorization: Optional[str] = Header(None)):
    return await _broker_call(brokerage.status, _token(authorization))


@router.get("/broker/connect")
async def broker_connect(authorization: Optional[str] = Header(None)):
    return {"url": await _broker_call(brokerage.connect_url, _token(authorization))}


@router.get("/broker/callback")
async def broker_callback(code: str = "", state: str = "", error: str = ""):
    from fastapi.responses import RedirectResponse
    site = os.getenv("MP_SITE_URL", "").rstrip("/")
    if error or not code:
        return RedirectResponse(f"{site}/account?broker=cancelled")
    try:
        await run_in_threadpool(brokerage.finish_connect, code, state)
    except brokerage.BrokerError:
        return RedirectResponse(f"{site}/account?broker=failed")
    return RedirectResponse(f"{site}/account?broker=connected")


@router.post("/broker/disconnect")
async def broker_disconnect(authorization: Optional[str] = Header(None)):
    await _broker_call(brokerage.disconnect, _token(authorization))
    return {"ok": True}


@router.post("/broker/preview")
async def broker_preview(body: PreviewIn, authorization: Optional[str] = Header(None)):
    return await _broker_call(brokerage.preview, _token(authorization), body.ticker, body.side, body.amount_usd, body.belief_id, body.pick_id)


@router.post("/broker/order")
async def broker_order(body: PlaceIn, authorization: Optional[str] = Header(None)):
    return await _broker_call(brokerage.place, _token(authorization), body.preview_id, body.confirm)


@router.get("/headlines")
async def get_headlines(limit: int = 6):
    return {"headlines": await run_in_threadpool(market.headlines, max(1, min(limit, 12)))}


@router.get("/brain")
async def get_brain():
    """Public, aggregate view of the learning. No user's own words."""
    return await run_in_threadpool(brain.snapshot)


@router.get("/movers")
async def get_movers():
    """Today's headlines as hunches, with the companies each one moves and their move today."""
    return await run_in_threadpool(movers.feed)


@router.get("/movers/story")
async def get_movers_story(h: str = ""):
    """One news story from today's feed, told as full-screen cards (Story mode)."""
    out = await run_in_threadpool(movers.story, h[:200])
    if not out:
        raise HTTPException(status_code=404, detail="That story is no longer in today's news.")
    return out


@router.get("/unsubscribe")
async def get_unsubscribe(a: str = "", s: str = ""):
    from fastapi.responses import HTMLResponse
    ok = await run_in_threadpool(notify.unsubscribe, a, s)
    msg = "You won't get these emails anymore." if ok else "That link didn't work. Reply to any of our emails and we'll take you off."
    return HTMLResponse(f"<html><body style='font-family:-apple-system,Arial;padding:40px;max-width:480px;margin:auto'>"
                        f"<h2>MarketPlayground</h2><p>{msg}</p></body></html>")


@router.get("/replay")
async def get_replay(tickers: str, directions: str = "", days: int = 365):
    ts = [t.strip().upper() for t in tickers.split(",") if t.strip()][:5]
    ds = [d.strip().lower() for d in directions.split(",")] if directions else []
    ds = (ds + ["bullish"] * len(ts))[:len(ts)]
    if not ts:
        raise HTTPException(status_code=400, detail="tickers required")
    try:
        return await run_in_threadpool(engine.replay, ts, ds, days)
    except market.MarketDataError as e:
        raise HTTPException(status_code=404, detail=f"Not enough price history for a replay ({e}).")


@router.get("/learning")
async def get_learning(x_admin_token: Optional[str] = Header(None)):
    """How the shared learning is going (owner only: it shows the practice feed and network internals)."""
    _check_admin(x_admin_token)
    return await run_in_threadpool(engine.learning_status)


@router.get("/my_beliefs")
async def get_my_beliefs(user_id: str):
    return await run_in_threadpool(engine.my_beliefs, user_id)


@router.get("/admin/ml")
async def admin_ml(x_admin_token: Optional[str] = Header(None)):
    """Full network report: data counts, every version's walk-forward metrics."""
    _check_admin(x_admin_token)
    return {"stats": await run_in_threadpool(engine.stats), "versions": await run_in_threadpool(nn.history, 30),
            "health": await run_in_threadpool(brain.health, False)}


@router.post("/admin/grade")
async def admin_grade(train: bool = False, x_admin_token: Optional[str] = Header(None)):
    _check_admin(x_admin_token)
    out = {"grade": await run_in_threadpool(grader.grade)}
    if train:
        out["train"] = await run_in_threadpool(nn.train)
    return out


@router.post("/waitlist")
async def join_waitlist(body: WaitlistIn):
    """Landing-page signup. Beliefs people leave here are kept for later seeding (not run automatically)."""
    if body.website:  # bot filled the hidden field; pretend success
        return {"status": "ok"}
    email = body.email.strip().lower()
    if len(email) > 254 or not _EMAIL.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    belief = (body.belief or "").strip()[:500] or None
    source = (body.source or "").strip()[:60] or None

    def save():
        if db.query_one("SELECT email FROM waitlist WHERE email = ?", (email,)):
            if belief:
                db.execute("UPDATE waitlist SET belief = ? WHERE email = ?", (belief, email))
            return
        db.execute("INSERT INTO waitlist (email, belief, source, created_at) VALUES (?,?,?,?)",
                   (email, belief, source, datetime.now(timezone.utc).isoformat()))

    await run_in_threadpool(save)
    return {"status": "ok"}


@router.get("/admin/waitlist")
async def admin_waitlist(x_admin_token: Optional[str] = Header(None)):
    _check_admin(x_admin_token)
    rows = await run_in_threadpool(db.query, "SELECT email, belief, source, created_at FROM waitlist ORDER BY created_at")
    return {"count": len(rows), "signups": rows}
