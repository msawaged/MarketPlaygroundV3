"""
"How sure are you?": the user's own stated probability on a call, and how well-calibrated they are.

When someone makes a call they can say how sure they are that it plays out (55 / 65 / 75 / 90%). The call is
graded the usual way (grader.score_selection's belief_right: did the theme beat the S&P 500 in the direction they
called) at the checkpoint that matches the call's horizon. Here we only compare what they said with what happened:
a Brier score (mean of (said - outcome)^2; 0 is perfect, 0.25 is what always saying 50% scores) and a small
said-vs-actual table, shown once there are enough graded calls to say anything.

Information only: it mirrors the user's own track record. It's not advice, it never feeds rankings or research.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from . import db, grader, market

CHOICES = (0.55, 0.65, 0.75, 0.90)
MIN_GRADED = 10          # below this the card shows a countdown, not a score
MIN_BUCKET = 3           # below this a row says "too few to say"
SET_WINDOW_DAYS = 1      # a probability can be set or changed until the day after the call (before the outcome shows)
NEAR = 0.10              # within 10 points of what you said counts as "about right"


def checkpoint_for(horizon_days) -> int:
    """The graded checkpoint a call's probability is scored at: the first one at or after its horizon."""
    try:
        h = int(horizon_days or 0)
    except (TypeError, ValueError):
        h = 0
    for cp in grader.CHECKPOINTS:
        if cp >= h:
            return cp
    return grader.CHECKPOINTS[-1]


def can_set(as_of_date: str, today: Optional[date] = None) -> bool:
    today = today or market.today()
    try:
        made = date.fromisoformat(str(as_of_date)[:10])
    except ValueError:
        return False
    return today <= made + timedelta(days=SET_WINDOW_DAYS)


def normalize(prob) -> Optional[float]:
    """Accept 0.55 or 55 (and the other choices); anything else is rejected (None)."""
    try:
        p = float(prob)
    except (TypeError, ValueError):
        return None
    if p != p:
        return None
    if p > 1:
        p = p / 100.0
    for c in CHOICES:
        if abs(p - c) < 1e-6:
            return c
    return None


def _verdict(said: float, actual: float, n: int) -> str:
    """'about right' within 10 points. Past that, a firm verdict only when the gap is also beyond two binomial
    standard errors of what they said (so small samples read 'leaning ...', not a confident label)."""
    gap = actual - said
    if abs(gap) <= NEAR:
        return "about right"
    word = "overconfident" if gap < 0 else "underconfident"
    se = (said * (1 - said) / max(1, n)) ** 0.5
    return word if abs(gap) > 2 * se else f"leaning {word}"


def score(pairs: list[tuple[float, int]], pending: int = 0) -> dict:
    """pairs: (stated probability, outcome 1/0) for graded calls. Pure; no DB."""
    n = len(pairs)
    out: dict = {"graded": n, "pending": int(pending), "min_graded": MIN_GRADED, "ready": n >= MIN_GRADED}
    if n == 0:
        return out
    brier = sum((p - o) ** 2 for p, o in pairs) / n
    said = sum(p for p, _ in pairs) / n
    hit = sum(o for _, o in pairs) / n
    out.update({"brier": round(brier, 4), "avg_said": round(said, 3), "hit_rate": round(hit, 3),
                "baseline_brier": 0.25})
    rows = []
    for c in CHOICES:
        g = [o for p, o in pairs if p == c]
        if not g:
            continue
        a = sum(g) / len(g)
        rows.append({"said": c, "n": len(g), "right": int(sum(g)), "actual": round(a, 3),
                     "verdict": _verdict(c, a, len(g)) if len(g) >= MIN_BUCKET else "too few to say"})
    out["buckets"] = rows
    out["overall"] = _verdict(said, hit, n)
    return out


def for_user(user_id: str) -> Optional[dict]:
    """The calibration card for one user (None if they never stated a probability)."""
    if not user_id or user_id == "anonymous":
        return None
    calls = db.query(
        "SELECT id, user_prob, horizon_days FROM beliefs WHERE user_id = ? AND source = 'user' AND user_prob IS NOT NULL",
        (user_id,))
    if not calls:
        return None
    want = {r["id"]: (float(r["user_prob"]), checkpoint_for(r["horizon_days"])) for r in calls}
    graded: dict = {}
    ids = list(want)
    for k in range(0, len(ids), 200):
        chunk = ids[k:k + 200]
        ph = ",".join("?" for _ in chunk)
        for r in db.query(
                f"""SELECT p.belief_id, o.checkpoint_days AS cp, MAX(o.belief_right) AS r
                    FROM outcomes o JOIN picks p ON p.id = o.pick_id
                    WHERE p.belief_id IN ({ph}) AND o.belief_right IS NOT NULL
                    GROUP BY p.belief_id, o.checkpoint_days""", chunk):
            if want[r["belief_id"]][1] == int(r["cp"]):
                graded[r["belief_id"]] = int(r["r"])
    pairs = [(want[b][0], o) for b, o in graded.items()]
    return score(pairs, pending=len(want) - len(pairs))
