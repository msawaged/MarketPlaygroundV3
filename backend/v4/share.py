"""
"I called it" cards: a share link with its own preview for each of a user's calls, wins and misses alike.

GET /c/{belief_id}       tiny HTML page: this call's own og/twitter tags (chat apps and social sites read these to
                         draw the preview), then an instant redirect into the app's welcome screen.
GET /c/{belief_id}.png   the 1200x630 preview image (Pillow), rendered once per grading state and kept in memory.
GET /c/{belief_id}.json  the same facts for the welcome screen ("<the shared call>, make your own").

Honest by construction: only stored grades are shown (outcomes.belief_right / bench_ret, the same one-number-per-call
measure My calls and the base rates use), a miss is drawn exactly like a win, ungraded checks say "not graded yet",
every card says "practice", and there is no user name or email anywhere. Only users' own calls (source = 'user') get
a card; seeded calls 404 so a back-dated practice call is never passed off as someone's live call.
"""
from __future__ import annotations

import html
import io
import os
import re
import threading
from collections import OrderedDict
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, Response

from . import db

router = APIRouter()

SITE = os.getenv("MP_SITE_URL", "https://marketplayground-web.onrender.com").rstrip("/")
SHOWN_CPS = (7, 30, 90)          # always on the card; 180/365 join once graded
MAX_TEXT = 140                   # characters of the belief on the card (and in the tags)
_ID = re.compile(r"^b-[0-9a-f]{6,32}$")
WORDS = {"bullish": "up", "bearish": "down", "volatile": "a big move"}


# ---------------------------------------------------------------- data

def _short(text: str, n: int = MAX_TEXT) -> str:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _fmt_date(d: Optional[str]) -> str:
    try:
        x = date.fromisoformat(str(d)[:10])
    except ValueError:
        return ""
    return f"{x.strftime('%b')} {x.day}, {x.year}"


def card(belief_id: str) -> Optional[dict]:
    """Everything the card shows, from stored rows only. None if it isn't a user's call."""
    if not _ID.match(belief_id or ""):
        return None
    b = db.query_one("SELECT id, text, as_of_date, created_at, direction, user_prob, source FROM beliefs WHERE id = ?",
                     (belief_id,))
    if not b or b.get("source") != "user":
        return None
    pick = db.query_one("SELECT ticker, name, direction FROM picks WHERE belief_id = ? AND shown = 1 "
                        "ORDER BY final_rank LIMIT 1", (belief_id,))
    core = b.get("direction") or ""
    shown = [r["ticker"] for r in db.query("SELECT ticker FROM picks WHERE belief_id = ? AND shown = 1 AND direction = ? "
                                           "ORDER BY final_rank LIMIT 3", (belief_id, core))]
    rows = db.query(
        """SELECT o.checkpoint_days AS cp, MAX(o.bench_ret) AS br, MAX(o.spy_ret) AS sr, MAX(o.eval_date) AS on_date
           FROM outcomes o JOIN picks p ON p.id = o.pick_id
           WHERE p.belief_id = ? AND o.belief_right IS NOT NULL AND p.direction = ?
           GROUP BY o.checkpoint_days""", (belief_id, core))
    from . import baserate  # lazy, as engine._graded_checks does: the same per-call measure
    graded = {}
    for r in rows:
        x = baserate._call_excess(core, r["br"], r["sr"])
        if x is not None:
            graded[int(r["cp"])] = {"vs_spy": round(x, 4), "on": str(r["on_date"] or "")[:10]}
    made = str(b.get("as_of_date") or b.get("created_at") or "")[:10]
    cps = sorted(set(SHOWN_CPS) | set(graded))
    checks = []
    for cp in cps:
        g = graded.get(cp)
        if g:
            checks.append({"days": cp, "status": "ahead" if g["vs_spy"] > 0 else "behind", "vs_spy": g["vs_spy"],
                           "on": g["on"]})
        else:
            due = None
            try:
                due = (date.fromisoformat(made) + timedelta(days=cp)).isoformat()
            except ValueError:
                pass
            checks.append({"days": cp, "status": "pending", "vs_spy": None, "due": due})
    latest = max(graded) if graded else None
    measured = _measured_on(belief_id, core, latest) if latest is not None else None
    prob = b.get("user_prob")
    return {
        "id": b["id"], "text": _short(b.get("text")), "made": made, "made_label": _fmt_date(made),
        "direction": core, "direction_word": WORDS.get(core),
        "pick": ({"ticker": pick["ticker"], "name": pick.get("name"), "direction": pick["direction"]} if pick else None),
        "picks": shown,
        "measured_on": measured,
        "sure": round(float(prob) * 100) if prob is not None else None,   # stored 0-1 (calibration.normalize)
        "checks": checks,
        "latest": ({"days": latest, **graded[latest]} if latest is not None else None),
    }


