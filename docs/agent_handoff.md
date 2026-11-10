# Agent handoff

Short notes between the Claude sessions working on this repo (build chat, research routine, polish routine, weekly
brain upgrade). Newest at the bottom. One entry per session that pushed something: date, who, what changed, files,
and anything the others must know. Keep entries to a few lines; details go in the topic logs.

## 2026-11-06 (research routine)
- Added idea 5, MAX effect ("avoid lottery stocks", rule `-z_max5`), commit 6b6efd1. New feature `max5` in
  `market.py` (`max5`, `max_features`, `features()`), `nn.make_features` num (not MODEL_NUMERIC), `research.FEATS` +
  `DIRECTIONAL`, and `research.enrich` backfill. Test: `test_max_effect_lottery_rule_and_enrich_backfill`.
- `enrich` is backfilling `max5` for older picks; research results for that rule are unreliable until it finishes.
- Logged the 2026-11-06 16:15 rerun (after volatile ideas were excluded) in `docs/research_ideas.md`.

## 2026-11-07 (research routine)
- Added `CLAUDE.md` and this file so sessions can hand work to each other through the repo.

## 2026-11-07 (polish routine)
- seeder.news_beliefs: the "I don't think ..." side no longer lower-cases names/acronyms (`_lower_first`); existing
  DB rows ("aI", "iran") are unchanged and age out of the feed. Belief text format is otherwise the same.
- /v4/brain `graded[]` gains `stock_vs_market`; Brain page "Just graded" shows the stock's move vs S&P, and the
  ranker box says "retrained <date>" instead of "live since". Files: backend/v4/seeder.py, backend/v4/brain.py,
  backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx.

## 2026-11-08 (build chat, CTO)
- research.py: new `MLPRanker`/`_fit_mlp`; ranker v2 now also evaluates "neural net (learned)" / "(risk-adjusted)"
  and `fit_production` may pick `mlp`/`mlp_adj` (kind "mlp", stored in GBM_KEY). Gate untouched. nn.py:
  `_training_rows` ORDER BY p.id. Details in docs/brain_upgrades.md (2026-11-08). Murad is in hospital: he wants
  sessions self-sufficient and to notify only when his action is needed.
- brain.py `_forward()` → `/v4/brain` `forward`: live forward test (non-backfill calls, directional ideas) per
  checkpoint: #1 beat rate, avg, lift vs same-belief ideas, t. BrainPage shows it under the scorecard. This is the
  metric Murad will use before trading his own money; don't fold backfill into it.
- augment.py (new) + seeder hourly `augment` step + research.load(include_aug) / run / fit_production "+ shifted"
  candidates. research.load builds compact rows directly (FeatRow.from_array, `_matrix`). Shifted calls are
  training-only; don't let them into tests or baselines. Env: MP_AUG_SHIFTS, MP_AUG_BATCH, MP_AUG_MAX.
- IMPORTANT: picks.final_rank is 0-based (0 = the #1 shown). research/lineages/brain used == 1 (the #2) until
  today; fixed. Use rank 0 for "app #1" everywhere. Expect ranker v2 + net to turn off at the next refit (the real #1
  is a higher bar). New: confidence thirds (`research.confidence_label`, ranker `confidence`, pick `confidence`,
  features `rv2_conf`/`rv2_spread`/`rv2`), `/v4/brain` `forward.by_confidence`.
## 2026-11-08 (daily polish walk)
- Frontend only: WhatsNew.jsx (no "Smarter #1 pick" claim while ranker v2 can be off; date Nov 8), BrainPage.jsx forward
  test now renders `forward.by_confidence` (keys high/medium/low) and a t-stat note; its lift is labelled "vs our
  average idea" because `_forward` and research lift include the #1 in the average. StrategyCard badge tooltip reworded.
  No backend changes. If you change `_forward`'s lift to exclude the #1, update those labels.
## 2026-11-09 (build chat, CTO)
- Gate amendment approved by Murad (option B): `<key>_mix` candidates (model mixed into the app score at
  MIX_WEIGHT 0.25) must pass `_passes` vs the real app #1 AND `research.live_check` (>=300 real-time calls graded at
  30 days, mix avg >= app avg). Ranker record gains `weight`, `mix`, `live`; engine uses `ranker.weight`.
  `research.load(days=, live_only=)`. Env: MP_RANKER_MIX_WEIGHT, MP_RANKER_LIVE_DAYS, MP_RANKER_LIVE_MIN.
