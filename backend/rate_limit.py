"""
Simple per-visitor rate limit for endpoints that cost money (each call can use Claude).

Defaults: 20 requests per visitor per 10 minutes, across all of these paths together.
Tune with MP_RATE_LIMIT (requests) and MP_RATE_WINDOW_SECONDS. Set MP_RATE_LIMIT=0 to turn off.
In-memory, per server process: good enough for a beta on one instance.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

COSTLY_PREFIXES = (
    "/strategy/process_belief",
    "/v4/belief",
    "/basket/generate_basket",
    "/market-events/strategies",
    "/news/ingest",
    "/alpaca/preview_trade",
    "/v4/auth/login",   # slows down password guessing
    "/v4/auth/signup",
    "/v4/auth/resend",  # each sends an email
    "/v4/auth/forgot",
)

_lock = threading.Lock()
_hits: dict[str, deque] = defaultdict(deque)


def _client_id(request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class CostlyEndpointRateLimit(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        limit = int(os.getenv("MP_RATE_LIMIT", "20"))
        if limit <= 0 or request.method == "OPTIONS" or not request.url.path.startswith(COSTLY_PREFIXES):
            return await call_next(request)
        window = int(os.getenv("MP_RATE_WINDOW_SECONDS", "600"))
        now = time.time()
        key = _client_id(request)
        with _lock:
            q = _hits[key]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                retry = int(q[0] + window - now) + 1
                return JSONResponse(
                    {"detail": f"You're going fast! Try again in about {max(1, retry // 60)} minute(s)."},
                    status_code=429,
                    headers={"Retry-After": str(retry)},
                )
            q.append(now)
            if len(_hits) > 50000:  # keep memory bounded
                for k in [k for k, v in _hits.items() if not v or v[-1] <= now - window][:10000]:
                    _hits.pop(k, None)
        return await call_next(request)


def reset_for_tests() -> None:
    with _lock:
        _hits.clear()