def _measured_on(belief_id: str, core: str, cp: int) -> Optional[str]:
    """What the grade was measured on (grader._group_scores): the theme's fund(s) among the picks if there are any,
    else the average of every related stock found (shown or not), else the one stock. The card names the shown picks,
    so without this a reader takes "+1.7 pts" for the first ticker's own result, which it isn't."""
    rows = db.query("""SELECT p.ticker, o.bench_kind AS kind, o.sel_edge AS edge FROM picks p JOIN outcomes o ON o.pick_id = p.id
                       WHERE p.belief_id = ? AND p.direction = ? AND o.checkpoint_days = ? AND o.belief_right IS NOT NULL
                       ORDER BY p.final_rank""", (belief_id, core, cp))
    if not rows:
        return None
    kind = rows[0].get("kind")
    tickers = [r["ticker"] for r in rows]
    if kind == "fund":
        funds = [r["ticker"] for r in rows if r.get("edge") is None]
        return f"{', '.join(funds)}, the theme's fund" if len(funds) == 1 else f"{', '.join(funds)}, the theme's funds"
    if len(tickers) > 1:
        return f"the average of {len(tickers)} related stocks"
    return tickers[0]


def headline(c: dict) -> str:
    """One honest line about the newest graded check, or that none is graded yet."""
    L = c.get("latest")
    if not L:
        nxt = next((k for k in c["checks"] if k["status"] == "pending"), None)
        when = f" First check {_fmt_date(nxt['due'])}." if nxt and nxt.get("due") else ""
        return f"Not graded yet.{when}"
    pts = abs(L["vs_spy"]) * 100
    side = "ahead of" if L["vs_spy"] > 0 else "behind"
    return f"{L['days']} days in: {side} the S&P 500 by {pts:.1f} pts"


def _call_line(c: dict) -> str:
    p = c.get("pick")
    names = ", ".join(c.get("picks") or ([p["ticker"]] if p else []))
    word = c.get("direction_word")
    if names and word:
        return f"{names} · calling {word}"
    return names


def _graded_on(c: dict) -> str:
    m = c.get("measured_on")
    return f"Graded on {m}" if m else ""


def copy_text(c: dict, url: str) -> str:
    """Wordle-style text for chats that don't show previews. Squares come from stored grades only."""
    sq = {"ahead": "🟩", "behind": "🟥", "pending": "⬜"}
    row = " ".join(f"{k['days']}d {sq[k['status']]}" for k in c["checks"])
    bits = [f"My call on MarketPlayground: “{c['text']}”"]
    who = _call_line(c)
    bits.append(" · ".join(x for x in (who, f"made {c['made_label']}" if c["made_label"] else "") if x))
    bits.append(f"{row} vs the S&P 500" + (f" ({_graded_on(c)[0].lower()}{_graded_on(c)[1:]})" if c.get("measured_on") else ""))
    bits.append(f"Practice call. {url}")
    return "\n".join(b for b in bits if b)


