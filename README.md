# MarketPlayground

Type what you believe about the world ("plumbing demand is about to boom", "air travel slows down next year"). MarketPlayground finds the companies and funds that belief affects and a strategy for each: shares, options spreads or ETFs, sized to your risk level, with an interactive profit/loss chart. Every user's results feed one shared learning system.

## What's where

| Folder | What it is |
|---|---|
| `frontend/` | The app (React + Vite + Tailwind). Main screens: Home, Believe (chat), Trending, Baskets, Portfolio. |
| `backend/` | The API (FastAPI). Entry point: `backend/app.py`. |
| `backend/v4/` | The belief engine: Claude interprets the belief, Alpaca checks tickers and prices, rules pick the trade, every pick is graded, and a neural network learns from all users. See [`backend/v4/README.md`](backend/v4/README.md). |
| `backend/engine_switch.py` | Picks the engine. `ENGINE_VERSION=v4` (default) or `legacy` (original GPT-4 + ML engine, needs `OPENAI_API_KEY`). |
| `docs/` | Waitlist landing page (GitHub Pages: Settings → Pages → branch, `/docs`). |
| `archive/` | Old code, models, reports and leftovers no longer used. Kept for reference; nothing imports it. |
| `render.yaml` | Render Blueprint: backend, website, Postgres database, daily grading and seeding jobs. |

## Deploy (Render)

1. Render → New → Blueprint → this repo and branch.
2. Paste `ANTHROPIC_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` when asked.
3. After the first deploy, check the backend's URL on its Render page. If it isn't
   `https://marketplayground-backend-18mm.onrender.com`, set `VITE_API_BASE` on `marketplayground-web`
   to the real URL and redeploy the website.
4. Visit `<backend>/health` to confirm keys and database are set (it shows true/false only).
5. Seed the learning once: see `backend/v4/README.md`.

## Run locally

```bash
# backend (from repo root)
pip install -r requirements.txt
export ANTHROPIC_API_KEY=... ALPACA_API_KEY=... ALPACA_SECRET_KEY=...
PYTHONPATH=./ uvicorn backend.app:app --port 8000

# frontend
cd frontend && npm ci && npm run dev     # opens on http://localhost:5173, talks to localhost:8000
```

## Tests

```bash
PYTHONPATH=./ python -m pytest backend/v4/tests -q   # engine, learning, network, API, rate limit
cd frontend && npm test                              # profit/loss math behind the charts
```

## Settings worth knowing

| Variable | Default | What |
|---|---|---|
| `ENGINE_VERSION` | `v4` | `legacy` switches back to the old engine |
| `MP_CLAUDE_MODEL` | `claude-sonnet-5-5` | Model for belief interpretation |
| `MP_RATE_LIMIT` / `MP_RATE_WINDOW_SECONDS` | `20` / `600` | Per-visitor cap on endpoints that call Claude |
| `MP_ADMIN_TOKEN` | generated | Protects admin endpoints (grading, retraining, server-side trades) |
| `ALPACA_DATA_FEED` | `iex` | `iex` works on Alpaca's free plan; `sip` needs a paid data plan |
| `ALLOWED_ORIGINS` | — | Extra website origins allowed to call the API (comma-separated) |

For education, not investment advice.

## Real money (Stage 2) — switched off

People connect their **own** Alpaca account (Alpaca Connect / OAuth) and approve every order; Alpaca holds
the money. Code: `backend/v4/brokerage.py`, `/v4/broker/*`, the Account page card, and the "Buy in my
Alpaca account" button on stock ideas. Stocks only, dollar-amount market orders, preview → tick → confirm,
2-minute preview expiry, per-order cap, encrypted tokens, every order logged in `broker_orders`.

Turn on only after a securities lawyer signs off:
1. Alpaca dashboard → OAuth Apps → register the app; callback URL `<backend>/v4/broker/callback`.
   Live trading for other people needs Alpaca's approval.
2. On the backend in Render set `ALPACA_OAUTH_CLIENT_ID`, `ALPACA_OAUTH_CLIENT_SECRET`,
   `ALPACA_OAUTH_REDIRECT_URI`, optionally `MP_REAL_MONEY_PILOT=email1,email2`, then `MP_REAL_MONEY=on`.
3. Test with `MP_BROKER_ENV=paper` (the practice side of real Alpaca accounts) before switching to `live`.
