"""Every route is either part of the current app, or owner-only. Nothing else is open."""
import re

import pytest

pytest.importorskip("pandas")
pytest.importorskip("yfinance")

PUBLIC = [
    r"^/$", r"^/health$", r"^/docs", r"^/redoc", r"^/openapi\.json$",
    r"^/v4/",                                   # current app (has its own checks)
    r"^/strategy/process_belief$", r"^/basket/generate_basket$",
    r"^/api/paper-trading/(execute|execute_options|close_option|cancel_queued|close_position|portfolio/\{user_id\})$",
    r"^/ticker/(prices|search)$",
    r"^/toggle/news_ingestion_status$",
    r"^/(force_)?retrain$",                     # checks the admin token itself
]


def test_every_leftover_route_is_owner_only(monkeypatch):
    monkeypatch.setenv("MP_ADMIN_TOKEN", "owner-secret")
    from fastapi.testclient import TestClient
    from backend.app import app
    c = TestClient(app, raise_server_exceptions=False)
    checked = 0
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or set()
        if not path or any(re.search(p, path) for p in PUBLIC):
            continue
        url = re.sub(r"\{[^}]+\}", "x", path)
        for m in methods - {"HEAD", "OPTIONS"}:
            r = c.request(m, url, json={})
            assert r.status_code == 403, f"{m} {path} answered {r.status_code} without the owner token"
            r2 = c.request(m, url, json={}, headers={"X-Admin-Token": "wrong"})
            assert r2.status_code == 403, f"{m} {path} accepted a wrong token"
            checked += 1
    assert checked >= 40  # the leftover surface is large; make sure we actually looked at it