def landing(belief_id: str) -> str:
    return f"{SITE}/welcome?ref=card&c={belief_id}"


def page_html(c: dict, url: str, png: str) -> str:
    e = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731
    title = f"“{c['text']}”"
    who = _call_line(c)
    on = _graded_on(c)
    desc = f"{headline(c).rstrip('.')}{' (' + on[0].lower() + on[1:] + ')' if on else ''}. " \
           f"{who + '. ' if who else ''}Practice call made {c['made_label']}, graded against the " \
           f"S&P 500 at 7, 30 and 90 days. Make your own call free."
    go = landing(c["id"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} · MarketPlayground</title>
<meta name="description" content="{e(desc)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="MarketPlayground">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{e(png)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{e(png)}">
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0;url={e(go)}">
<style>body{{background:#020617;color:#e2e8f0;font-family:system-ui,sans-serif;padding:24px}}a{{color:#93c5fd}}</style>
</head><body>
<p>{e(title)}</p><p>{e(headline(c))}</p>
<p><a href="{e(go)}">Open MarketPlayground</a></p>
<script>location.replace({_js(go)});</script>
</body></html>"""


def _js(s: str) -> str:
    import json
    return json.dumps(s).replace("<", "\\u003c")


# ---------------------------------------------------------------- image

W, H = 1200, 630
_png_cache: "OrderedDict[tuple, bytes]" = OrderedDict()
_png_lock = threading.Lock()
PNG_CACHE_MAX = 64   # ~60 KB each, so a few MB at most


def _font_path(bold: bool) -> Optional[str]:
    import importlib.util
    spec = importlib.util.find_spec("matplotlib")
    names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    dirs = []
    if spec and spec.submodule_search_locations:
        dirs.append(os.path.join(list(spec.submodule_search_locations)[0], "mpl-data", "fonts", "ttf"))
    dirs += ["/usr/share/fonts/truetype/dejavu"]
    for d in dirs:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
    return None


def _font(size: int, bold: bool = False):
    from PIL import ImageFont
    p = _font_path(bold)
    if p:
        return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def _plain(s: str) -> str:
    """Characters the font can draw: drop emoji and other astral-plane symbols."""
    return "".join(ch for ch in str(s) if ord(ch) < 0x2600 or 0x2010 <= ord(ch) <= 0x2027)


def _wrap(draw, text: str, font, width: int, max_lines: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for w in words:
        t = f"{line} {w}".strip()
        if draw.textlength(t, font=font) <= width or not line:
            line = t
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    # a single unbroken word wider than the card
    out = []
    for ln in lines:
        while draw.textlength(ln, font=font) > width and len(ln) > 1:
            ln = ln[:-2] + "…"
        out.append(ln)
    return out


def render_png(c: dict) -> bytes:
    key = (c["id"], c.get("measured_on"), tuple((k["days"], k["status"], k.get("vs_spy")) for k in c["checks"]))
    with _png_lock:
        hit = _png_cache.get(key)
        if hit:
            _png_cache.move_to_end(key)
            return hit
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), "#020617")
    d = ImageDraw.Draw(img)
    for y in range(H):  # soft top-to-bottom gradient
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(11 * (1 - t) + 2 * t), int(26 * (1 - t) + 6 * t), int(58 * (1 - t) + 23 * t)))
    blue, grey, white = (77, 163, 255), (148, 163, 184), (255, 255, 255)
    green, red, slate = (134, 239, 172), (252, 165, 165), (51, 65, 85)
    X = 64
    # brand: white tile with a blue M, then the name
    d.rounded_rectangle([X, 48, X + 56, 104], radius=14, fill=white)
    d.line([(X + 14, 92), (X + 14, 62), (X + 28, 80), (X + 42, 62), (X + 42, 92)], fill=(37, 99, 235), width=7,
           joint="curve")
    d.text((X + 74, 56), "MarketPlayground", font=_font(32, True), fill=white)
    kicker = f"MY CALL · MADE {c['made_label'].upper()}" if c["made_label"] else "MY CALL"
    d.text((X, 140), kicker, font=_font(24, True), fill=(147, 197, 253))
    quote = f"“{_plain(c['text'])}”"
    big = _font(50, True)
    lines = _wrap(d, quote, big, W - 2 * X, 3)
    step = 62
    if len(lines) == 3:   # long calls: a touch smaller so the line under them clears the boxes
        big, step = _font(44, True), 54
        lines = _wrap(d, quote, big, W - 2 * X, 3)
    y = 180
    for ln in lines:
        d.text((X, y), ln, font=big, fill=white)
        y += step
    who = _call_line(c)
    if c.get("sure") is not None:
        who += f"{' · ' if who else ''}I said {c['sure']}% sure"
    if who:
        d.text((X, y + 8), _plain(who), font=_font(28), fill=grey)
    # one box per checkpoint, misses drawn exactly like wins (just red instead of green)
    checks = c["checks"][:5]
    gap = 20
    bw = (W - 2 * X - gap * (len(checks) - 1)) // max(1, len(checks))
    by, bh = 410, 118
    for i, k in enumerate(checks):
        bx = X + i * (bw + gap)
        tone = {"ahead": green, "behind": red}.get(k["status"])
        fill = {"ahead": (20, 60, 40), "behind": (70, 24, 30)}.get(k["status"], (22, 30, 48))
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=22, fill=fill, outline=tone or slate, width=3)
        d.text((bx + 22, by + 16), f"{k['days']} days", font=_font(24, True), fill=grey)
        if k["status"] == "pending":
            d.text((bx + 22, by + 58), "not graded yet", font=_font(26), fill=(203, 213, 225))
        else:
            v = k["vs_spy"] * 100
            d.text((bx + 22, by + 50), f"{'+' if v > 0 else ''}{v:.1f} pts", font=_font(40, True), fill=tone)
    on = _graded_on(c)
    foot = f"vs the S&P 500, in the direction called{'. ' + on if on else ''}. Practice call, no real money."
    size = 22
    while size > 16 and d.textlength(_plain(foot), font=_font(size)) > W - 2 * X:
        size -= 1
    d.text((X, 552), _plain(foot), font=_font(size), fill=grey)
    d.text((X, 584), "Make your own call free: marketplayground-web.onrender.com", font=_font(22, True), fill=blue)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    out = buf.getvalue()
    with _png_lock:
        _png_cache[key] = out
        while len(_png_cache) > PNG_CACHE_MAX:
            _png_cache.popitem(last=False)
    return out


# ---------------------------------------------------------------- routes

def _base(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    if host.endswith(".onrender.com"):
        proto = "https"
    return f"{proto}://{host}"


async def _card_or_404(belief_id: str) -> dict:
    c = await run_in_threadpool(card, belief_id)
    if not c:
        raise HTTPException(status_code=404, detail="not found")
    return c


@router.get("/c/{belief_id}.png")
async def share_png(belief_id: str):
    c = await _card_or_404(belief_id)
    png = await run_in_threadpool(render_png, c)
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/c/{belief_id}.json")
async def share_json(belief_id: str, request: Request):
    c = await _card_or_404(belief_id)
    url = f"{_base(request)}/c/{belief_id}"
    return JSONResponse({**c, "headline": headline(c), "url": url, "copy_text": copy_text(c, url)})


@router.get("/c/{belief_id}", response_class=HTMLResponse)
async def share_page(belief_id: str, request: Request):
    c = await _card_or_404(belief_id)
    base = _base(request)
    print(f"[share] card view {belief_id} ua={request.headers.get('user-agent', '')[:60]!r}")
    return HTMLResponse(page_html(c, f"{base}/c/{belief_id}", f"{base}/c/{belief_id}.png"),
                        headers={"Cache-Control": "public, max-age=600"})