## 2026-11-09 (daily "Market's open" reel routine, follow-up with Murad)
- Reels now have a voiceover and no music (Murad approved). `scripts/make_reel.js` fetches the story itself, speaks one
  line per card with `scripts/reel_voice.py` (Kokoro, free, local; model cached in ~/.cache/kokoro, needs
  `pip install kokoro-onnx soundfile`), records `/reel?h=..&d=..` with each card as long as its line, and mixes the
  voice in at each card's start (`window.__reelMarks`). VOICE=0 = old silent reel. STORY_JSON = one-off story.
- The app is still pre-launch: the reel's last card says "MarketPlayground is coming soon / Follow for launch day".
  `/reel?live=1` (make_reel `LIVE=1`) switches it back to "Make your call free". Flip that at launch, not before.
- Files: frontend ReelPage.jsx + StoryViewer.jsx (optional `durations`, `launched`; normal Story mode unchanged),
  scripts/make_reel.js, scripts/reel_voice.py, scripts/social/README.md.
- Feed gap: today's biggest story (Nvidia board probing Jensen Huang over an alleged Chinese spy, NVDA about -5%) never
  showed up as its own item in /v4/movers. Worth a look by whoever owns the movers ranking.
- (same day, later) Reels now open on a ~2s brand card (logo, wordmark, "Story mode" pill) and show a "Story mode" pill
  in the header, so viewers tie the reel to the in-app feature. Reel-only (`reel` prop); in-app Story mode unchanged.
  The voice's first line is "MarketPlayground Story mode." (make_reel.js voiceLines). Keep them in sync if you edit.
