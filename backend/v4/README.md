# MarketPlayground v4 belief engine

Turns any belief — "plumbing demand is going to be high", "potatoes are in demand",
"AAPL hits 250" — into trade ideas, and learns from every user's results.

## How a belief flows

1. **Shared memory** (`learning.py`): finds similar past beliefs from all users and
   how their picks were graded, plus each ticker's track record on those themes.
2. **One Claude call** (`interpreter.py`): interprets the belief, gives direction,
   horizon, conviction, themes, the reasoning chain, and 5–12 candidate tickers.
3. **Validation** (`market.py`): every ticker must be a real, active, tradable US
   equity on Alpaca with price history.
4. **Scoring**: Claude's score + graded track record + user votes + the neural
   network (once it has earned a say).
5. **Trade structure** (`strategy.py`): plain rules (direction × horizon ×
   conviction × risk profile), shifted only when graded results show a clear edge.
6. **Saved** (`db.py`) for grading and learning.

## How it learns

- `grader.py` (daily) grades every pick at 7/30/90/180/365 days: return vs SPY in
  the direction the belief called for, plus the return of the trade structure.
- `nn.py` is MarketPlayground's own neural network. It predicts how well a
  (belief, ticker) pair will do. It is tested **walk-forward** (trained on older
  picks, tested on later ones it never saw) and only goes **active** when its top
  pick beats both the average candidate and Claude's own top pick. Until then it
  runs in **shadow** mode: it scores picks, but users don't see the effect.
- `seeder.py` feeds it beliefs:
  - `backfill`: beliefs at random past dates, graded immediately. Fast start.
    Claude may know how those years went, so these rows never show Claude's
    score/rank to the network, and are tagged `seed_backfill`.
  - `live`: fresh beliefs every day, graded going forward. Clean data.

## Setup

Environment variables (backend service and cron jobs):

| Variable | What |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` | already used by the app |
| `DATABASE_URL` | Postgres URL. **Required on Render** — local files are wiped on each deploy. `render.yaml` creates `marketplayground-db` and wires it up. Without it, a local SQLite file is used. |
| `ENGINE_VERSION` | `v4` (default) or `legacy` to switch back to the old engine |
| `MP_CLAUDE_MODEL` | default `claude-sonnet-5-5`; `claude-haiku-5-5` is cheaper |
| `MP_ADMIN_TOKEN` | protects `POST /v4/admin/grade` |
| `ALPACA_DATA_FEED` | `iex` (default, free plan) or `sip` |

Kick-start the network (run once, from the repo root, with the env vars set):

```bash
PYTHONPATH=./ python -m backend.v4.seeder backfill --n 300 --generate 100 --max-usd 5
PYTHONPATH=./ python -m backend.v4.grader --train
```

`--max-usd` is a hard cap on Claude spend; the seeder uses Haiku by default
(about a cent or less per belief).

## API

- `POST /strategy/process_belief` — existing endpoint, now served by v4 (same response shape, plus `picks`, `belief_id`, `pick_id`)
- `POST /v4/belief` — `{belief, user_id, risk_profile}`
- `POST /v4/feedback` — `{belief_id, kind: up|down|executed, pick_id?}`
- `GET /v4/belief/{id}` — belief, picks and their grades
- `GET /v4/stats` — counts, Claude spend, network status
- `POST /v4/admin/grade?train=true` — header `X-Admin-Token`

## Tests

```bash
PYTHONPATH=./ python -m pytest backend/v4/tests -q
```

Option premiums are Black-Scholes estimates from realized volatility, used to
grade structures consistently. Check live quotes before placing real orders.

## Proving the learning works (offline, free)

```bash
PYTHONPATH=./ python -m backend.v4.ml_check --quick
```

Builds a fake market where the right answers are known, runs the real engine → grader → network
on it, and checks: (1) with a real signal the network gets promoted and improves the top pick over
Claude alone, (2) on pure noise it is never promoted. Last run: promoted on signal at 800 practice
beliefs in both seeds, never promoted on noise, peak memory ~225 MB.

Admin view of every network version: `GET /v4/admin/ml` with header `X-Admin-Token`.
Public, plain-English view: `GET /v4/learning` (the app's "How it learns" page).
