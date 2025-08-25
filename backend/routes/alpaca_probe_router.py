# backend/routes/alpaca_probe_router.py
import os, time, requests
from fastapi import APIRouter, Query
from typing import Dict, Any, List, Optional
from datetime import datetime

ROUTER = APIRouter(prefix="/alpaca", tags=["alpaca-probe"])

ALPACA_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY", "")
DATA_BASE = os.getenv("ALPACA_DATA_BASE", "https://data.alpaca.markets")

HDRS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}

def _get(path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    url = f"{DATA_BASE}{path}"
    r = requests.get(url, headers=HDRS, params=params or {}, timeout=20)
    r.raise_for_status()
    return r.json()

def _try(path: str, params: Dict[str, Any] | None = None):
    try:
        return {"ok": True, "data": _get(path, params)}
    except requests.HTTPError as e:
        return {"ok": False, "error": f"{e.response.status_code} {e.response.text[:300]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}

def _nearest_exp(expirations: List[str], target_days: int = 45) -> Optional[str]:
    if not expirations: return None
    today = datetime.utcnow().date()
    exps = []
    for e in expirations:
        try:
            d = datetime.strptime(e, "%Y-%m-%d").date()
            exps.append((abs((d - today).days - target_days), e))
        except:
            continue
    exps.sort(key=lambda x: x[0])
    return exps[0][1] if exps else None

@ROUTER.get("/probe")
def probe_symbol(
    symbol: str = Query(..., description="Underlying symbol, e.g. AAPL"),
    expiration: Optional[str] = Query(None, description="YYYY-MM-DD; if omitted, will auto-pick"),
    include_options: bool = Query(True),
    include_stocks: bool = Query(True),
    include_news: bool = Query(True),
    include_crypto: bool = Query(False),
):
    """
    Hit many Alpaca DATA endpoints for the given symbol and return everything found.
    Any endpoint that fails returns an error string instead of breaking the whole call.
    """
    symbol = symbol.upper().strip()
    out = {
        "meta": {
            "symbol": symbol,
            "expiration_input": expiration,
            "ts": int(time.time()),
            "data_base": DATA_BASE,
        },
        "success": {},
        "errors": {},
    }

    # ---- Stocks data (v2)
    if include_stocks:
        stock_endpoints = {
            f"/v2/stocks/{symbol}/snapshot": {},
            f"/v2/stocks/{symbol}/trades/latest": {},
            f"/v2/stocks/{symbol}/quotes/latest": {},
            f"/v2/stocks/{symbol}/bars": {"timeframe": "1Day", "limit": 100},
            f"/v2/stocks/{symbol}/bars/latest": {"timeframe": "1Min"},
        }
        for path, params in stock_endpoints.items():
            res = _try(path, params)
            (out["success"] if res["ok"] else out["errors"])[path] = res.get("data") if res["ok"] else res["error"]

    # ---- News (v1beta1)
    if include_news:
        path = "/v1beta1/news"
        params = {"symbols": symbol, "limit": 50}
        res = _try(path, params)
        (out["success"] if res["ok"] else out["errors"])[path] = res.get("data") if res["ok"] else res["error"]

    # ---- Options (v1beta1) - expirations, strikes, chain
    if include_options:
        # expirations
        exp_path = f"/v1beta1/options/snapshots/{symbol}/expirations"
        exp_res = _try(exp_path)
        (out["success"] if exp_res["ok"] else out["errors"])[exp_path] = exp_res.get("data") if exp_res["ok"] else exp_res["error"]

        chosen_exp = expiration
        exps = []
        if exp_res.get("ok"):
            exps = exp_res["data"].get("expirations") or exp_res["data"].get("data") or []
            if not chosen_exp:
                chosen_exp = _nearest_exp(exps)

        # strikes (if we have an expiration)
        if chosen_exp:
            strikes_path = f"/v1beta1/options/snapshots/{symbol}/expirations/{chosen_exp}/strikes"
            strikes_res = _try(strikes_path)
            (out["success"] if strikes_res["ok"] else out["errors"])[strikes_path] = strikes_res.get("data") if strikes_res["ok"] else strikes_res["error"]

            # chain
            chain_path = f"/v1beta1/options/chain"
            chain_res = _try(chain_path, {"symbol": symbol, "expiration": chosen_exp})
            (out["success"] if chain_res["ok"] else out["errors"])[chain_path + f"?symbol={symbol}&expiration={chosen_exp}"] = (
                chain_res.get("data") if chain_res["ok"] else chain_res["error"]
            )
        else:
            out["meta"]["note"] = "No usable expiration found; chain/strikes skipped."

    # ---- Crypto (optional)
    if include_crypto:
        crypto_paths = {
            f"/v1beta3/crypto/us/{symbol}/trades/latest": {},
            f"/v1beta3/crypto/us/{symbol}/quotes/latest": {},
            f"/v1beta3/crypto/us/{symbol}/bars/latest": {"timeframe": "1Min"},
        }
        for path, params in crypto_paths.items():
            res = _try(path, params)
            (out["success"] if res["ok"] else out["errors"])[path] = res.get("data") if res["ok"] else res["error"]

    return out
