"""v4 API routes (mounted at /v4)."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from . import engine, grader, interpreter, market, nn

router = APIRouter()


class BeliefIn(BaseModel):
    belief: str
    user_id: str = "anonymous"
    risk_profile: str = "moderate"


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


@router.get("/stats")
async def get_stats():
    return await run_in_threadpool(engine.stats)


@router.post("/admin/grade")
async def admin_grade(train: bool = False, x_admin_token: Optional[str] = Header(None)):
    _check_admin(x_admin_token)
    out = {"grade": await run_in_threadpool(grader.grade)}
    if train:
        out["train"] = await run_in_threadpool(nn.train)
    return out