## 2026-11-09 (daily ranker research routine)
- Idea 5 (MAX / lottery) result logged: no edge (raw -0.87%, t -2.40; adj -0.32%). Idea 6 added: Novy-Marx
  intermediate momentum `mom_12_7` (close[t-125]/close[t-250]-1), new feature in market.features/echo_features,
  nn.make_features num, research.FEATS + DIRECTIONAL, enrich backfill (as of each pick's date), rule
  `intermediate momentum (z_mom_12_7)`. Gate untouched. Files: backend/v4/market.py, nn.py, research.py,
  tests/test_v4.py, docs/research_ideas.md.
- test_ranker_v2_picks_the_stronger_model: the "loses -> ridge" step now zeroes every non-ridge learned candidate
  (the net could win by chance on the tiny synthetic set once a feature was added). Test-only; gate untouched.
## 2026-11-09 (daily polish walk)
- OUTAGE ~21:00-21:40 UTC: backend hung at startup (502 everywhere) because a 44-minute ad-hoc SELECT run through the
  Render Postgres query tool held picks; startup's no-op `ALTER TABLE picks ADD COLUMN` queued behind it and blocked
  everything else on picks. I cancelled that query. **If you run ad-hoc SQL on prod, keep it small**: the query keeps
  running on the server after the tool call times out. No correlated subqueries over outcomes/picks; do heavy
  analysis locally on an export.
- Fix: backend/v4/db.py ensure_schema skips migrations whose column exists (no lock) and bounds DDL lock waits
  (lock_timeout 10s). Test in tests/test_v4.py. When you add a migration keep the "ALTER TABLE t ADD COLUMN c ..." shape
  (`_migration_target` parses it; the test asserts every migration does).
- d856c72 (research, app baseline without look-ahead) had not deployed because of the outage; it ships with this push.
## 2026-11-09 night (build chat, CTO, scheduled check)
- Nightly run OK. gbm_adj_aug_mix passes `_passes` but waits on live_check (0/300 real-time calls at 30 days). Docs
  only: docs/brain_upgrades.md (2026-11-09 night check) incl. a proposal (point-in-time baseline) left for Murad.
- Note from the polish walk respected: keep ad-hoc prod SQL small (I only read kv_cache rows tonight).
## 2026-11-10 (build chat with Murad: personal real-money + options + public journey)
- Murad asked for real-money trading for HIS OWN account only (pre-launch), options included, and a public
  "watch my journey" record for IG/TikTok. Still OFF in production until he sets env vars himself:
  MP_REAL_MONEY=on, MP_BROKER_ENV=live, MP_BROKER_KEY_ID / MP_BROKER_SECRET_KEY (his live Alpaca keys; separate from
  ALPACA_API_KEY which stays market-data only), MP_REAL_MONEY_PILOT=<his email>, MP_JOURNEY_PUBLIC=on.
  Optional MP_JOURNEY_SHOW_DOLLARS=on (default: percentages only), MP_MAX_ORDER_USD (default 1000).
- brokerage.py: "keys mode" requires a non-empty pilot list (empty = nobody, never everyone). preview_option (single
  listed call/put, buy to open, LIMIT, cap + options buying power, closest listed contract), preview_close (sell what
  you hold only; no shorts / naked options), positions, orders (+ _sync of fills), journey (FIFO lots via build_lots,
  vs SPY at preview time). broker_orders.request is now {"order", "meta"}; place() still reads old flat rows.
- Routes: /v4/broker/preview_option, /preview_close, /positions, /orders, public /v4/journey. market.option_quote,
  market.parse_occ. Frontend: RealMoneySheet (stock/option/close modes, portalled to body), StrategyCard real-money
  button for single-leg Long Call/Long Put, AccountPage holdings + Sell + "Deposit or withdraw in Alpaca" link
  (Alpaca's Trading API can't move money), new public /journey page. No spreads yet. Don't open this to other users
  without Murad + a securities lawyer (adviser question discussed with him).
## 2026-11-10 (build chat, later: take-profit / max-loss exits, Murad chose hybrid "C")
- New backend/v4/exits.py + broker_exits table. Stocks: exits ride on the buy as an Alpaca bracket/OTO order (whole
  shares, gtc), nothing watched. Options: max-loss = a STOP order at Alpaca re-armed each trading day (option orders are
  day-only); take-profit watched by exits.tick() (15s in market hours), which cancels the stop and sells at the bid.
- Restart safety: state in DB, catch-up on first tick, DB lease (`exits:lease`) so only one runner sells, heartbeat
  `exits:beat`; exits.watchdog() runs in the web service and in the hourly seeder cron and pushes the owner if silent.
- Runner: thread in the web service (MP_EXITS_RUNNER=web, default). Plan agreed with Murad: move to its own Render
  background worker (`PYTHONPATH=./ python -m backend.v4.exits`, MP_EXITS_RUNNER=worker on the web service) before take-
  profits are used regularly / before other users. Murad creates that ($7/mo); don't create paid services.
- Selling by hand (place() with side sell) cancels open sell orders for that symbol and turns its exits off first.
- Files: exits.py, brokerage.py (tp_pct/sl_pct on preview + preview_option, _clear_exits_for_sale), router.py
  (/broker/exits, /broker/exits/{id}/cancel), db.py, seeder.py (watchdog), app.py, frontend RealMoneySheet, AccountPage,
  lib/broker.js. Next agreed with Murad: option "Price check" (parity + IV vs realized vol, daily option-IV logging),
  then a point-in-time experiment log + real fills feeding cost/slippage modelling (not P&L into rankings).
## 2026-11-10 (build chat, later: option Price check + daily option-vol log + feature_log)
- backend/v4/pricecheck.py: put-call parity gap vs the bid-ask spread (European formula, explained as dividends /
  borrow / early exercise; never "free money"), implied vs realized vol (cheap < 0.9x, expensive > 1.35x of 60-day RV),
  spread cost, and IV percentile once 20+ days are logged. Public GET /v4/price_check (10-min cache). MP_RISK_FREE
  (default 0.038, 3-month T-bill Nov 2026). market.option_chain_near.
- New tables: option_vol_daily (one row per underlying per trading day: ATM IV ~30d, RV20/60, put-call skew; written by
  pricecheck.log_daily from the hourly seeder after 16:15 ET) and feature_log (point-in-time record of any feature's
  verdict for a pick; price_check writes it when a pick_id is passed). Brain: once option_vol_daily has history, test
  "cheap/expensive" against graded outcomes through the normal gates; don't use it in rankings before that.
- Frontend: chat/PriceCheck.jsx on option idea cards ("Is this a fair price?", loads on tap).
- (same day) Price check fixes found on live AAPL data: cheap/expensive uses AT-THE-MONEY IV from a chain around the
  stock price (far strikes carry smile/skew IV; that's explained separately, never called "expensive"); parity is only
  judged while the market is open (overnight the stock's last trade and option quotes are from different moments).
  Next (not built): real fills vs preview estimates (broker_orders est_price vs filled_avg_price) feeding a
  spread/slippage model for practice grading, once real trades exist.
