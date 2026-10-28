"""v4 API routes (mounted at /v4)."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from . import auth, db, engine, grader, interpreter, market, nn

router = APIRouter()


class BeliefIn(BaseModel):
    belief: str
    user_id: str = "anonymous"
    risk_profile: str = "moderate"


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


async def run_belief(belief: str, user_id: str, risk_profile: str) -> dict:
    try:
        return await run_in_threadpool(engine.process_belief, belief, user_id, risk_profile)
    except engine.BeliefError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except interpreter.InterpreterError as e:
        raise HTTPException(status_code=502, detail=f"belief interpreter failed: {e}")
    except market.MarketDataError as e:
        raise HTTPException(status_code=502, detail=f"market data unavailable: {e}")


@router.post("/belief")
async def post_belief(body: BeliefIn):
    return await run_belief(body.belief, body.user_id, body.risk_profile)


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


@router.get("/learning")
async def get_learning():
    """How the shared learning is going, in plain words (aggregate only)."""
    return await run_in_threadpool(engine.learning_status)


@router.get("/my_beliefs")
async def get_my_beliefs(user_id: str):
    return await run_in_threadpool(engine.my_beliefs, user_id)


@router.get("/admin/ml")
async def admin_ml(x_admin_token: Optional[str] = Header(None)):
    """Full network report: data counts, every version's walk-forward metrics."""
    _check_admin(x_admin_token)
    return {"stats": await run_in_threadpool(engine.stats), "versions": await run_in_threadpool(nn.history, 30)}


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
