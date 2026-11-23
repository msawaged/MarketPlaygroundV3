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
## 2026-11-10 (build chat, later: in-app Real money switch + user setup flow)
- Account page card "Real money" with a switch everyone sees. Non-pilot users: locked, "Coming soon". Owner (MP_OWNER_EMAIL,
  else first MP_REAL_MONEY_PILOT email): sees a server-setup checklist (which settings exist, never values) until set up.
  Pilot users not connected: 4-step connect guide (open Alpaca, Connect Alpaca via OAuth, per-order limit, switch on).
- Server: per-account switch `rm:on:<id>` and limit `rm:cap:<id>` in kv_cache; POST /v4/broker/switch {on, max_order_usd}.
  Switch OFF blocks new BUY previews/orders only; selling and the exits watcher always work. Default is OFF; disconnect
  turns it off. Real-money buttons on idea cards need broker.on. Files: brokerage.py, router.py, AccountPage.jsx,
  StrategyCard.jsx, lib/broker.js, tests.
## 2026-11-10 (daily ranker research routine)
- Idea 6 (Novy-Marx 12-7 echo) result logged: lift +0.77%, beat 50.0%, t 2.20 (adj +0.38%, t 1.12), no better than
  plain 12-1. Idea 7 added: moving average distance `mad` = MA21/MA200 - 1 (Avramov, Kaplanski & Subrahmanyam 2021),
  new feature in market.features/mad_features, nn.make_features num, research.FEATS + DIRECTIONAL, enrich backfill
  (as of each pick's date), rule `moving average distance (z_mad)`. Gate untouched. Files: backend/v4/market.py, nn.py,
  research.py, tests/test_v4.py, docs/research_ideas.md.
## 2026-11-10 (daily polish walk)
- Price check wording only (no thresholds or logic changed: cheap < 0.9x, expensive > 1.35x, parity rules untouched):
  headline "Normal price vs how much the stock moves" instead of "Fairly priced", realized vol described as yearly
  swings (not "moved X%"), normal band says low/high end, spread % to one decimal, footnote mentions parity only when
  checked. PriceCheck.jsx shows "Closest listed contract to the idea's $K · date" when the checked contract differs.
  Smile line only when strike IV differs from ATM by 2+ vol points.
  Files: backend/v4/pricecheck.py, frontend/src/components/chat/PriceCheck.jsx, tests/test_v4.py, docs/polish_log.md.
## 2026-11-11 (daily ranker research + feature scout routine)
- Idea 7 (moving average distance) result logged: lift -0.73%, beat 51.1%, t -2.41 (adj -0.67%, t -2.33); not a
  candidate. Idea 8 added: Amihud (2002) illiquidity `amihud` = log(1 + 1e8 * mean |r| / dollar volume) over 252 days,
  new feature in market.features/amihud_features, nn.make_features num, research.FEATS + DIRECTIONAL, enrich backfill
  (as of each pick's date, closes+volumes), rule `illiquidity premium (z_amihud)`. Gate untouched.
- New docs/feature_ideas.md (backlog of proposals for Murad and other sessions). First entry: user-stated "How sure
  are you?" probability + personal Brier/calibration card (proposed, not built).
- Files: backend/v4/market.py, nn.py, research.py, tests/test_v4.py, docs/research_ideas.md, docs/feature_ideas.md.
## 2026-11-11 (weekly brain upgrade routine)
- Ranker v2 research now picks each belief's #1 only among ideas in the belief's own direction, as the engine shows it
  (`research._lead` / `_top`; `lead` flag per idea from `b.direction`). Applies to learned models, mixes, fixed rules,
  the no-look-ahead app baseline and `live_check`. Gate untouched. New diagnostics in `research:ranker`: `lead_only`,
  `mixed_direction`, `off_lead`. 39% of graded beliefs mix directions, so expect learned lifts to move at the next
  refit. Don't revert to argmax over all ideas. Follow-up not done: same rule in `lineages` (score/_graded_beliefs).
- Files: backend/v4/research.py, backend/v4/tests/test_v4.py, docs/brain_upgrades.md, docs/agent_handoff.md.
## 2026-11-11 (daily polish walk)
- engine.trending: a theme card's sample summary now comes from the newest belief in the card's (majority) direction,
  so "Bearish" is never shown above a bullish summary. WhatsNew: Price check line, UPDATED 'Nov 11'.
  Files: backend/v4/engine.py, backend/v4/tests/test_v4.py, frontend/src/components/WhatsNew.jsx, docs/polish_log.md.

## 2026-11-12 (build chat, CTO): campaign "Prove them wrong" (all routines read this)
- Murad's direction: the next promos push back on "AI bot desk turned $87 into $8,000" style hype reels. Our angle is
  receipts, not hype: every call graded in public, the small but real edge, and the gate that turns off our own models.
- Rules for every reel/caption/social post in this campaign: never name, show or tag another creator; no claims about
  their results beyond "claimed / unverified"; every number pulled live from /v4/brain the same day (skill.top vs
  skill.rest at 90 days, counts.graded, ranker.active + oos vs old); practice money, "not investment advice";
  keep "Coming soon. Got an invite? Jump in." until launch. Murad posts; we never post.
- First reel is built (prove_them_wrong.mp4): #1 pick beat the S&P 500 over 90 days 53.4% vs 51.3% for our other
  ideas (4,398 / 18,881 graded); 112,595 calls graded; the risk-matched gate switched the learned ranker off on
  2026-11-11 (ridge 53.0% vs current ranking 54.2%).
- Daily "Market's open" reel: when the day's story allows, end on one honest receipt line (e.g. today's graded count).
- Research/brain routines: the hype reel's "Skeptic" bot (argues against each trade, e.g. reward:risk < 2:1 → skip) is
  a testable idea. Treat it as a candidate filter in ranker research (does skipping low reward:risk ideas raise
  beat_adj out of sample?). Ship only if it passes `_passes`; log the result either way.
- Weekly growth report: track this campaign's posts separately when Murad shares numbers.
## 2026-11-12 (daily ranker research + feature scout routine)
- Idea 8 (Amihud illiquidity) result logged: lift +1.20%, beat 52.7%, t 3.98 (adj +1.00% / 54.2% / t 3.44), the
  strongest fixed rule so far; raw beat still below the app's, so not a gate pass on its own. Idea 9 added: continuing
  overreaction `co` (Byun, Lim & Yun 2016) = weighted signed monthly volume over 12 months, -1..+1, new feature in
  market.features/co_features, nn.make_features num, research.FEATS + DIRECTIONAL, enrich backfill (as of each pick's
  date, closes+volumes), rule `continuing overreaction (z_co)`. Gate untouched.
- feature_ideas.md: "Luck bar" proposal (count every rule tested, report Bonferroni/Holm thresholds; reporting only).
- Not done: the "Skeptic" reward:risk filter from the campaign entry above is still open for the weekly brain routine.
- Files: backend/v4/market.py, nn.py, research.py, tests/test_v4.py, docs/research_ideas.md, docs/feature_ideas.md.
## 2026-11-12 (CTO routine session, later: Murad said "build it")
- Built the "luck bar" (reporting only, gate untouched): `research.luck` → `luck` block in `research:ranker`, running
  set of tried methods in kv `research:tries` (don't delete it; it's what makes `tries_ever` honest), `skill.luck` in
  /v4/brain, "luck check" line in BrainPage's honest scorecard. Research routine: quote "clears the luck bar" from
  `luck.clear` / `clear_adj` instead of eyeballing t ≥ 2. Campaign: "we've tested N ways; X cleared" is a valid live
  receipt (pull N and X from /v4/brain the same day). Appears after the next research run.
- Files: backend/v4/research.py, brain.py, tests/test_v4.py, frontend/src/components/BrainPage.jsx, docs/brain_upgrades.md,
  docs/feature_ideas.md.

## 2026-11-12 (build chat, CTO): new feature "Yes / No" (Murad's request)
- "Will NVDA close above $150 on Fri Nov 21?" Market's odds from real option prices (N(d2) at the listed strike's IV),
  the brain's lean (small capped nudge: MuLine trend, recent ideas on the stock, people's own YES/NO), and a fixed-risk
  practice trade: YES = call spread (k1 at/below line, next strike up), NO = put spread. Opened via
  practice_options.open_trade, so it shows in Portfolio and settles at expiration like other option trades.
- Purely additive: own table `yesno_calls` (with point-in-time `features`), own endpoints /v4/yesno/*, own page /yes-no
  (entry cards on Home and Practice, What's new line). Does NOT write beliefs/picks/outcomes, so the 90-day scorecard,
  ranker research and promo numbers are unaffected. Don't route it into picks without a deliberate decision.
- Feeds the brain: hourly cron (seeder auto) grades expired questions; once a trading day (10:00-15:30 NY) the brain asks
  itself one question on 15 big tickers; nightly `yesno.learn()` fits a logistic model on graded questions and turns it
  on only if it beats the market's odds on the newest unseen 30% (Brier gain > 0, paired t >= 1.5, min 200 graded).
  Status in kv `yesno:model`, public at /v4/yesno/scorecard.
- Real money: every quote carries `real_money` = the Alpaca multi-leg (mleg) limit order for the same two listed
  contracts. available=false; brokerage.py doesn't place spreads yet and user real money is off (MP_REAL_MONEY).
  When legal signs off, wire it through brokerage preview -> confirm -> cap; don't bypass that path.
- Marketing routine: Murad wants a promo LAYOUT (storyboard + captions) for Yes / No made for tomorrow (Nov 13) for
  his review. Same campaign rules as "Prove them wrong": honest numbers only, practice money, not investment advice,
  "Coming soon. Got an invite? Jump in."; the brain's yes/no record is brand new, so don't claim it beats the market.
- Files: backend/v4/yesno.py (new), db.py (table), router.py, seeder.py, tests; frontend YesNoPage.jsx (new), App.jsx,
  ToolSelectorPage.jsx, PracticePage.jsx, WhatsNew.jsx, lib/api.js.
## 2026-11-12 (daily polish walk)
- Yes / No: YES and NO now priced with ONE volatility (the line strike's IV) so they add up to the payout; before, after
  hours they didn't (SPY YES $76 + NO $19 for $100 = free practice money). New optional `vol_override` kwarg on
  practice_options.quote/open_trade (default None = old behaviour for every other options trade). Each side has
  `breakeven`; page labels the lean "starting rules, untested" until `yesno:model` is active and drops "proven".
- Open for the build chat (not changed): YES uses k1 at/below the line, so the spread's breakeven sits above the line;
  centering the spread on the line would match the question better. SPY line chips step $25 (700-800), coarse for
  1-day questions.
- Files: backend/v4/yesno.py, practice_options.py, tests/test_v4.py, frontend/src/components/YesNoPage.jsx,
  docs/polish_log.md.

## 2026-11-12 evening (build chat, CTO): Yes / No is now named "Close Call"
- Murad asked for a name: **Close Call** (every question is about where a stock closes). Page title, Home card,
  Practice link, What's new and practice-trade label renamed; route /close-call added (/yes-no still works).
  Backend module/table/endpoints keep the yesno name (internal). Marketing: call the feature "Close Call".

## 2026-11-12 night (build chat, CTO): social bot queue + first queued post
- Murad approved "Close Call vs Polymarket" (78s, voiceover) and asked to hand it to the posting agent.
- scripts/social/post.js now: git pull --ff-only before each run; posts the oldest item in scripts/social/queue/<id>/
  (video.mp4 + caption.txt) before any auto-made post; marks it done in ~/.mp_social/state.json only after a
  successful post. Queued: 2026-11-13-close-call. Only Murad-approved posts go in the queue.

## 2026-11-12 night, update (build chat, CTO): Close Call video goes to marketing; Murad posts it himself
- Murad: "Just send to agent and I'll post." The video is NOT in the bot queue (removed so nothing double-posts).
- Final files for the marketing agent: docs/marketing/close-call/close_call_vs_polymarket.mp4 (78s, voiceover) and
  docs/marketing/close-call/caption.txt (IG/TikTok caption with sources). Murad posts it manually.
- Marketing agent: treat this as the launch video for Close Call; build tomorrow's short announcement layout to
  complement it (don't redo the Polymarket comparison), and log reach when Murad shares numbers.

## 2026-11-12 night (build chat, CTO/CMO): two Close Call teasers for Murad to post
- docs/marketing/close-call/close_call_teaser_tonight.mp4 (26s) + caption_teaser_tonight.txt: "Yes or no" hook,
  live NVDA $170 Fri Nov 20 question (market odds 42%, YES risk $100 to make $150), brain's 112,595 graded calls.
- close_call_teaser_tomorrow.mp4 (37s) + caption_teaser_tomorrow.txt: how the brain grew (3 beliefs Oct 28 -> 6,248;
  112,595 graded; Gen 10, 16 retired; 38 ways tested; learned ranker switched off 53.1% vs 54.2% risk-adjusted) and
  "Close Call record 0-0, starts today, 15 questions a day". Says "16 days ago", so it's for Nov 13.
- Every number came from /v4/brain and /v4/yesno on Nov 12 21:46 ET. On-screen notes say most graded calls are
  replays on past markets since Oct 2023 (4,741 of 6,248 beliefs). Source + render script: teaser_src/.
- Murad posts both himself (not in the bot queue). Marketing agent: log reach when he shares numbers.

## 2026-11-13 (marketing routine, CMO): Close Call short announcement layout for Murad's review
- Draft only, nothing posted: ~23s vertical reel, 6 scenes (hook / the question / market vs brain odds / YES-NO with
  practice money / every answer graded / "Coming soon. Got an invite? Jump in."). No stock, price, date or trade
  numbers; odds bars have no percentages; brain's lean labeled "record: brand new". Complements the Polymarket video.
- Files: docs/marketing/close-call/announce_layout/ (frames.html + shoot.js -> frame_1..6.png at 1080x1920,
  contact_sheet.png, storyboard.md with VO lines, captions.txt with IG/TikTok + 160-char Snapchat).
- Waiting on Murad's go-ahead or changes before rendering the full reel (voiceover via scripts/reel_voice.py, like teaser_src).

## 2026-11-13 (daily ranker research + feature scout routine)
- Idea 9 (continuing overreaction `co`) result logged: lift +0.09%, beat 50.6%, t 0.32 (adj +0.29% / 52.7% / t 1.05);
  no edge, doesn't clear the luck bar. Idea 10 added: return seasonality `seas` (Heston & Sadka 2008) = average
  return over the same ~3 months (63 sessions) starting 1-4 years before the pick's date; new feature in
  market.features/seas_features, nn.make_features num, research.FEATS + DIRECTIONAL, enrich backfill (as of each
  pick's date), rule `same season, past years (z_seas)`. Gate untouched.
- feature_ideas.md: "Honest t-stats" proposal (Newey-West / date-clustered t's: 2,703 test beliefs sit on 429 dates
  with overlapping 90-day windows; reporting only).
- Files: backend/v4/market.py, nn.py, research.py, tests/test_v4.py, docs/research_ideas.md, docs/feature_ideas.md.

## 2026-11-13 (weekly brain upgrade routine)
- Lineages now score each strategist's #1 within the belief's own direction (`lineages._lead`, `lead` flag from
  `b.direction` in `_graded_beliefs`), the same rule research got on 2026-11-11. Champion gate constants unchanged.
  Expect lineage fitness on the brain page to dip a little after tonight's evolve; that's the leak coming out, not a bug.
- Health ok; NN retrains are frozen at n_train 11,408 because 90-day labels only exist for practice calls until
  real-time calls reach 90 days (~late Jan); identical shadow results day to day are expected.
- Files: backend/v4/lineages.py, backend/v4/tests/test_v4.py, docs/brain_upgrades.md, docs/agent_handoff.md.

## 2026-11-13 evening (daily polish walk)
- Seeder news beliefs: the "I don't think ..." opposite is now made only for single, un-negated hunches
  (`seeder._negatable`): compound ("X and could Y", ", and", "but", "while", ", so") or already-negative hunches gave
  ambiguous opposites that were learned as the same side (e.g. both Tesla-SpaceX sides bearish TSLA). Fewer seed_news
  beliefs per hour (~5%); no gate or ranker change.
- Close Call: clearer "couldn't load options" message (was "Try a bigger company" even for SPY).
- Files: backend/v4/seeder.py, backend/v4/yesno.py, backend/v4/tests/test_v4.py, docs/polish_log.md.

## 2026-11-13 evening (build chat, CTO): Agent HQ — every agent at one table with Murad
- Murad wanted one place to talk to all agents and see what they need. Page: /hq (owner only via
  brokerage.is_owner; link on Account for the owner). Endpoints GET /v4/hq, POST /v4/hq/message (owner session).
- Murad's messages: table hq_messages (id, author, to_agent, body, created_at). Agent status + replies:
  docs/hq/status/<key>.json, read by the backend from GitHub raw (2-min cache; falls back to the deployed copy).
- EVERY agent: follow docs/hq/README.md — read your messages at the start of a run (read-only SQL), write your
  status file at the end (status-only commits use "[skip render]"). Keys: cto, health, reel, scout, brain, polish, growth.
- Files: backend/v4/hq.py (new), db.py, router.py, tests; frontend HQPage.jsx (new), App.jsx, AccountPage.jsx,
  lib/api.js; docs/hq/ (agents.json, README.md, status/*.json seeded by the CTO).

## 2026-11-13 night (build chat, CTO): reviewer is a derivatives expert — read docs/expert_review.md
- Prof. Brown worked on exotic contracts at Credit Suisse; Murad: "the smartest person I know". Every agent holds
  options content to a desk's standard. Checklist: docs/expert_review.md.
- Close Call odds now come from the tight call spread around the line (skew included, `digital_from_spread`);
  single-vol N(d2) is only a labelled fallback. Quote returns `odds_source` and `market_p_flat_vol`. Screen labels
  odds "risk-neutral" and says practice prices are before bid/ask costs.

## 2026-11-13 night (build chat, CTO): options card numbers now exact
- library.economics read max loss / max gain off a 2,400-point grid that stepped over the strikes, so payoffs that
  peak or bottom exactly at a strike were misstated by up to ~1% (e.g. a $480 straddle showed max loss $2,344 vs
  $2,372 actually paid; butterfly max gain understated). Now evaluated exactly at 0, every strike and a far point,
  breakevens solved per segment. Independent audit of 22 structures x 45 price/vol/horizon cases: 0 mismatches
  (was 36). Test: test_economics_exact_at_strikes.

## 2026-11-14 early (daily polish walk)
- Close Call: YES / NO practice prices now come from the listed mid of the trade's own k1/k2 call spread
  (`yesno.spread_vol`, a flat vol fitted to that mid), so cost agrees with last night's spread-based odds; line IV is
  the fallback (also when the fit is >20% off the line IV: noisy quotes). Quote adds `price_vol`, `price_source`; make_call opens trades with `price_vol`. Features unchanged.
- Close Call odds guard (on top of the build chat's `digital_from_spread`, not replacing it): a spread digital >10
  pts from the one-vol N(d2) is treated as stale quotes (live SPY after hours: 61% above $755 with spot $752) and
  the labelled one-vol fallback is shown.
- Brain page "N today" is the New York day now (was UTC). "Both sides of most stories" wording.
- Files: backend/v4/yesno.py, backend/v4/brain.py, backend/v4/tests/test_v4.py, frontend YesNoPage.jsx, BrainPage.jsx,
  docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-13 night (build chat, CTO): options cards priced at implied volatility
- Cards were priced with 60-day historical vol; desks price at implied (usually higher, so cards made long options
  look cheap). engine.card_vol: the 3 shown picks of a live belief use market.option_iv near the card's expiry and
  the money (cached 30 min), falling back to vol60; backfill and unshown picks stay on vol60. trade.vol_source =
  "implied" | "historical"; the card says which, with the vol %. Don't switch grading to a different vol: a pick is
  graded with the vol stored on its trade.

## 2026-11-14 (Builder routine): option cards explain American exercise, assignment and pin risk
- Expert-review checklist item ("American exercise, dividends, early assignment, pin risk ... never claim European
  payoffs"). `library.exercise_notes(legs, ticker)` returns plain-words notes; `strategy.build_trade` adds them as
  `trade.exercise` (also on alt trades). Per short leg: early assignment (calls: before ex-dividend; puts: deep ITM),
  shares delivered/bought, and what covers it (shares, cash, the other leg, or "caps the loss but you'd be short/long
  shares"); pin risk at short strikes; auto-exercise of longs >= $0.01 ITM; prices assume no dividends.
- StrategyCard: collapsible "Early exercise, assignment and pin risk" (or "Early exercise and dividends" for
  long-only) under the scenarios on option cards. Cards cached before today just don't show it. Pricing/grading unchanged.
- Files: backend/v4/library.py, strategy.py, tests/test_v4.py (test_exercise_notes_american_style),
  frontend StrategyCard.jsx, docs/expert_review.md, docs/hq/status/builder.json.

## 2026-11-14 morning (daily polish walk)
- Moving now / story cards: the stock move label is "today" only for today's NY session; on weekends / before the
  open it reads "on Fri". movers._snapshots adds `change_day` (dailyBar date); frontend `sessionLabel` in MoversFeed.jsx.
- Noted, not changed: weekend Close Call AAPL $360 odds 42.7% vs YES cost 33% (trade-spread fit rejected as noisy);
  re-check on a weekday.
- Files: backend/v4/movers.py, backend/v4/tests/test_v4.py, frontend MoversFeed.jsx, StoryViewer.jsx,
  docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-14 (weekly brain upgrade routine)
- Ranker v2's "+ app (25%)" mixes are now tested mixed into the point-in-time app score (`pit_app`, new per-idea
  field in `research.load`), not the stored practice-call score that carries look-ahead. Stricter only: `_passes`,
  the bar (`old`), `live_check`, embargo and the engine are unchanged. Expect tonight's mix numbers to drop and the
  mixes to stop passing; that's intended (see docs/brain_upgrades.md). Don't switch mixes back to `c["app"]`.
- Files: backend/v4/research.py, backend/v4/tests/test_v4.py, docs/brain_upgrades.md, docs/hq/status/brain.json.

## 2026-11-14 morning (CTO scout routine)
- Idea 10 (return seasonality) preliminary result logged: raw +0.89% / t 2.73, risk-matched +0.54% / t 1.73; 5,279
  graded picks still lack `seas`, so re-check once enrich finishes.
- Idea 11 added: relative downside beta (Ang, Chen & Xing 2006). New feature `dbeta` (market.dbeta /
  dbeta_features, market.features, nn.make_features num — not MODEL_NUMERIC), research.FEATS + DIRECTIONAL, enrich
  backfill as of each pick's date, fixed rule "downside beta premium (z_dbeta)". Gate / fit_production untouched.
- Proposal (not built): "I'm wrong if..." one-line pre-mortem per call, in docs/feature_ideas.md.
- Files: backend/v4/market.py, nn.py, research.py, tests/test_v4.py (test_downside_beta_rule_and_enrich_backfill),
  docs/research_ideas.md, docs/feature_ideas.md, docs/hq/status/scout.json.

## 2026-11-14 morning, extra run (CTO scout routine; Murad asked for an extra run)
- Idea 12 added: short-term reversal, fixed rule "short-term reversal (-z_mom20)" on the stored mom20 (every graded
  pick has it; no new feature, no backfill). Gate / fit_production untouched.
- Proposal (not built): per-feature coverage in research runs + "provisional" flag, in docs/feature_ideas.md.
- Files: backend/v4/research.py, tests/test_v4.py (test_short_term_reversal_rule), docs/research_ideas.md,
  docs/feature_ideas.md, docs/hq/status/scout.json.

## 2026-11-14 (Builder routine): option cards show position Greeks
- Expert-review checklist item ("Greeks ... on option ideas must match the numbers on the card").
  `strategy.position_greeks(legs, spot, vol, as_of)`: delta (share-equivalents, stock legs included), gamma (per $1),
  theta ($/calendar day), vega ($ per 1 vol pt) for one unit, Black-Scholes at the same vol/time/RISK_FREE the card's
  premiums use. `build_trade` adds it as `trade.greeks` (None for shares). Pricing/grading unchanged.
- StrategyCard: collapsible "Greeks today · delta · theta" panel (2x2, plain words for each) between the scenarios and
  the exercise panel, scaled to the chosen contract count. Cards cached before today just don't show it.
- Test: test_position_greeks_match_card_pricing (finite differences of bs_price; straddle/condor/covered-call signs).
- Files: backend/v4/strategy.py, backend/v4/tests/test_v4.py, frontend/src/components/chat/StrategyCard.jsx,
  docs/expert_review.md, docs/hq/status/builder.json.

## 2026-11-14 late morning (daily polish walk)
- Practice options (and Close Call trades) open immediately even when the market is closed; that's unchanged, but
  `practice_options.open_trade` now returns `market_closed` and says so in its message, and the Portfolio closed-market
  banner now says only share trades wait for the open. If someone later makes options queue too, update both texts.
- Greeks panel (Builder's 57e5cc2): numbers verified; only wording changed for near-zero delta (no "−0 sh").
- Files: backend/v4/practice_options.py, backend/v4/tests/test_paper.py, frontend PracticePage.jsx, StrategyCard.jsx,
  docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-14 afternoon (Builder routine): "I'm wrong if..." pre-mortem on calls
- Built the 2026-11-14 proposal from docs/feature_ideas.md (size S-M). After the picks in chat, an optional
  "+ I'm wrong if..." row: one line (140 chars) and/or a price line on one shown pick (bullish: closes below, must be
  under the entry; bearish: closes above, must be over it). Also addable/editable later on My beliefs.
- `beliefs` gets `wrong_if`, `wrong_if_px`, `wrong_if_ticker` (additive migrations). `engine.set_wrong_if` (owner
  only, user calls only), `engine.tripwire` (first daily close strictly after the call date at/past the line; the live
  price only says where it is now), `my_beliefs` returns `wrong_if` per call. Route `POST /v4/wrong_if`.
- Information only: nothing trades, no alerts yet, not used by research or ranking. Seeded calls never get one.
- Files: backend/v4/db.py, engine.py, router.py, tests/test_v4.py (test_wrong_if_pre_mortem_..., fuzz list),
  frontend chat/WrongIf.jsx (new), ChatInterface.jsx, MyCallsPage.jsx, lib/api.js, docs/feature_ideas.md,
  docs/hq/status/builder.json.
- Deploy note: Render skips a push when the newest commit message contains the text "[skip render]" anywhere (even
  quoted, e.g. "previous push ended on a [skip render] commit"). Put a docs-only "[skip render]" commit in its own
  push, never on top of code. This run's code went live via a manual deploy of cf8f44b (backend + web); the two crons
  pick up the code on the next normal push (they don't use the new code).

## 2026-11-14 afternoon (daily polish walk)
- "I'm wrong if..." (Builder's ccb4e74): wording only. The pre-mortem prompt now uses the call's own horizon instead of
  a fixed "90 days" (WrongIf gets a `horizonDays` prop), and My beliefs says the line is checked "against each daily
  close after the day of your call" (matches engine.tripwire, which skips the call date's own close). No backend change.
- Files: frontend chat/WrongIf.jsx, ChatInterface.jsx, MyCallsPage.jsx, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-14 midday (health routine)
- All healthy. Render emailed that the workspace has used >70% of its 500 free build pipeline minutes this month.
  Every normal push to v4-polish builds backend + web (+ crons), so please batch code changes into fewer pushes and
  keep docs-only pushes on "[skip render]" (alone in their push, per the deploy note above). No code changed.
- Files: docs/agent_handoff.md, docs/hq/status/health.json.

## 2026-11-14 evening (Builder routine): "How sure are you?" calibration
- Built the 2026-11-11 proposal from docs/feature_ideas.md (size M). Under the picks in chat (above "I'm wrong if...")
  and on each call on My beliefs: one tap 55 / 65 / 75 / 90% that the idea beats the S&P 500 (bearish: does worse;
  volatile: moves more) at the check matching its horizon (`calibration.checkpoint_for`: first of 7/30/90/180/365 at or
  after horizon_days). Settable/changeable only until the day after the call (`calibration.can_set`), then locked.
- `beliefs.user_prob` (additive migration). `engine.set_user_prob` (owner only, user calls with a direction),
  route `POST /v4/user_prob`. `my_beliefs` adds `sure` per call and top-level `calibration` (`calibration.for_user`:
  uses grader's existing `belief_right` at that checkpoint; Brier, avg said vs hit rate, per-choice table).
  Shown with 10+ graded calls only (countdown before); buckets need 3+; verdict "about right" within 10 pts, else
  "leaning over/underconfident" unless the gap is beyond 2 binomial SEs. Claude's `conviction` untouched.
- Information only: not used by ranking or research; nothing trades. Glossary term "brier" added.
- Files: backend/v4/calibration.py (new), db.py, engine.py, router.py, tests/test_v4.py
  (test_how_sure_calibration_scores_stated_probabilities, fuzz list), frontend chat/HowSure.jsx (new),
  ChatInterface.jsx, MyCallsPage.jsx, ui/Term.jsx, lib/api.js, docs/feature_ideas.md, docs/hq/status/builder.json.

## 2026-11-14 late afternoon (daily polish walk)
- "I'm wrong if..." starter chip now follows the call's direction (bearish calls are wrong if they BEAT the S&P, volatile
  if they move less); WrongIf takes a `direction` prop (ChatInterface + MyCallsPage pass it). Window = min(30, horizon).
- "How sure" calibration countdown wording on My beliefs (no more "0 of 10 calls ... graded" after one tap); "Leaning"
  footnote only once scored. No backend change.
- Files: frontend chat/WrongIf.jsx, ChatInterface.jsx, MyCallsPage.jsx, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-14 night (Builder routine): honest t-stats (overlapping 90-day windows counted once)
- Built the 2026-11-13 proposal from docs/feature_ideas.md (size S). `research._se_overlap` + `_metrics` add
  `lift_t_nw`, `lift_adj_t_nw`, `dates`, `n_eff` to every research result (`_pick` now returns the belief date as a
  5th tuple element; old 4-tuples still work). `research.luck` adds `clear_nw`, `clear_adj_nw`, `app_clears_nw`,
  `app_clears_adj_nw`, `app_t`, `app_t_nw`, `app_dates`, `app_n_eff`; `/v4/brain` passes them through `skill.luck`.
  Brain page luck card: "Counting overlap honestly" line (days, ~independent calls, t both ways, how many clear).
- Reporting only: `_passes`, `fit_production`, MIN_T and the ranker don't read any of it. Numbers appear after the next
  research run (web start runs one ~2.5 min after deploy). Research routine: quote t_nw beside t (docs/research_ideas.md).
- Files: backend/v4/research.py, tests/test_v4.py (test_overlap_honest_t_counts_shared_market_paths_once),
  frontend BrainPage.jsx, docs/feature_ideas.md, docs/research_ideas.md, docs/brain_upgrades.md, docs/hq/status/builder.json.

## 2026-11-14 evening (daily polish walk)
- /brain wording only (BrainPage.jsx): the scorecard no longer calls the #1 gap "skill" while the overlap-honest luck
  check (skill.luck.app_clears_nw) says it doesn't clear; the plain "N of 41 cleared" sentence is labelled "Counting
  each call as independent"; feed line "Learned N beliefs from the news" (was "today's news", clashed with "78 today").
  No backend change, gates untouched.
- Files: frontend/src/components/BrainPage.jsx, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-14 evening (CTO scout routine)
- Research idea 13: idiosyncratic volatility (Ang, Hodrick, Xing & Zhang 2006). New feature `ivol` (1-month residual
  vol vs SPY, annualized; neutral 0.30 when short of data, also in `research.NEUTRAL`): `market.ivol` /
  `ivol_features`, `market.features`, `nn.make_features` (not MODEL_NUMERIC), `research.FEATS` + DIRECTIONAL,
  `research.enrich` backfills it as of each pick's own date. New fixed rule `low idiosyncratic vol (-z_ivol)` (luck bar
  now 42 tries). Ranker v2 gate untouched. Enrich will take a while to fill `ivol` on ~23k graded picks.
- Logged results: idea 12 (short-term reversal) final, +0.60% / t 1.96 (t_nw 1.32), doesn't clear; ideas 10, 11
  still filling in (3,779 picks missing `seas`, 6,779 missing `dbeta`).
- Proposal (docs/feature_ideas.md): "The outside view": show the base rate (how often calls of this direction and
  horizon beat the S&P, from our own grading) above the "How sure" buttons.
- Files: backend/v4/market.py, nn.py, research.py, tests/test_v4.py (test_idiosyncratic_vol_rule_and_enrich_backfill),
  docs/research_ideas.md, docs/feature_ideas.md, docs/hq/status/scout.json.

## 2026-11-14 night (Builder routine): "The outside view" base rate above "How sure"
- Built the 2026-11-14 evening proposal from docs/feature_ideas.md (size S-M). New `backend/v4/baserate.py`: one
  aggregate query, one result per graded CALL (MAX(belief_right) per belief and checkpoint, the same thing the "How
  sure" calibration card scores; not per pick), grouped by direction x checkpoint, stored in kv `baserate:v1`
  (~15 cells: n, right, beat, since/upto call dates). Refreshed by the grade phase of v4-grade-and-train and by the
  web start thread (`research.run_background`, only if older than a day). Never computed on a request.
  Public `GET /v4/base_rates` returns cells with n >= 100 only.
- Frontend `chat/HowSure.jsx`: "Base rate: of 2,651 graded bullish calls (made Nov 2023 to Jul 2026), 42% beat the
  S&P 500 at the 90-day check" above the buttons (chat and My beliefs) and under the locked "You said" line; if the
  user's pick is 10+ points off, it says so plainly. Glossary term "base rate". No default, no advice.
- Prod numbers today (call level): bullish 90d 41.8% (n 2,651), bearish 90d 59.2% (n 1,664); volatile cells are
  under 100 calls (except 7d n 47, also hidden) so volatile calls show no line.
- Information only: not used by ranking, research, gates or anything that trades.
- Files: backend/v4/baserate.py (new), grader.py, research.py, router.py, tests/test_v4.py
  (test_base_rate_outside_view_counts_each_call_once), frontend chat/HowSure.jsx, ui/Term.jsx, lib/api.js,
  docs/feature_ideas.md, docs/hq/status/builder.json.

## 2026-11-14 night (weekly brain upgrade, CTO routine)
- Ranker v2 training label now matches how the #1 is chosen: `research.load` computes `rel` / `rela` against the mean
  of the idea's own group in the belief (lead group = belief's own direction, or the off-direction group; one group /
  no stated direction = whole belief as before) and sets `train=False` on an idea alone in its group. `_xy` drops those
  rows; `_fit_ridge`, `_fit_gbm`, `_fit_mlp` and `fit_production` (ridge weights + refits) all go through `_xy`.
- Test scoring (`_pick`, `_top`), `_passes`, MIN_LIFT/MIN_T/MIN_T_ADJ, embargo, bar, mixes, `live_check`: unchanged.
- Evidence (prod SQL, 90-day): 2,341 off-direction ideas in 1,707 mixed beliefs (group offset sd 18%), 1,269 of them
  alone in their group. Win/revert criterion in docs/brain_upgrades.md. Research routine: compare learned-model lift
  in the next `research:ranker` run with tonight's 20:15 UTC run (ridge +0.93%, gbm +1.15%, net +1.26%).
- Files: backend/v4/research.py, backend/v4/tests/test_v4.py, docs/brain_upgrades.md, docs/hq/status/brain.json.

## 2026-11-14 night (daily polish walk)
- /brain wording only (BrainPage.jsx): ranker card no longer says "smarter" while its numbers trail the old way's stored
  (look-ahead) numbers; it shows `old_pit` (old way without look-ahead) beside them. Luck card names the old app score
  "the old way" while the ranker is active and adds the ranker's `oos.lift_t_nw`. Gate/ranking untouched.
- Files: frontend/src/components/BrainPage.jsx, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-14 late night (Builder routine): feature coverage, "provisional" rules
- Built the 2026-11-14 extra-run proposal from docs/feature_ideas.md (size S). `research.load` keeps two small
  bitmasks per candidate (`miss`: key never stored, `zero`: stored as exactly 0) over `COV_KEYS` (FEATS + REG_KEYS).
  `research.run` adds `coverage` ({n, share, zero_share} on the test-period calls), `provisional` ({rule: {feature:
  share}} for fixed rules reading a feature under `COVERAGE_OK` 0.99) and `low_coverage`. A rule's inputs are traced
  from its own lambda (`rule_inputs`), so nothing to keep in sync when the scout adds rules.
- `/v4/brain` passes `provisional` / `low_coverage` in `skill.luck`; Brain page luck card adds "Still filling in" (which
  ways read half-filled data, % filled, and how many of the cleared ones are among them). Hidden when nothing is short.
- Reporting only: `_passes`, `fit_production`, MIN_T, RISK_COVERAGE and the ranker don't read it. Numbers appear after
  the next research run. Research routine: read coverage from kv `research:ranker`, not a LIKE scan (docs/research_ideas.md).
- Files: backend/v4/research.py, brain.py, tests/test_v4.py (test_feature_coverage_marks_rules_on_half_filled_data_provisional),
  frontend BrainPage.jsx, docs/feature_ideas.md, docs/research_ideas.md, docs/hq/status/builder.json.

## 2026-11-15 overnight (daily polish walk)
- News move percents never show "-0.0%": new `signedPct` / `pctTone` / `TONE` in frontend/src/lib/figures.js, used by
  MoversFeed, StoryViewer, TrendingPage, ToolSelectorPage and ui/Page `pct` (same output otherwise; null still '—' in Page).
- Story mode: `movers._hook` rewrites a bare date hook ("November 30, 2026") to "On Nov 30", also on cached stories at
  read time; STORY_PROMPT says no bare dates; `_fallback_story` no longer takes digits from model names ("E195-E2").
- Files: frontend/src/lib/figures.js, figures.test.mjs, components/MoversFeed.jsx, StoryViewer.jsx, TrendingPage.jsx,
  ToolSelectorPage.jsx, ui/Page.jsx, backend/v4/movers.py, backend/v4/tests/test_v4.py, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-15 night (Builder routine): "Did that happen?" on the user's "I'm wrong if..." line
- Finishes the pre-mortem loop (docs/feature_ideas.md 2026-11-14, the part listed as not built). On My beliefs, a written
  "I'm wrong if..." line gets "Did that happen?" Yes / Partly / Not yet from 7 days after the call (`WRONG_IF_ASK_DAYS`,
  the first checkpoint); before that it says from which date. The answer can be changed; it's cleared when the user
  writes a different line (same line kept). Once answered, it's set beside the call result: "Yet the call is ahead of
  the S&P so far. Was your test wrong, or is the result luck?" / "Yet the call trails the S&P: something you didn't
  list is moving it." Price-line-only tests keep the automatic crossed / not-crossed check (no question).
- New columns `beliefs.wrong_if_answer`, `wrong_if_answered_at` (ADD COLUMN migrations), `engine.answer_wrong_if`,
  `POST /v4/wrong_if/answer` (owner only). Information only: not read by ranking, research, gates or anything that trades.
- Files: backend/v4/db.py, engine.py, router.py, tests/test_v4.py (test_wrong_if_did_that_happen_answer; the pre-mortem
  test now checks only the text/price/ticker keys), frontend components/MyCallsPage.jsx, lib/api.js,
  docs/feature_ideas.md, docs/hq/status/builder.json.

## 2026-11-15 early (daily polish walk)
- /brain wording only (BrainPage.jsx): with the ranker off (as after the 02:19 UTC retrain) the page no longer presents
  the stored #1 (look-ahead on practice calls, d856c72) as skill without saying so. Scorecard adds "A catch we found"
  from `skill.ranker.old_pit`; luck card and confidence card say "as stored". Shown whenever stored lift > old_pit lift,
  ranker active or not. Gates/ranking/numbers untouched. If research stops writing `old_pit`, the note just hides.
- WhatsNew.jsx: Nov 15, lines for How sure / base rate and I'm wrong if... / Did that happen?
- Files: frontend/src/components/BrainPage.jsx, WhatsNew.jsx, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-15 day (Builder routine): "You vs the outside view" on the calibration card
- My beliefs > How well-calibrated: once 10+ graded "How sure" calls have a base rate (baserate.py cell for the call's
  direction x checkpoint, n >= 100), the card shows the Brier the user would have scored by saying the base rate every
  time beside their own Brier on those same calls, with a paired 2-standard-error verdict (better / worse / about the
  same as the outside view). Says the base rates are today's record (they include results after the call).
- `calibration.outside_view`, `MIN_OUTSIDE`; `score()` takes optional 3rd element (base rate) per call, old 2-tuples
  unchanged; `for_user` reads `baserate.public()` (kv, no new scan; lazy import to avoid a cycle).
- Replaces the "brain's own High/Medium/Low" follow-up: `conviction` is "medium" on ~97% of calls, nothing to score.
- Information only: not read by ranking, research, gates or anything that trades.
- Files: backend/v4/calibration.py, backend/v4/tests/test_v4.py (test_calibration_compares_with_the_outside_view),
  frontend/src/components/MyCallsPage.jsx, docs/feature_ideas.md, docs/hq/status/builder.json.

## 2026-11-15 morning (daily polish walk)
- Story mode: `movers._sentences` ends story happened/why/twist on a whole sentence (also on cached stories at read
  time); `_hook` rejects a hook ending in "…". STORY_PROMPT asks for a neutral hook_line; feed PROMPT asks that each
  company's reason agree with its up/down direction (prompt text only, schema unchanged).
- /brain live activity: grouped rounds read "· N rounds over Xh".
- Files: backend/v4/movers.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-15 morning (Builder routine): Close Call record says "too early" instead of crowning a winner on one day
- The brain's Close Call record card said its odds were "closer to what happened than the market's" whenever its Brier
  was lower, on any sample. The first grades (Nov 19) are 11 questions all closing Nov 18, one shared market move, so
  it would have claimed a win on a coin flip. Now `yesno.record_verdict` clusters the Brier gap by expiration day (each
  closing day counts once) and says too early (< `MIN_VERDICT_DAYS` 5 days) / better / worse (past 2 clustered
  standard errors) / about even. The card also shows how often the market's odds alone picked the right side, next to
  the brain's lean, and how many closing days the questions cover.
- `scorecard()` adds `market_side_right`, `days`, `brier_gain`, `brier_se`, `verdict`, `min_days`; `brain_better` now
  means verdict == "better". Reporting only: `learn()`, its MIN_T gate and the lean are untouched.
- For the brain/research sessions (not changed here): `learn()`'s walk-forward t-stat treats questions that share an
  expiration as independent, so it overstates t the same way. Clustering it by expiration would tighten that gate; a
  deliberate change to write up in docs/brain_upgrades.md if someone takes it.
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py (test_yesno_record_verdict_counts_each_expiration_day_once),
  frontend/src/components/YesNoPage.jsx, docs/hq/status/builder.json.

## 2026-11-15 mid-morning (daily polish walk): news feed no longer shows the wrong company on quiet days
- `movers.build`: news-source tags (direction None, used only when Claude kept nothing) must be named in the
  headline/summary (`_names_company`); weekend tags like Dr. Martens -> DOCS (Doximity) were shown as "companies it
  touches".
- `movers.feed`: if a rebuild has no Claude hunches but the stored feed does (built < 3 days ago,
  `MP_MOVERS_KEEP_CURATED_SECONDS`), the curated feed stays; `checked_at` (new optional key) drives the TTL, `built_at`
  still drives "Updated Xm ago". Seeder's news_beliefs already skips used hunches, so no double learning.
- BrainPage.jsx: catch note says "on those same calls with the peek".
- Files: backend/v4/movers.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-15 afternoon (Builder routine): Close Call "Your answers" shows your record against the market's odds
- No HQ messages from Murad; every feature_ideas.md proposal is built, so this is a finishing touch on Close Call.
- Users never saw their own Close Call record, only a list of right/wrong pills; being right on a 90% favourite says
  little. Now, once 5+ answers are graded, "Your answers" opens with "You were right X of Y" beside "Market's odds
  expected Z" (sum of the odds the market gave each chosen side when they answered) and a verdict clustered by
  closing day like the brain's record: too early (< 5 days) / ahead / behind (past 2 clustered SEs) / within luck
  (with the ± band). Each row also says "Market gave YES 55% · closed $201.30".
- `yesno.my_record(views)`, `my_record_for(user_id)`, `MIN_MY_RECORD = 5`; `GET /v4/yesno/my_record?user_id=`
  (same pattern as /yesno/mine). Same question answered twice counts once. Information only: read by nothing else.
- Files: backend/v4/yesno.py, router.py, tests/test_v4.py (test_yesno_my_record_sets_right_against_the_market_odds),
  frontend/src/components/YesNoPage.jsx, lib/api.js, docs/hq/status/builder.json.

## 2026-11-15 afternoon (daily polish walk): honest MuLine vs ALMA wording, two grammar fixes
- /brain MuLine box: verdict sentence now built from the numbers (`trendlab.results`); a lag gap under 0.5 day says
  "about as fast as ALMA" instead of "sooner". `verdict_vs_alma` from trendlab.py is unchanged (still picks the "Still
  tuning" suffix). Luck card "1 of 42 ways does".
- yesno `_reasons`: "(for 1 trading day)" singular.
- Files: frontend/src/components/BrainPage.jsx, backend/v4/yesno.py, backend/v4/tests/test_v4.py, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-15 evening (Builder routine): /brain says how many grades are real time
- No HQ messages from Murad; every feature_ideas.md proposal is built, so this is a finishing touch on the Brain page.
- "Graded by the market 113,960" and the "Growing every day" chart read as live market grading. Live DB: 108,486 of
  those grades are practice calls (seed_backfill, made on past dates, graded at once at 7/30/90/180/365 days); only
  5,474 come from calls made in real time. The shared-scale chart also drew "beliefs learned" as a flat line.
- `brain._growth` adds a running `live` total per day; `counts.graded_live` (both use the forward test's definition,
  source <> 'seed_backfill'). Tile sub-line: "5,474 in real time, the rest practice". Chart is now two small charts
  with their own scales and latest values (beliefs learned, graded in real time) plus one line saying what the other
  grades are. Old snapshots without `live` still render (falls back to picks graded).
- Information only: no ranking, research, gate or grading logic touched.
- Files: backend/v4/brain.py, backend/v4/tests/test_v4.py (test_brain_counts_say_how_many_grades_are_real_time),
  frontend/src/components/BrainPage.jsx, docs/hq/status/builder.json.

## 2026-11-15 late morning (daily polish walk): volatile picks no longer drawn as ▲; honest growth labels
- /brain "Just learned" drew volatile picks (big move either way) as ▲; now ↕ with a short legend.
- /brain growth sparks: "+6,567 in 30 days" equalled the total (data starts Oct 28); now "all since <first day>" when
  the count started inside the window.
- Frontend only. Files: frontend/src/components/BrainPage.jsx, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-15 late evening (Builder routine): strategist scoreboard shows the app's own #1 and a random idea
- No HQ messages from Murad; every feature_ideas.md proposal is built, so this is a finishing touch on /brain.
- "Survival of the smartest" said the leader beat the S&P by +2.6 pts with no yardstick. Live DB on its 300-call
  window: the app's own #1 did +2.6 pts (beat 51%), a random idea from the same lead group +0.3 pts, and all 300 are
  practice calls (seed_backfill). So the leader only ties the app's pick, and it was selected on those calls.
- `lineages.window_baselines(beliefs)` -> {app, avg_idea, practice, n}; stored by `evolve()` in kv_cache
  `lineage_window` (also on the too-early path), read by `_snapshot()` as `window` (None until the next evolve, Mon
  after the close; the card hides until then). `_graded_beliefs` now also reads b.source (`practice` flag).
- BrainLineages.jsx: leader card gets "App's own #1, same calls / A random idea, same calls" plus a plain verdict
  (ahead / about the same / behind) and why the live record is the fair test; the list gets an unnumbered "The app's
  own #1" reference row in fitness order; live records add "app's #1: +x pts" on the same calls.
- Information only: fitness, selection, culling, champion rule and LIVE_MIN/LIVE_MARGIN unchanged. Docstring fix:
  checkpoint is ninety days, not thirty.
- Files: backend/v4/lineages.py, backend/v4/tests/test_v4.py
  (test_lineages_scoreboard_shows_the_apps_own_pick_and_the_average_idea), frontend/src/components/BrainLineages.jsx,
  docs/hq/status/builder.json.

## 2026-11-15 evening (daily polish walk): options footnote wording; What's new mentions the Close Call record
- Options card footnote no longer reads "(no live option quotes) (24%)": now "(24% a year), since there were no live
  option quotes". What's new adds the Close Call "Your answers" record line.
- Frontend only. Files: frontend/src/components/chat/StrategyCard.jsx, frontend/src/components/WhatsNew.jsx,
  docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-15 night (CTO scout routine): idea 14 long-term reversal; ideas 10, 11, 13 final; spread-of-outcomes proposal
- No HQ messages from Murad.
- Research: new feature `ltr` (return from ~3 years to ~1 year before the pick's date, latest year skipped; De Bondt &
  Thaler 1985) and fixed rule `long-term reversal (-z_ltr)` (directional). `market.ltr` / `ltr_features`, in
  `market.features`, `nn.make_features` num (NOT MODEL_NUMERIC), `research.FEATS` + `DIRECTIONAL`; `research.enrich`
  backfills it as of each pick's own date (its SQL filter and `_need` now also check `"ltr"`). Luck bar goes to 43
  tries. Ranker v2 gate / activation untouched.
- docs/research_ideas.md: final results for 10 (seasonality, weak), 11 (downside beta, small steady positive, under the
  bar) and 13 (low IVOL: clearly *worse* raw, t -4.00 / t_nw -1.58) from the 2026-11-15 17:16 UTC run.
- docs/feature_ideas.md: proposal "How wide it can go" (p10/p50/p90 of 90-day excess return per direction in
  `baserate:v1`, one line in HowSure). Not built.
- Files: backend/v4/market.py, nn.py, research.py, tests/test_v4.py (test_long_term_reversal_rule_and_enrich_backfill),
  docs/research_ideas.md, docs/feature_ideas.md, docs/hq/status/scout.json.

## 2026-11-15 night (Builder routine): "How wide it can go" under the base rate
- No HQ messages from Murad. Built the scout's 2026-11-15 proposal (feature_ideas.md), the only one still "proposed".
- `baserate.compute()` adds p10 / p50 / p90 to each `baserate:v1` cell: how far each *call* finished from the S&P in
  the direction called (theme = `outcomes.bench_ret` of the call's own-direction picks vs `spy_ret`; same rule as
  grader belief_right, whose sign it is). Call-level, not pick-level as the proposal sketched, so the spread and the
  "42% beat" line describe the same calls (live: 0 sign mismatches). Python percentiles = percentile_cont; a cell
  gets no spread unless every counted call has a number. Same MIN_N, same daily refresh, never on a request.
- HowSure.jsx `SpreadLine` (inside BaseRateLine, so chat and My calls both get it): small bar with the S&P mark in
  the middle, plus "the worst 1 in 10 ended 12 pts or more the wrong way; the best 1 in 10 ended 12 pts or more the
  right way. The middle call ended 2 pts the wrong way." Wording holds when the whole range is on one side.
- Shows after the next grading run (or the web service's stale refresh) rewrites `baserate:v1`; old cells without
  p10/p50/p90 just don't show the bar. Information only: no ranking, research, gate or grading change.
- Files: backend/v4/baserate.py, backend/v4/tests/test_v4.py (test_base_rate_spread_says_how_far_calls_landed),
  frontend/src/components/chat/HowSure.jsx, docs/feature_ideas.md, docs/hq/status/builder.json.

## 2026-11-15 late night (weekly brain upgrade): confidence badge without look-ahead, cuts from live calls
- No HQ messages from Murad. Last week's group-label change held up (ridge/gbm/net each +0.1–0.2 pt out of sample).
- Ranker off: the #1's confidence label now uses the thirds of "app, no look-ahead" (`research.run` records its
  spreads) and, with ≥150 real-time calls in the last 7 days, cuts at their terciles (`research._app_confidence`,
  `_live_spreads`, `CONF_LIVE_DAYS`, `CONF_LIVE_MIN`). Was 56% "high" live under the old practice cuts.
  `ranker:v2.confidence` gains `basis`, `cuts_from`, `cuts_n`, `cuts_test`. No ordering/gate change.
- Files: backend/v4/research.py, backend/v4/tests/test_v4.py, docs/brain_upgrades.md, docs/hq/status/brain.json.
- Still open for Murad: whether the gate's bar moves to the point-in-time app (see brain_upgrades.md).

## 2026-11-15 night (daily polish walk): confidence badge hidden until its test backs it; foreign news tags
- The #1's "High/Medium/Low confidence" badge is now shown only while `research.confidence_backed(conf)` (top third's
  lift > bottom third's). Live no-look-ahead thirds are high +0.2 / mid +0.9 / low +0.5 pts, so it's hidden today.
  The label is still stored in `features.rv2_conf` (forward test by_confidence unchanged). Brain routine: if you
  change how confidence is judged, keep this rule or replace it with something equally honest; don't just re-show it.
- /brain confidence card: no more "uses the score as stored, which peeked" on the no-look-ahead basis; honest verdict
  line when the badge is hidden.
- movers.build: a tagged ticker must name the company in the story even when Claude picked it (Centrica's "CNA" was
  CNA Financial). Prompt line added.
- Files: backend/v4/research.py, engine.py, movers.py, tests/test_v4.py, frontend/src/components/BrainPage.jsx,
  docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-15 late night (Builder routine): Brain family tree fits a phone
- No HQ messages from Murad; no "proposed" items left in feature_ideas.md.
- /brain "Survival of the smartest" family tree: at 390px it showed only Gen 1–5 of 11 and cut "Gen 6" in half; the
  newest generations, where the leaders live (Gen 9b, 11b), were off the right edge in a hidden side scroll. The tree
  now measures its card (ResizeObserver) and spaces the generations to fit (64px max, 24px min per column); labels go
  to every other generation (always the newest) when columns are under 34px. Only past ~14 generations on a phone does
  it scroll, and then it opens at the newest end. Checked at 375/390/768 against the live /v4/brain data: all 11
  generations and all 8 alive strategists visible, no page overflow.
- Frontend only. Files: frontend/src/components/BrainLineages.jsx, docs/hq/status/builder.json.

## 2026-11-16 early (daily polish walk): option card max gain read exactly
- No HQ messages from Murad. Frontend `lib/payoff.js` `summarize` / `capitalPerUnit` now evaluate the expiry payoff at
  $0, every strike and a far point (same method as backend `library.economics`) instead of a grid starting at 1% of the
  price. A long put's max gain was short by 1% of the price x 100 ($3,661 vs $3,699 on a $39 put at $2.01).
- Files: frontend/src/lib/payoff.js, frontend/src/lib/payoff.test.mjs, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-16 (Builder routine): a news hunch and its opposite no longer bet the same stock the same way
- No HQ messages from Murad; no "proposed" items in feature_ideas.md.
- Found on /brain "Just learned": "I don't think big retailers' sales recovery will stall" -> TGT down, same as the
  hunch. Live count: in 385 of 939 hunch/opposite pairs since Oct 30, at least one stock was bet the same way on both
  sides (844 picks), so the brain was partly taught that both sides of a story mean the same thing.
- seeder.run: an opposite ("I don't think <hunch>", `seeder.OPPOSITE`) now runs after its hunch and passes the hunch's
  picks as `avoid` to `engine.process_belief`, which drops any candidate bet the same way (bullish/bearish only;
  volatile/neutral untouched) before scoring. Nothing left -> `same_side_as_original`, not stored
  (`results["same_side_skipped"]`). No extra Claude calls.
- interpreter SYSTEM_PROMPT: one line so "I don't think X" / "X won't happen" (from users too) is read as a bet on the
  opposite of X.
- Not changed: the 844 old same-side picks stay in the data (no deletes). Brain routine: if you want them out of
  training, that's your call; they're seed_news beliefs starting "I don't think " whose pick repeats the hunch's
  ticker+direction. No gate, ranking or grading change.
- Files: backend/v4/engine.py, seeder.py, interpreter.py, tests/test_v4.py
  (test_news_opposite_never_bets_a_stock_the_same_way_as_its_hunch), docs/hq/status/builder.json.

## 2026-11-16 morning (daily polish walk): honest retrain list; share counts match the amount
- No HQ messages from Murad. Frontend only.
- /brain versions list: retrains on unchanged data (same n_train/n_test as the one before) now say "same data as the
  one before", with one line explaining no new 90-day results arrive until real-time calls reach 90 days (date from
  `forward.since` + 91). Activity feed: "Retrained the brain". When n_train grows again the old text comes back by
  itself. No backend, gate or training change.
- `payoff.shareCount`: share counts show 2 decimals under 100 shares (card said "17 shares" next to "about 17.24").
- Files: frontend/src/components/BrainPage.jsx, frontend/src/lib/payoff.js, frontend/src/lib/payoff.test.mjs,
  docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-16 (Builder routine): My beliefs shows where your graded call landed among calls like it
- No HQ messages from Murad; no "proposed" items left. Built the unbuilt half of "How wide it can go" (feature_ideas).
- `engine.my_beliefs` items gain `graded`: the call's newest graded checkpoint `{checkpoint_days, vs_spy, right, on}`,
  from `engine._graded_checks` (one grouped query, same call-level number as `baserate._spreads`: theme vs the S&P in
  the direction called; its sign is belief_right, checked on the live DB). 31 user calls have a 7-day grade today;
  none has reached its own checkpoint yet.
- My beliefs card: "Graded at the 7-day check (Nov 5): your idea finished 9 pts the right way vs the S&P", the spread
  bar for that same direction x check with a "You" mark, where it sits (worst 1 in 10 / blue band / best 1 in 10) and
  the lesson that one call says little about skill; "An early read" when the check is before the call's own one.
  `HowSure.jsx` gains `SpreadBar` (shared with `SpreadLine`), `spotWord`, `YourSpot`.
- Information only: no gate, ranking, grading or research change. Checked at 375/390 with mocked data: no overflow.
- Files: backend/v4/engine.py, backend/v4/tests/test_v4.py, frontend/src/components/chat/HowSure.jsx,
  frontend/src/components/MyCallsPage.jsx, docs/feature_ideas.md, docs/hq/status/builder.json.

## 2026-11-16 midday (daily polish walk): "Protect what I own" says what an owner actually pays
- No HQ messages from Murad. No sizing, gate, ranking or grading change.
- Protective Put / Collar cards (goal "protect" = insurance for shares I have) said "Doesn't fit $5,000 ... No version
  of this idea fits" because the price includes buying 100 shares. Now: badge "With the 100 shares included, 1 contract
  costs more than your $X", backend note says the price includes the shares and an owner only adds the options, and the
  plain-English deal adds "Already own 100 NVDA shares? Then only the put is new money: about $210" (collar: net).
- Option legs show cents ($177.50 strike, $2.10).
- Files: backend/v4/strategy.py (fit_budget note), backend/v4/tests/test_v4.py, frontend/src/lib/payoff.js
  (`ownedNote`), frontend/src/lib/payoff.test.mjs, frontend/src/components/chat/StrategyCard.jsx, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-16 (Builder routine): Close Call YES / NO cost now matches the market's odds (each strike at its own IV)
- No HQ messages from Murad; no "proposed" items in feature_ideas.md.
- Found on live /v4/yesno/quote: AAPL $360 Dec 18 showed market odds 50.2% (skew included) but YES cost $204 of $500
  (41%), price_source "line_iv". Cause: one flat vol can't reprice a skewed vertical spread (its flat-vol value at
  any vol tops out near $212, the skewed mid is ~$230), so `spread_vol` found no root / was rejected by the 20% guard
  and YES fell back to the line IV. A user (or a professor) sees 50% odds to win $296 for $204: looks like free money.
- `yesno.leg_vols` / `strike_vol`: each of k1, k2 at the IV that reprices its own listed call mid ("sticky strike"),
  same 20% guard per strike, not used when the odds are flagged stale. YES and NO legs carry `vol`; `price_source`
  "strikes", quote returns `leg_vols`. YES = the listed spread mid; NO at the same two vols, so YES + NO = the
  discounted payout. Fallbacks unchanged (spread_vol -> line IV -> estimate).
- practice_options: legs may carry their own `vol` (used by `unit_value` / `_priced`, so marks after opening use the
  same vols, no jump). Only kept when server code passes `keep_leg_vols=True` (Close Call); a request can't set it.
  Other practice trades unchanged.
- `digital_from_spread(calls, level, years)`: divides the spread price by exp(-r t) (a spread pays at expiration).
  ~0.2-0.4 pts on odds; grading/learning unchanged.
- YesNoPage note: "Practice trades cost the listed mid prices of the $360 and $365 options, each at its own implied
  volatility (24.1% and 23.5%, so skew is included)". No real-money change (`real_money_order` untouched).
- Files: backend/v4/yesno.py, backend/v4/practice_options.py, backend/v4/tests/test_v4.py
  (test_yesno_skewed_chain_prices_each_strike_at_its_own_vol), frontend/src/components/YesNoPage.jsx,
  docs/hq/status/builder.json.

## 2026-11-16 afternoon (daily polish walk): Baskets never serve a canned 60/40 with a promised return
- No HQ messages from Murad. No gate, ranking, grading or real-money change.
- `/basket/generate_basket` used to answer any failure with VTI 60 / BND 40 and "5-7% annually" whatever the goal. It now
  returns 500 with a plain "couldn't build a basket, nothing was made up, try again" (the page shows it). v4
  `basket.generate` raises ValueError when no valid holding survives (empty goal still gets the labelled stand-in).
- BrainPage wording: "Training runs" instead of "Brains trained" (matches the same-data retrain note).
- Render builds are failing (out of build minutes since 08:07 UTC): this commit, like 0dbdbfc, won't be live until
  Murad restores builds. Don't re-push to "kick" it.
- Files: backend/routes/basket_router.py, backend/v4/basket.py, backend/v4/tests/test_v4.py,
  frontend/src/components/BrainPage.jsx, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-16 late morning (Builder routine): Close Call odds read at the line itself, not at a spread's middle
- No HQ messages from Murad; no "proposed" items in feature_ideas.md. Render builds still failing (out of build
  minutes, flagged to Murad by the 08:03 run): this commit queues behind 0dbdbfc / 4db4cda and won't be live until
  builds resume. Don't re-push to kick it.
- Found on live /v4/yesno/quote: NVDA "close above $150" (Nov 20) said "From the $149/$152.5 call spread". A call
  spread prices the chance of finishing above the middle of its strikes ($150.75 here), not above the line, so uneven
  strikes (or a typed line between strikes) gave the odds of a different question (~1-2 pts off on NVDA).
- `yesno.digital_from_spread` now reads the chance at the line: the two neighbouring strike pairs whose middles sit
  either side of it, in a straight line between them (even strikes around a listed line = the same central spread
  as before). One pair only -> that spread, as before. Returns (p, lo, hi, strikes used). `odds_label`: "the
  $149/$150/$152.5 call prices, read at the $150 line (skew included)" or "the $157.5/$162.5 call spread (skew
  included)". Stale check, YES/NO pricing, grading and learning unchanged.
- Tests: test_yesno_digital_from_call_spread updated, test_yesno_odds_at_the_line_with_uneven_strikes (smooth
  lognormal chain: new reading within 0.2 pts of P(close > $150), the old one wasn't). 178 passed.
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, docs/hq/status/builder.json.

## 2026-11-16 midday (daily polish walk): two-breakeven cards show both numbers; stay-out cards drop the budget line
- No HQ messages from Murad. No gate, ranking, grading or real-money change. Frontend + dev script only.
- StrategyCard `Stat` takes an array (one line each); Breakeven passes both, so "$164.04 / $205.96" no longer truncates
  to "$164.04..." at 375px. Sell / Avoid cards hide "Fits your $X" and the generic "what you said matters most" reason.
- scripts/dev_offline_server.py fake interpreter now also returns volatile / neutral beliefs (local walking only).
- For the build chat (not touched): neutral (range-bound) beliefs get bullish picks, because candidate directions are
  only bullish/bearish/volatile (`interpreter._sanitize`), so Iron Condor / Iron Butterfly are never offered and a
  "sideways" call can get a Bull Call Spread. Needs a grading rule for neutral first. Details in docs/polish_log.md.
- Render builds still failing (out of build minutes): this queues behind ee64847. Don't re-push to kick it.
- Files: frontend/src/components/chat/StrategyCard.jsx, scripts/dev_offline_server.py, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-16 afternoon (Builder routine): Brain page market regime says what it is, with the numbers
- No HQ messages from Murad; no "proposed" items in feature_ideas.md. Render builds still failing (out of build
  minutes): this commit queues behind 083cc8b and won't be live until builds resume. Don't re-push to kick it.
- Found on live /brain: "Market regime: Calm. Markets are quiet or moving sideways." while the S&P 500's 20-day
  volatility was 22.1% a year (above its usual level) and it was 3.2% off its high. "calm" is just the bucket for
  anything that isn't a steady climb or turbulent; a finance professor would read "quiet" as wrong.
- Backend: `market.regime_state` thresholds are now named constants (REG_CRISIS_VOL/DD, REG_TREND_R60/VOL, same
  values, same classification; regime features and research untouched). The state also returns `date` (last S&P
  close used) and `rule` (`market.REGIME_RULE`, written from those constants).
- BrainPage: "calm" shows as "In between: not a steady climb and not turbulent", "trending" as "Steady climb"; under the
  label the three S&P 500 numbers (3 months, off 1-year high, 20-day volatility) and the rule. Works with the old
  backend shape too (numbers/rule just hidden).
- Test: test_regime_label_says_why_with_the_numbers. 179 passed.
- Files: backend/v4/market.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx,
  docs/hq/status/builder.json.

## 2026-11-16 late (daily polish walk): "I doubt it" beliefs read as English; news opposites say "will", not "may"
- No HQ messages from Murad. No gate, ranking, grading or real-money change.
- Frontend: lib/text.js `oppositeOf(hunch)` replaces MoversFeed's blind first-letter lower-casing ("I don't think aI
  firms...", "nvidia", "europe's"); may/might/could -> will; negative hunches -> "I doubt that ...". Test
  src/lib/text.test.mjs, added to `npm test`. auth.biometricName: "a passkey" off Windows.
- seeder: `_opposite()` (same rule), legacy-wording opposites not re-learned, pairing for `avoid` still works with the
  new wording (originals keyed by both forms). Test test_news_opposite_reads_as_english_and_still_pairs_with_its_hunch.
- For the Builder: same-side opposites with *different* stocks still slip past the avoid guard (Bitcoin selloff
  opposite -> QQQ bearish). Details in docs/polish_log.md. Not touched.
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: frontend/src/lib/text.js, text.test.mjs, auth.js, components/MoversFeed.jsx, package.json,
  backend/v4/seeder.py, backend/v4/tests/test_v4.py, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-16 evening (Builder routine): news opposites with no side of their own are no longer learned
- No HQ messages from Murad; no "proposed" items in feature_ideas.md. Picked up the polish walk's note for the
  Builder: the same-side guard only dropped a stock bet the same way on both sides, so "I don't think Bitcoin's
  selloff may signal a longer crypto downturn" was still learned as QQQ down.
- `engine.drop_same_side(cands, avoid)` (used by process_belief when `avoid` is passed, i.e. news opposites only):
  rule 1 as before (same stock, same way: dropped); rule 2: if what's left bets only the hunch's main direction
  (majority of its up/down picks; no rule on a tie), those picks go too. Any pick the other way keeps the whole set,
  so winners-vs-losers opposites ("AI firms won't pay publishers" -> publishers down, META up) stay. Volatile picks
  never dropped. Checked by hand on 60 live pairs: catches the crypto->QQQ, "young renters" and "oil will struggle"
  misreads, no false drops seen. User beliefs untouched (no avoid); gates, grading, ranking unchanged.
- Test: test_opposite_view_with_no_side_of_its_own_is_dropped. 181 passed; vite build passes.
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/engine.py, backend/v4/tests/test_v4.py, docs/hq/status/builder.json.

## 2026-11-16 evening (daily polish walk): option rows show strikes; no made-up "what matters most"
- No HQ messages from Murad. No gate, ranking, grading or real-money change.
- Portfolio options rows list their legs (strikes) under the strategy name.
- strategy.select: when the user gave no goal (Shares, or "Any options strategy"), the reason no longer says "Best fit
  for what you said matters most". Same structures picked; only the text changed.
- Shares paper-trade confirmation links to Portfolio (was My beliefs).
- For the build chat (not touched, M): sold positions leave no record (no closed-trades list). Details in polish_log.
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/strategy.py, backend/v4/tests/test_v4.py, frontend/src/components/PracticePage.jsx,
  frontend/src/components/chat/StrategyCard.jsx, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-16 evening (CTO scout routine): idea 15 price delay; proposal "ticker identity check" (PARA is a reused ticker)
- No HQ messages from Murad. No gate, ranker v2 activation, grading or real-money change.
- Part A: idea 15, price delay (Hou & Moskowitz 2005): `market.delay` / `delay_features` (1 - R2 same-week SPY / R2
  with 4 lagged weeks, weekly returns over 52 weeks, as of each pick's date; neutral 0.20), in `market.features`,
  `nn.make_features` (not MODEL_NUMERIC), `research.FEATS` + DIRECTIONAL + NEUTRAL, `research.enrich` backfill, rule
  `price delay premium (z_delay)`. Test test_price_delay_rule_and_enrich_backfill. Idea 14 (long-term reversal)
  recorded as preliminary (ltr coverage 77%).
- Part B, for the Builder (proposed in docs/feature_ideas.md): PARA picks are **Parabolic Technologies**, not Paramount
  (ticker reused after the Aug 2025 Skydance merger). 30 picks, 25 backfill calls from Dec 2023 with entry prices up to
  $215,128 and 16 fake -60% to -86% grades. `engine.process_belief` never compares Claude's company name with Alpaca's.
  Not fixed here (proposal only); excluding rows from research is a deliberate step for brain_upgrades.md.
- Render builds still failing (out of build minutes): this queues too, so idea 15 is not live and research won't
  rerun with it until builds resume. Don't re-push to kick it.
- Files: backend/v4/market.py, nn.py, research.py, tests/test_v4.py, docs/research_ideas.md, docs/feature_ideas.md,
  docs/hq/status/scout.json.

## 2026-11-16 night (Builder routine): ticker identity check (a ticker must still be the company the idea names)
- No HQ messages from Murad. Built the CTO scout's "proposed" ticker identity check (first part).
- Problem: the engine trusted the ticker alone. Of 1,439 live (ticker, Claude's name, Alpaca's name) pairs from the
  interpretation cache, ~25 were different companies: PARA = Parabolic Technologies (not Paramount), PMI = Picard
  Medical (not Philip Morris), BYD = Boyd Gaming, CAL = Caleres (not Cal-Maine), CATL = a SPAC, INTM = a muni ETF, etc.
  Users saw and were graded on the wrong company.
- New `backend/v4/names.py` `same_company()`: word overlap after dropping legal/listing/fund-issuer words, word
  prefixes, initials (ADP, UEC, TSMC, GE, Wabtec), short rename list (SLB, MARA, MSTR, IREN, GOOGL, QQQ...). Empty name
  passes. On all 1,439 pairs: drops the misreads, no false drops found (misses: Yum China -> YUM, Barrick -> GOLD).
- `engine.process_belief`: mismatched candidates skipped (like an untradable ticker), listed in `name_mismatch` on the
  result and printed; backfill candidates whose call-date price is >200x off today's are skipped too
  (`_plausible_history`, PARA's $215k Dec 2023 rows); each pick's features keep `claude_name`. seeder counts
  `name_mismatch`. Gates, grading, ranking unchanged. Old PARA rows untouched: auditing/excluding them from research
  is a separate deliberate step (brain_upgrades.md).
- Test: test_ticker_must_still_be_the_company_the_idea_names.
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/names.py, engine.py, seeder.py, tests/test_v4.py, docs/feature_ideas.md, docs/hq/status/builder.json.

## 2026-11-16 night (weekly brain upgrade): a ranker that passed alone goes live alone (weight 1.0, as tested)
- No HQ messages from Murad; no "proposed" brain items in feature_ideas.md.
- Ranker v2 switched on this morning (refit 07:00 UTC, `mlp_adj` alone, through the unchanged gate), but the engine
  blended it 50/50 with the app score, a setup never tested (27% of today's real-time #1s were not the model's #1).
- `research.WEIGHT` 0.5 -> 1.0; `engine.process_belief`: non-mix ranker uses `research.WEIGHT`, mix uses its stored
  tested weight. No gate, embargo, live_check, grading or real-money change. Don't put a hand-picked blend weight back
  without testing that exact blend in research.run.
- Tests: test_ranker_that_passed_alone_goes_live_alone, test_engine_orders_by_a_lone_ranker_exactly_as_tested. 186 passed.
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/research.py, engine.py, tests/test_v4.py, docs/brain_upgrades.md, docs/hq/status/brain.json.

## 2026-11-16 night (daily polish walk): Brain page says the #1 model runs alone, shows its risk-matched luck score
- No HQ messages from Murad. No gate, ranking, grading or real-money change.
- brain._skill ranker now carries `mix`; BrainPage luck check says "today's #1 now comes from the retrained model"
  unless it's a mix (matches the brain upgrade's weight 1.0); overlap paragraph adds the risk-matched counted-overlap t
  (4.3, clears the 3.25 bar); "It grades itself" notes the nightly brain and the #1 pick model are separate.
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/brain.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-16 late night (Builder routine): Closed trades on Portfolio (a sale leaves a record)
- No HQ messages from Murad; no "proposed" items in feature_ideas.md. Built the polish walk's open item: a sold
  position disappeared with no record ("Nothing here yet", the gain only hidden inside Account value).
- New `closed_trades` table in the practice DB (`paper_trading._init_database`); `_close_at` writes one row per sale
  (now or queued for the open) with qty, cost basis, exit price, gain, belief, opened/closed times.
  `PaperTradingEngine.closed_trades()` reads them, plus older SELL transactions with "cost not recorded" (no made-up gain).
- `practice_options.closed()`: closed / expired options with set aside, cash back and gain (= cash back - set aside,
  the same numbers that moved the account). Expired trades now get closed_at = expiration day 16:00 (was "now").
- `/api/paper-trading/portfolio/{uid}` adds `closed_trades` (both kinds, newest first, max 50).
- PracticePage: "Closed trades" list (5, then "Show all"), "Locked in: +$X on N trades", Sold / Closed / Expired date
  chips, options legs; empty state says "No open positions" when there are past trades. Numbers checked locally at
  375/390: the gains add up to the account's total gain.
- Not changed (noticed): practice shorts' cash accounting (open adds no cash, cover adds the proceeds) is off, but no
  screen opens a practice short today. Money math, grading, gates untouched.
- Test: test_sold_positions_leave_a_closed_trade_record (test_paper.py).
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/paper_trading.py, backend/v4/practice_options.py, backend/routes/paper_trading_router.py,
  backend/v4/tests/test_paper.py, frontend/src/components/PracticePage.jsx, docs/hq/status/builder.json.

## 2026-11-17 early (daily polish walk): Closed trades show the right day; "buying shares" wording
- No HQ messages from Murad. No gate, ranking, grading or real-money change.
- practice_options times now stored in UTC with offset (were bare server time, so a 7:30 PM ET close showed the next
  day); expiry settles at 4pm New York with offset; older bare rows read correctly; "Expired" only for a settle at or
  after 4pm NY on expiration day. `_closed_trades` sends every closed_at with an offset. Keep offsets on new timestamps.
- StrategyCard bearish shares hint: "Buying shares only makes money if the price rises."
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/practice_options.py, backend/routes/paper_trading_router.py, backend/v4/tests/test_paper.py,
  frontend/src/components/chat/StrategyCard.jsx, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-17 (Builder routine): Portfolio "You vs the S&P 500" (same money, same days)
- No HQ messages from Murad; no "proposed" items left in feature_ideas.md. Picked a finishing touch for Prof Brown:
  the practice account showed gains with no benchmark.
- New `backend/v4/benchmark.py`: each measured trade's money (shares qty x avg price; options set aside) x SPY's move
  from its last daily close before the trade opened (New York time, a close counts from 4pm) to its last close before
  it closed, or SPY's live price if still open. Shorts, older sales with no cost, and trades with no SPY history are
  left out; no live SPY price -> open trades left out (never a stale price). Daily closes only, no look-ahead.
- `/api/paper-trading/portfolio/{uid}` adds `benchmark` (trades, money, gain, spy_gain, ahead, beat, open,
  skipped_short, since) and `vs_spy` on each position / options trade / closed trade; wrapped in try (None on failure).
- PracticePage: "You vs the S&P 500" card under Account value + one "Same money in the S&P 500: ... ahead/behind by"
  line on each open and closed trade, with the method in a footnote. Checked at 375/390 with a mocked portfolio: the
  per-trade S&P gains add up to the card, the trade gains add up to the account's total gain; no overflow.
- Information only: no ranking, research, gate, grading or real-money change.
- Test: backend/v4/tests/test_benchmark.py (3 tests). Backend 192 passed, vite build passes.
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/benchmark.py, backend/routes/paper_trading_router.py, backend/v4/tests/test_benchmark.py,
  frontend/src/components/PracticePage.jsx, docs/hq/status/builder.json.

## 2026-11-17 morning (daily polish walk): S&P comparison starts at the trade's moment, not the previous close
- No HQ messages from Murad. Information only: no ranking, research, gate, grading or real-money change.
- benchmark.py: inside market hours, SPY's price comes from its 5-minute bar at the trade's open/close moment
  (`_price_at_factory`, `level_at`); outside hours or on any fetch failure, the old last-close rule. A brand-new 2pm
  trade no longer shows "behind the S&P" by the morning's move. `attach(..., at=)` is injectable; tests pass
  `at=lambda ny: None` to stay offline.
- paper_trading `_fill_queued`: fill time uses `market._session_open_dt(day)` (was hard-coded -04:00, 8:30 AM in winter).
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/benchmark.py, backend/paper_trading.py, backend/v4/tests/test_benchmark.py,
  frontend/src/components/PracticePage.jsx, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-17 (Builder routine): Expired practice options settle at the expiration-day close
- No HQ messages from Murad; no "proposed" items in feature_ideas.md. Found a money-math bug (rule a): an expired
  practice options trade (every Close Call practice trade) settled at whatever the stock traded at when the user next
  opened Portfolio, not at the expiration-day close. Two ways it went wrong: on expiration day it settled in the
  morning at the 10am price (stamped 4pm); a week later it settled at that week's price. A Close Call YES graded
  "right" on Friday's close could settle as a total loss on Monday's price. A derivatives reviewer would catch it.
- `market.session_close_on(symbol, d)`: raw (unadjusted) daily close of the last session on/before d, only once d is
  before today in New York; cached. `practice_options.positions`: past expiry -> settle at that close
  (`closed_at` = 4pm NY on expiration day, as before); until the close is in, the trade stays open with
  `settling: true` at its value at the latest price. `_past_expiry` = after 4pm NY on expiration day.
  `close()` refuses a by-hand close once expired (no after-hours price). Before 4pm on expiration day nothing changed.
- PracticePage: "Settling" chip, P&L greyed with "≈ / est.", a line saying it settles at the official close on that
  date and the cash comes back once that close is in; the Close button is hidden. Structure pill now wraps/truncates
  (long "Close Call: YES NVDA > $190.00" pill was breaking into 3 lines at 390px).
- Not changed: `yesno.grade_due` still grades on the adjusted close a day after expiry (same day's close in practice);
  no ranking, research, gate or real-money change.
- Test: test_expired_options_settle_at_the_expiration_day_close_not_a_later_price; two older tests now patch
  `market.session_close_on`. Backend 194 passed, vite build passes.
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/market.py, backend/v4/practice_options.py, backend/v4/tests/test_paper.py,
  frontend/src/components/PracticePage.jsx, docs/hq/status/builder.json.

## 2026-11-17 day (daily polish walk): options day count, "180-day check" explained, What's new
- No HQ messages from Murad. Display/wording only: no ranking, research, gate, grading, pricing-server or real-money change.
- frontend payoff.js: `daysToExpiry(expiration, today)` counts New York calendar days (was hours rounded to 4pm on
  expiry, so "186 days" for a 185-day option before ~noon ET). Feeds the card's day count, slider and time value.
- HowSure: `checkNote` adds ", the first one after your ~4-month window" when the checkpoint is later than the horizon.
- WhatsNew: UPDATED Nov 17, two lines for Portfolio (vs S&P 500, Closed trades / expiration-day settle).
- scripts/dev_offline_server.py stubs `market.session_close_on` so expired practice options settle in local walks.
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: frontend/src/lib/payoff.js, frontend/src/lib/payoff.test.mjs, frontend/src/components/chat/HowSure.jsx,
  frontend/src/components/WhatsNew.jsx, scripts/dev_offline_server.py, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-17 (Builder routine): Brain page forward test's confidence split says which calls it covers
- No HQ messages from Murad; no "proposed" items in feature_ideas.md. Picked a misleading number (rule a/c, Brain page):
  the live forward test headline is "+0.4 pts on 1,409 calls", and right under it High/Medium/Low show -0.1/-0.4/+0.6
  on 97+56+37 = 190 calls, with no word that the split is a different, smaller sample (confidence labels began Nov 8)
  or that groups of 37-97 calls are nowhere near clear of luck. A reader can't make the numbers add up.
- brain._forward: sends `confidence_since` (first labelled live call) and `by_confidence[d]["all"]` (the labelled
  subset taken together). BrainPage: a line under the split ("Confidence labels began on Nov 8, so this split covers
  only the 190 graded calls that carry one, not all 1,409. On those calls together the #1 did 0.0 pts..., against
  +0.4 pts on all 1,409. No group is clear of luck yet (each needs t 2 or more)..."); no "-0.0"; call counts with commas.
- Information only: no ranking, research, gate, grading or real-money change.
- Test: test_brain_forward_confidence_split_says_which_calls_it_covers. Backend 195 passed, vite build passes.
  Checked at 390 with the live /v4/brain data mocked in.
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/brain.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx, docs/hq/status/builder.json.

## 2026-11-17 late morning (daily polish walk, 2nd run): "Even with the S&P 500", money-formatted odds label
- No HQ messages from Murad. Display/wording only: no ranking, research, gate, grading, pricing or real-money change.
- PracticePage: |ahead| < $0.50 shows "Even with the S&P 500" / "even with it" in grey (was a red "Behind by $0").
- benchmark.py: `EVEN = 0.5`; summary "beat" counts trades at least 50 cents ahead (was > 0).
- yesno.odds_label: "$157.50/$162.50", "$186.30" (was "$157.5", "$186.3").
- scripts/dev_offline_server.py: synthetic option chain + option_quote (Close Call walkable offline).
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: frontend/src/components/PracticePage.jsx, backend/v4/benchmark.py, backend/v4/yesno.py,
  backend/v4/tests/test_benchmark.py, backend/v4/tests/test_v4.py, scripts/dev_offline_server.py, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-17 midday (Builder routine): Brain page forward test judges luck the way the scorecard does
- No HQ messages from Murad; no "proposed" items in feature_ideas.md. Picked a misleading claim (rule a, Brain page):
  the live forward test said "+0.4 pts ... unlikely to be luck (t 2.1)" counting all 1,409 calls as independent,
  while the scorecard right above it says calls made close together aren't independent and counts overlap. The
  1,409 graded 7-day calls were made on only 14 days (Oct 28 - Nov 10), each day's calls riding the same market week.
- brain._forward: each summary (by_days and every by_confidence group) now also sends `lift_t_nw` (same lift's t with
  `research._se_overlap`, window = the checkpoint's days, call date = belief created_at day), `days` (distinct call
  days) and `n_eff`. Live numbers checked with read-only SQL: t 2.0 counted that way (2.1 plain; date-clustered
  alone 1.65), 14 days, worth ~1,254 calls. So the headline still reads "unlikely to be luck", now honestly, at t 2.0.
- BrainPage: luck label and the confidence split's "clear of luck" use lift_t_nw (fallback lift_t); one line under
  the boxes says how many days the calls came from, the overlap-honest t and the plain t; the per-checkpoint grid
  uses 1/2/3 columns to match how many checkpoints exist (one box was stuck at a third of the width).
- Information only: no ranking, research, gate, grading or real-money change. Gates still read plain t's.
- Test: test_brain_forward_luck_check_counts_same_day_calls_once. Backend 197 passed (fresh venv), vite build passes.
  Checked at 390 and 375 with live /v4/brain data mocked in.
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/brain.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx, docs/hq/status/builder.json.

## 2026-11-17 midday (daily polish walk, 3rd run): credit trades worded at expiration; young MuLine turns flagged
- No HQ messages from Murad. Wording only: no ranking, research, gate, grading, pricing or real-money change.
- payoff.js plainEnglish: credit spreads / CSP / condor / butterflies / collar describe the payoff at expiration with
  the date ("is at or above $56 on Feb 19, 2027"), not "stays above ... until"; worst cases carry the date.
- Term.jsx + library.py blurbs for bull put / bear call spreads: "keep it all if the stock is above/below your strike
  at expiration".
- StrategyCard MuLine: trend age <= 3 trading days adds "It only turned up N trading days ago, so the trend isn't settled."
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: frontend/src/lib/payoff.js, frontend/src/lib/payoff.test.mjs, frontend/src/components/ui/Term.jsx,
  frontend/src/components/chat/StrategyCard.jsx, backend/v4/library.py, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-17 afternoon (Builder routine): Close Call shows how far the stock could move, and flags event-sized moves
- No HQ messages from Murad; no "proposed" items in feature_ideas.md. Picked a missing-context gap on Close Call (rule c):
  live NVDA "close above $160 on Fri Nov 20" was priced off 130% implied vol (NVDA's 60-day realized is ~45%: an
  earnings-week chain), yet the page showed only "40% YES" and the brain's MuLine reasons, with no word that the market
  expects a huge move before that date. A finance professor would ask where the event is.
- yesno.expected_move (pure): ATM IV of that one expiration (strike nearest spot, must be within 3%), the 1-sd
  range spot*exp(+-iv*sqrt(t)) ("about a 2-in-3 chance"), and implied / 60-day realized; `big` when > 1.35x (same line
  as Price Check's "expensive"; ~7% of logged 30-day ATM readings since Oct 15, e.g. NVDA, WMT, DIS). yesno.move_text
  writes the sentences. quote() sends `move` (None without market IVs). Information only: doesn't feed odds, lean,
  pricing or grading.
- YesNoPage: "How far it could move" box under the odds bars: grey band = the range, white tick = now, blue = the line,
  labels hang inward at the ends; amber line when the move is bigger than usual. WhatsNew line added.
- Tests: test_yesno_expected_move_and_big_move_warning, test_yesno_quote_sends_the_expected_move. Backend 199 passed
  (fresh venv), vite build passes. Checked at 390 and 375 (offline server; event case mocked in).
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, frontend/src/components/YesNoPage.jsx,
  frontend/src/components/WhatsNew.jsx, docs/hq/status/builder.json.

## 2026-11-17 late morning ET (daily polish walk, 4th run): "Moving now" keeps today's stories; no bare-year hooks
- No HQ messages from Murad. News feed display only: no ranking, research, gate, grading, pricing or real-money change.
- movers.feed: a curated rebuild now keeps earlier picked stories (news < 24h old, `MP_MOVERS_CARRY_HOURS`) after the
  new ones, up to 8 (live had 1 story at 10:24 AM ET Tuesday). Seeder/push unaffected (seeder dedupes; push uses item 0 = fresh).
- movers._hook / _fallback_story: a bare year ("2026") is never the Story hook.
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/movers.py, backend/v4/tests/test_v4.py, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-17 late afternoon (Builder routine): Close Call answers show what their practice trade did
- No HQ messages from Murad; no "proposed" items in feature_ideas.md. Picked a numbers-that-add-up gap on Close Call
  (rule c): "Your answers" showed only right / wrong, and a practice-traded answer looked the same as "Just call it".
  A YES call spread that closes between its strikes is right on the question but can lose money (below the breakeven),
  and the reverse for NO, so the page could say "right" next to a trade that lost, with the loss only on Portfolio.
- practice_options.outcomes(user_id, ids): read-only cost / status / gain per position (same cash numbers as closed()).
  yesno.mine attaches `trade` to answers with a position_id; when a graded answer's trade is still open it runs
  practice_options.positions() first, the same settle step the Portfolio runs (expiration-day close), so the two
  pages agree. yesno.trades_total; my_record_for adds `trades` {settled, pnl, won, open}.
- YesNoPage: "Your practice trades" box (total gain on settled/closed, how many made money, how many open) and on
  each traded answer "Practice trade · $X at risk" or "+$X at expiration" / "(closed early)", with an amber line when
  the trade and the answer disagree. WhatsNew line added.
- Information only: no odds, lean, pricing, grading, research or real-money change.
- Test: test_close_call_answers_show_what_their_practice_trade_did (test_paper.py). Checked at 390 and 375 (offline
  server; settled cases mocked in).
- Render builds still failing (out of build minutes): this queues too. Don't re-push to kick it.
- Files: backend/v4/practice_options.py, backend/v4/yesno.py, backend/v4/tests/test_paper.py,
  frontend/src/components/YesNoPage.jsx, frontend/src/components/WhatsNew.jsx, docs/hq/status/builder.json.

## 2026-11-17 afternoon ET (daily polish walk, 5th run): forward test's overlap t can't be surer than the plain t
- No HQ messages from Murad. Reporting only: no ranking, research gate, grading, pricing or real-money change.
- brain._forward summary: se_h = max(_se_overlap, plain se). With a few call days inside one window _se_overlap
  collapses toward 0 (live: High group, 97 calls on 3 days, -0.1 pts, plain t -0.1, overlap t -3.5, shown as
  "clear of luck"). research._se_overlap itself is unchanged; research/brain-upgrade sessions may want the same
  floor in research._metrics' reporting-only tnw if they ever run it on few dates (the scorecard has 429 dates, fine).
- BrainPage: clear groups say "ahead"/"behind"; "the rest" only when there is one.
- Files: backend/v4/brain.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx,
  docs/polish_log.md, docs/hq/status/polish.json.
## 2026-11-17 evening (CTO scout routine): idea 16 realized skewness; idea 14 final; proposal "outlier check"
- No HQ messages from Murad. Research only: no change to the live ranking, ranker v2's gate, grading or real money.
- Idea 14 (long-term reversal) recorded as final in docs/research_ideas.md: +0.53% lift, t 1.78 (t_nw 1.32), under the bar.
  Idea 15 (`delay`) was still at 0% coverage at the 17:40 UTC run; enrich fills it now that deploys are live again.
- New feature `rskew` (skewness of daily log returns over 63 sessions; Amaya et al. 2015): market.rskew /
  rskew_features, market.features, nn.make_features (not MODEL_NUMERIC), research.FEATS + DIRECTIONAL, research.enrich
  backfill (as of each pick's date). New fixed rule "avoid right-skewed stocks (-z_rskew)". Luck bar now 45 tries.
- Proposal in docs/feature_ideas.md: outlier check on research results (winsorized lift, median lift, top-10 share;
  reporting only). 81 graded 90-day outcomes are beyond ±100%.
- Test: test_realized_skewness_rule_and_enrich_backfill.
- Files: backend/v4/market.py, backend/v4/nn.py, backend/v4/research.py, backend/v4/tests/test_v4.py,
  docs/research_ideas.md, docs/feature_ideas.md, docs/hq/status/scout.json, docs/agent_handoff.md.

## 2026-11-17 afternoon ET (Builder routine): outlier check on research results ("Without the extremes" on the Brain page)
- No HQ messages from Murad. Built the scout's 2026-11-17 proposal (rule b). Reporting only: `_passes`,
  `fit_production`, MIN_LIFT / MIN_T, embargoes and the live ranking are unchanged.
- research.winsor_cuts: 1st / 99th percentile of every test-period idea's 90-day excess, per run. run() sets each test
  belief's clipped mean (`b["wmean"]`, rides in `_pick`'s new 6th item; None outside run(), e.g. live_check) and passes
  the cuts to `_metrics`, which adds lift_w / lift_w_t / lift_w_t_nw (with cuts) and lift_med / top10_share (always).
  luck() adds clear_w, app_clears_w, app_lift, app_lift_w, app_lift_w_t, app_lift_med, app_top10_share; run() stores
  `winsor` {q, lo, hi} (also in luck). brain._skill passes luck through unchanged.
- BrainPage: "Without the extremes" paragraph in the luck check (capped lift vs plain, 10 best calls' share, how many
  ways clear the bar capped; says "broad" at >= 70% kept, "a handful of huge calls" under 50%). Shows after the next
  research run fills the kv. WhatsNew line added. docs/research_ideas.md header explains the new columns.
- Tests: test_outlier_check_tells_a_broad_edge_from_a_few_lottery_tickets, test_research_run_reports_the_outlier_check.
  Checked at 390 and 375 (live /v4/brain JSON with mocked outlier numbers).
- Files: backend/v4/research.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx,
  frontend/src/components/WhatsNew.jsx, docs/research_ideas.md, docs/feature_ideas.md, docs/hq/status/builder.json.

## 2026-11-17 night (weekly brain upgrade): learned rankers hold back features still being backfilled
- No HQ messages from Murad; no "proposed" brain items in feature_ideas.md.
- research.learn_keys(coverage): ridge / gbm / neural-net inputs = ZKEYS minus z-features (and interactions on them)
  under COVERAGE_OK on the test-period ideas. run() uses it and stores `learn_keys` / `learn_held_back`;
  fit_production fits and stores `keys` from it (score_candidates already reads r["keys"]); live_check takes `keys`.
- Why: delay (12.6% filled) got a ridge weight as big as vol60's and moved mlp_adj from passing to failing on identical
  data. Scout: a new feature in FEATS no longer touches the learned models until enrich fills it; its fixed rule is
  still scored (provisional). No gate, embargo, MIN_* or NN promotion rule changed.
- Files: backend/v4/research.py, backend/v4/tests/test_v4.py, docs/brain_upgrades.md, docs/hq/status/brain.json.

## 2026-11-17 evening ET (daily polish walk, 6th run): Close Call ignores out-of-step spread quotes; ETF move wording
- No HQ messages from Murad. No ranking, research gate, grading or real-money change.
- yesno.digital_from_spread(..., why=None): left pair > 2 pts below the right pair -> None, "inverted" appended to why;
  quote() treats that as stale (one-vol odds, "out of date" label). Defensive only: the live NVDA 46%-above-$155
  case turned out to be monotone (lumpy) quotes, not inverted, so it still shows; it's under the 10-pt stale guard.
- yesno.move_text(..., is_etf=False): funds get "like a Fed decision or a big economic report" instead of earnings.
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-17 night ET (Builder routine): Moving now shows the S&P 500's move and each stock's move against it
- No HQ messages from Murad; no "proposed" items left in feature_ideas.md, so a finishing touch (rule a/c).
  Information only: no ranking, research gate, grading, pricing or real-money change.
- Why: live at Tue 5:50 PM ET every card on /trending was red (ACN "story helps" at -3.4%, MSFT -2.4%, CNI, UNP...),
  with no word that the whole market fell, so a story's effect couldn't be told from the market's. A finance
  professor reads any one-day move against the market first.
- movers.feed: SPY is fetched in the same snapshot call (BENCH); response gets `benchmark` {ticker, change,
  change_day} (None without a quote) and each company `vs_market` = change - SPY change, only when both moves are from
  the same session (`_vs_market`). story() returns feed items, so Story mode gets it too.
- MoversFeed: Pct shows "-3.4 pts vs S&P" under "stock -4.9% today" (VsMarket, points not %); MarketLine on
  TrendingPage under "Updated": "S&P 500 -1.5% today. Under each stock: its move vs the S&P...". StoryViewer's
  "Who it moves" card shows the same line. Home chips (ToolSelectorPage) unchanged. WhatsNew line added.
- Test: test_movers_feed_shows_each_move_against_the_sp500. Checked at 390 and 375 (live feed with mocked SPY).
- Files: backend/v4/movers.py, backend/v4/tests/test_v4.py, frontend/src/components/MoversFeed.jsx,
  frontend/src/components/TrendingPage.jsx, frontend/src/components/StoryViewer.jsx,
  frontend/src/components/WhatsNew.jsx, docs/hq/status/builder.json.

## 2026-11-18 early (UTC) (daily polish walk): luck check's "Without the extremes" line says its t is plain
- No HQ messages from Murad. Wording only; no ranking, research gate, grading or real-money change.
- BrainPage "Without the extremes": names its sample (the luck check's n test calls), says app_lift_w_t / clear_w count
  each call as independent, and points to the overlap count as the stricter test (the page read "0 of 45" then
  "7 of 45" a few lines apart). If research.py later adds an overlap-counted capped t, show it here instead.
- Files: frontend/src/components/BrainPage.jsx, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-18 early (UTC) (Builder routine): Close Call shows the brain's own questions and where it took the other side
- No HQ messages from Murad; no "proposed" items in feature_ideas.md, so a finishing touch (rule c). Information only:
  odds, lean, pricing, grading and the learning gate are unchanged.
- Why: the brain's Close Call record was a bare aggregate (and first grades land Thursday: 11 questions close Wed Nov 18).
  Its lean only nudges the market's odds a few points, so "picked the right side X%" mostly repeats the market; the only
  place it differs is when it takes the other side near 50%. A professor would ask to see the calls and that split.
- yesno.brain_questions(limit=12): the brain's own questions (user_id 'brain' only; users' stay private), newest asked
  first, with market_p / brain_p at asking, close, right/wrong/open, `disagrees`. yesno._disagrees(). scorecard() adds
  `recent` (also when nothing is graded yet) and `disagree` {n, right, days} on graded questions.
- YesNoPage: BrainQuestions list under "The brain's Close Call record" (6, "Show all"), amber "Took the other side
  from the market"; pcSide keeps one decimal near 50% (49.8% vs 50.2%); a line "Where its lean took the other side...
  right X of N". WhatsNew line.
- Test: test_yesno_scorecard_lists_the_brains_questions_and_where_it_took_the_other_side. Checked at 390 and 375.
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, frontend/src/components/YesNoPage.jsx,
  frontend/src/components/WhatsNew.jsx, docs/hq/status/builder.json.

## 2026-11-18 ~03:30 UTC (daily polish walk): Close Call brain list readable on phones, honest open count
- No HQ messages from Murad. Wording/layout only; odds, lean, pricing, grading and the learning gate are unchanged.
- yesno.scorecard() adds `brain_open` (brain's own open questions); the page uses it instead of `open` (all askers).
- YesNoPage: brain question rows and Your answers rows wrap instead of truncating the expiry; brain rows show the asked
  date; intro says seed_daily skips questions already open; "Show the latest 12".
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, frontend/src/components/YesNoPage.jsx, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-18 ~05:30 UTC (Builder routine): Close Call shows the real bid/ask next to the practice price
- No HQ messages from Murad; no "proposed" items in feature_ideas.md, so a finishing touch (rule a/c). Information
  only: odds, lean, practice prices, grading and the learning gate are unchanged.
- Why: Close Call said only "before bid/ask costs". Live at Tue 11:50 PM ET, SPY $725/$726 YES practiced at $63 while
  the listed spread was mid $74 / ask $105 (more than the $100 it can pay): a derivatives reviewer would price-check
  it against his screen and see neither number. A digital's odds are read at mid but paid at the ask.
- yesno.listed_costs(chain, k1, k2, exp, sides): per side bid (buy bid - sell ask, floor 0), ask (buy ask - sell bid),
  mid, practice, odds_at_ask (ask / payout), odds_at_practice, wide (no bid, ask >= payout, or gap > 20% of payout);
  None when a leg has no quote. quote() returns it as `listed`.
- YesNoPage ListedCosts box under Contracts: "$61 bid / $69 ask · practice $63" per side, break-even odds at the ask,
  round-trip cost; amber "too wide to trade as shown" note otherwise. WhatsNew line; docs/expert_review.md note.
- Test: test_yesno_listed_costs_show_the_real_bid_ask_next_to_the_practice_price. Checked at 390 and 375 (live quote,
  `listed` mocked for an in-hours and an after-hours case).
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, frontend/src/components/YesNoPage.jsx,
  frontend/src/components/WhatsNew.jsx, docs/expert_review.md, docs/hq/status/builder.json.

## 2026-11-18 ~06:45 UTC (daily polish walk): Close Call YES + NO never cost more than the payout
- No HQ messages from Murad. Pricing precision only: odds, lean, vols, grading and the learning gate are unchanged.
- practice_options.unit_value: legs marked `whole_cents` (set only by yesno.quote, kept by _clean_legs only when
  keep_leg_vols=True) sum unrounded leg prices and round the trade once to the cent. Per-leg rounding let live
  AAPL $350 read YES $112 + NO $139 = $251 on a $250 payout. Idea-card / other practice trades keep per-leg cents.
- YesNoPage: Risk / make amounts show cents when present (usdc).
- Files: backend/v4/practice_options.py, backend/v4/yesno.py, backend/v4/tests/test_v4.py,
  frontend/src/components/YesNoPage.jsx, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-18 ~08:30 UTC (Builder routine): Moving now says when a stock's move came before the news
- No HQ messages from Murad; no "proposed" items in feature_ideas.md, so a misleading-label fix (rule a). Information
  only: picks, directions, grading, prices and the learning gate are unchanged.
- Why: live at Wed 2:50 AM ET every card on /trending paired an overnight story with Tuesday's close ("SERV ▲ story
  helps · stock -2.8% on Tue"), so a red number read as the story already being wrong, though the move happened first.
- movers.move_timing(created_at, change_day): 'before' (story at/after that session's 4 PM ET close), 'during' (story
  mid-session), None (story before the open, or a time missing). feed() adds `move_timing` to each company with a move
  (_with_timing); story() returns feed items, so Story mode gets it too. Early-close days count as a 4 PM close.
- MoversFeed: Timing line "before this news" / "partly before this news" under the vs-S&P line (Pct); StoryViewer's
  "Who it moves" card too. Home chips unchanged. WhatsNew line.
- Test: test_movers_feed_says_when_the_price_move_came_before_the_news. Checked at 390 and 375 (live feed, timing
  computed by the new code; one card forced to 'during').
- Files: backend/v4/movers.py, backend/v4/tests/test_v4.py, frontend/src/components/MoversFeed.jsx,
  frontend/src/components/StoryViewer.jsx, frontend/src/components/WhatsNew.jsx, docs/hq/status/builder.json.

## 2026-11-18 ~09:40 UTC (daily polish walk): Moving now hunches matched to their own headline
- No HQ messages from Murad. Live: the 4 newest /trending cards showed the neighbouring headline's hunch/companies.
- movers: SCHEMA/PROMPT add `starts` (headline's first 5 words); _align() files answers by the headline they name
  (number, ±1, then any), drops non-matches; old numbered-from-1 shift kept only for answers without `starts`.
  Company `why` clipped at a whole word (110). KEY movers:v1 -> movers:v2 (drops the bad cached cards; first request
  after deploy rebuilds the feed, so carried older stories restart).
- Files: backend/v4/movers.py, backend/v4/tests/test_v4.py, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-18 ~11:15 UTC (Builder routine): Brain page "Just graded" says real-time or practice, and the call date
- No HQ messages from Murad; no "proposed" items in feature_ideas.md, so a misleading-label fix (rule a). Display only:
  grading, ranking, research gates and the forward test are unchanged.
- Why: live /brain "Just graded by the market" showed "WOOD bullish · after 365 days · 2h ago" with no word it was a
  practice call (seed_backfill, as of 2025-11-17, graded at once), mixed in with real-time 7-day grades. Real-time calls
  began Oct 28, so a 365-day grade "2h ago" read as a year-old live call.
- brain._recent_graded joins beliefs and adds `live` (source <> 'seed_backfill', the forward test's definition) and
  `called_on` (as_of_date). BrainPage rows: "Real-time call from Nov 10 · graded 2h ago" / "Practice call from
  Nov 17, 2025 · graded 2h ago", plus a one-line note under the list when a practice row is present.
- Test: test_brain_just_graded_feed_says_real_time_or_practice_and_the_call_date. Checked at 390 and 375 (live
  /v4/brain JSON with the new fields added).
- Files: backend/v4/brain.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx,
  docs/hq/status/builder.json.

## 2026-11-18 ~12:45 UTC (daily polish walk): Close Call odds don't read skew from quotes too wide to trade
- No HQ messages from Murad. Pricing source only: lean, grading, learning gate and research gates are unchanged.
- yesno.quote: if listed_costs(chain, k1, k2, exp, {})["wide"] (same test as the real-order box), market_p = the
  one-IV answer and the practice price uses the line IV (no leg_vols / spread_vol). Pre-market live SPY $725 read
  59% / 65% / 74% a minute apart off wide mids. Tight in-hours quotes keep the skew read.
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-18 ~14:30 UTC (Builder routine): option Price check compares the card's own price with the listed quote
- No HQ messages from Murad; no "proposed" items in feature_ideas.md, so a misleading-number fix (rule a). Information
  only: card prices, payoffs, Greeks, grading and the learning gate are unchanged.
- Why: option idea cards price every leg with Black-Scholes at one at-the-money IV (no skew) and show "$350 strike ·
  $11.51", but the Price check never mentioned that number, so a desk reviewer comparing with his screen saw two
  prices and no link. Live AAPL Bull Call Spread $350/$370 Dec 18: short $370 card $4.06 vs listed mid $3.04 (the
  strike trades at 23% IV vs the card's 26%), so the card's $7.45 debit vs $8.57 at mids, $9.84 paying the ask.
- pricecheck.card_vs_listed(res, premium, strike, exp, vol, vol_source, spot): same_contract, mid, diff, diff_pct,
  in_spread, text (in line / higher-lower by $ and %; then "the stock moved since the card was priced" or "this strike
  trades at X% IV vs the card's Y%"; a card strike that isn't listed gets no one-for-one comparison). check() adds it
  as `card` per request (never cached or written to feature_log). /v4/price_check takes card_premium, card_vol,
  card_vol_source, card_spot. engine: alt trades now carry vol_source too.
- PriceCheck.jsx: "Card vs listed" box per leg (amber when 10%+ off), and "Whole trade, per share" (card estimate,
  listed mids, ask/bid natural) when every option leg (2 max) matched its listed contract. StrategyCard passes trade +
  price. WhatsNew line. docs/expert_review.md: open item, cards price every strike at one IV (decide deliberately).
- Test: test_price_check_compares_the_cards_own_price_with_the_listed_quote. Checked at 390 and 375 (live AAPL quotes
  as fixtures in a throwaway harness).
- Files: backend/v4/pricecheck.py, backend/v4/router.py, backend/v4/engine.py, backend/v4/tests/test_v4.py,
  frontend/src/components/chat/PriceCheck.jsx, frontend/src/components/chat/StrategyCard.jsx,
  frontend/src/components/WhatsNew.jsx, docs/expert_review.md, docs/hq/status/builder.json.

## 2026-11-18 ~15:50 UTC (daily polish walk): option snapshots read every page (SPY Price check showed Dec 4 for Dec 18)
- No HQ messages from Murad. Data fetch only: pricing formulas, grading, research gates unchanged.
- market._option_snapshots follows Alpaca's next_page_token (max 8 pages). option_chain_near + option_iv use it;
  option_iv now requests strikes within ±30% of the asked strike and caches (time, rows, lo, hi) per
  (underlying, kind, expiration), refetching when a strike falls outside the cached band. Affects Price check, Close
  Call chains, card ATM IV and practice option marks on busy chains (SPY/QQQ-like): they now see the right expiration.
- pricecheck.card_vs_listed: "Most of the gap is volatility" only when the vol gap points the same way as the price gap.
- Files: backend/v4/market.py, backend/v4/pricecheck.py, backend/v4/tests/test_v4.py, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-18 ~17:30 UTC (Builder routine): option idea cards price each strike at its own listed implied vol
- No HQ messages from Murad; no "proposed" items in feature_ideas.md. Closes the expert_review.md open item (one ATM
  IV for every strike, no skew). Checked first: grader.structure_return re-marks every pick at the stock's realized
  vol and never reads card premiums, so grading, learning, ranking and research gates are unchanged.
- strategy.price_at_strike_vols(trade, price, as_of, iv_row): each option leg priced at its strike's listed IV, OTM
  side (put vol below spot, call vol at/above; parity makes either kind use it). All legs or none: listed strike within
  1%, expiry within 3 days, vol within 0.5x-2x the ATM vol, else the trade is returned unchanged. Recomputes
  est_premium, net_cost, capital, max loss/gain, breakevens (library.economics) and Greeks; legs carry `vol`,
  vol_source 'implied_strike', `one_vol` keeps the old debit. position_greeks uses a leg's own `vol` when present.
- market.option_iv_row returns (expiration, strike, iv) of the closest listed contract; option_iv wraps it (same cache).
- engine: one `mk()` builder for the card, the budget fallback and the alt version; only live cards whose vol came
  from the market (cvol_src 'implied', top 3) are re-priced. Backfill/practice seeding untouched.
- pricecheck.card_vs_listed: an 'implied_strike' card says "this strike's own listed implied volatility" (no "one
  number for every strike"). PriceCheck.jsx sends each leg's own vol.
- StrategyCard: caption "Each strike priced at its own implied volatility from listed options (23% to 26% a year)";
  Greeks note says the same; one-vol cards now say "one number for every strike". WhatsNew line.
- Still open (expert_review.md): opening a practice trade from a card prices at the AVERAGE of its legs' IVs.
- Test: test_option_cards_price_each_strike_at_its_own_listed_implied_vol. Checked at 390 and 375 (harness card).
- Files: backend/v4/strategy.py, backend/v4/engine.py, backend/v4/market.py, backend/v4/pricecheck.py,
  backend/v4/tests/test_v4.py, frontend/src/components/chat/StrategyCard.jsx,
  frontend/src/components/chat/PriceCheck.jsx, frontend/src/components/WhatsNew.jsx, docs/expert_review.md,
  docs/hq/status/builder.json.

## 2026-11-18 ~18:45 UTC (daily polish walk): practice trades from option cards open at the card's per-strike price
- No HQ messages from Murad. Closes the expert_review.md open item from the Builder's 17:30 entry.
- practice_options.quote (non-Close-Call path only): new `_strike_vols` reads each leg's listed IV with the same rule
  as strategy.price_at_strike_vols and stores `vol` on each leg (vol_source "strike"); marks reuse it. Average-IV
  fallback when any strike isn't listed. Client-sent vols still ignored. Grading/research gates untouched.
- Files: backend/v4/practice_options.py, backend/v4/tests/test_paper.py, docs/expert_review.md, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-18 ~20:30 UTC (CTO scout routine): idea 17 coskewness; ideas 15/16 results; "Is it new?" proposal
- No HQ messages from Murad. Research only: ranker v2's gate (`_passes`, `fit_production`) unchanged.
- Results recorded in docs/research_ideas.md (run 2026-11-18 17:19 UTC, delay and rskew 100% covered): idea 15 price
  delay = nothing (lift -0.20%, t -0.67); idea 16 realized skewness = strongest fixed rule so far (lift +1.45%, t 4.96,
  t_nw 2.90; risk-matched t_nw 3.38, in `clear_adj_nw`; lift_w +1.26%), but its numbers sit almost on the app's own #1.
- New feature `coskew` (Harvey & Siddique 2000 standardized coskewness, daily returns vs SPY over ~1 year):
  market.coskew / coskew_features, market.features, nn.make_features num (not MODEL_NUMERIC), research.FEATS +
  DIRECTIONAL, research.enrich backfill (as of each pick's date), rule `negative coskewness premium (-z_coskew)`.
  Result pending until `coskew` leaves `provisional`.
- Test fix (no behaviour change): test_lineages_pick_the_number_one_within_the_beliefs_own_direction compared a float
  with == (ten 0.02s average to 0.019999999999999997) and failed on the branch before this commit; now uses a 1e-9
  tolerance like the asserts above it.
- Proposal (docs/feature_ideas.md, proposed): per-rule agreement with the app's #1 and the head-to-head lift where
  they differ (reporting only).
- Files: backend/v4/market.py, backend/v4/nn.py, backend/v4/research.py, backend/v4/tests/test_v4.py,
  docs/research_ideas.md, docs/feature_ideas.md, docs/hq/status/scout.json.

## 2026-11-21 ~00:50 UTC (daily polish walk): My beliefs shows a same-day re-run of an idea once
- No HQ messages from Murad. Display only: stored beliefs, picks, grading, learning and research gates unchanged.
- engine.my_beliefs fetches limit*3 rows, collapses them with `_one_per_call` (normalized text + as_of_date + direction;
  keeps the run with user_prob/wrong_if, else the newest), adds `runs` per belief; the summary counts each call once.
- MyCallsPage shows "You ran this idea N times that day, so it's shown and counted once." when runs > 1.
- test_paper.test_close_call_answers_show_what_their_practice_trade_did now pins po._now_utc to the test clock (it
  failed on the real clock after Nov 20 4 PM ET; no code change).
- Files: backend/v4/engine.py, backend/v4/tests/test_v4.py, backend/v4/tests/test_paper.py,
  frontend/src/components/MyCallsPage.jsx, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-21 ~02:40 UTC (Builder routine): "Is it new?" — research rules vs the app's own #1
- No HQ messages from Murad. Builds the 2026-11-18 proposal in docs/feature_ideas.md. Reporting only: `_passes`,
  `fit_production`, the luck bar, MIN_LIFT/MIN_T and embargoes are unchanged and never read the new keys.
- research.run records each method's chosen #1 per test belief (fixed rules, "app (current #1)", learned models and
  their mixes) and the app's no-look-ahead #1 (`VS_APP_BASE`). `_vs_app` adds to each result: `same_as_app`,
  `n_diff`, `lift_diff`, `lift_diff_t`, `lift_diff_t_nw` (rule's #1 excess minus the app's on disagreements only).
  `is_new(results)` -> `luck.is_new`: the 3 strongest methods (by lift_t_nw) with those numbers; reaches the Brain page
  via brain._skill's luck passthrough. Fixed rules now pick via `_top` inline (`_choose` kept, unused).
- BrainPage.jsx: "New, or the app restated?" paragraph in the luck check (quotes the head-to-head only with 100+
  disagreements). WhatsNew line. docs/research_ideas.md header explains the new columns. Values appear after the
  next research run.
- Tests: test_is_it_new_reports_agreement_with_the_app_and_the_head_to_head_where_they_differ,
  test_research_run_reports_is_it_new. Checked at 390 and 375 (live /v4/brain with a planted is_new).
- Files: backend/v4/research.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx,
  frontend/src/components/WhatsNew.jsx, docs/feature_ideas.md, docs/research_ideas.md, docs/hq/status/builder.json.

## 2026-11-21 ~03:50 UTC (daily polish walk): "Next market grading" clock now shows when picks really get graded
- No HQ messages from Murad. Display only: grader, grading, research gates and render.yaml unchanged.
- brain._next_runs: grading = first hourly :13 run in the midnight-ET hour after a weekday (Tue-Sat 12:13 AM ET),
  because grader.grade skips closes dated today (NY), so the 22:47 UTC grade-and-train job grades nothing new.
  BrainPage: "Sat 12:13 AM ET, once Friday's close is final"; "Last market grading" from real graded feed events.
- FYI for whoever owns the jobs: the 22:47 UTC job's `health:grading` timestamp is a retrain run, not a grading.
- Files: backend/v4/brain.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx,
  docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-21 ~05:30 UTC (Builder routine): strategists compared with the app's #1 without the peek
- No HQ messages from Murad; no proposals open in feature_ideas.md, so this fixes a misleading number on /brain.
- "Survival of the smartest" judged the leading strategist against the app's stored #1 on its 300-call window, which
  is 100% practice calls (prod kv lineage_window, Nov 20), where the stored #1 used track records that include later
  results (the Brain page's "catch we found"). Strategists never see those, so "about the same as the app's own pick"
  compared against an inflated yardstick (+2.6 pts stored).
- lineages._graded_beliefs(pit=True) (evolve only) adds each candidate's research._pit_score (app's score as of the
  call's date; real-time calls keep their stored #1); window_baselines adds `app_pit` when every candidate has it.
  BrainLineages.jsx compares the leader (and the "app's own #1" row in the ranking) with app_pit, shows the stored
  number beneath as "as stored, with the peek", one sentence why. Falls back to the old text until the next evolve.
- Display only: strategist fitness/selection, pick_champion's live gate (LIVE_MIN/LIVE_MARGIN), research gates
  unchanged. Value appears after the next grade-and-train run (22:47 UTC weekdays, so Mon Nov 23).
- Files: backend/v4/lineages.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainLineages.jsx,
  docs/hq/status/builder.json.

## 2026-11-21 ~06:50 UTC (daily polish walk): Close Call confirmations read as the question
- No HQ messages from Murad. Wording only: prices, set-aside, the stored "Close Call: ..." structure label (Portfolio
  shows it), grading and research gates unchanged.
- yesno.make_call builds its own confirmation instead of practice_options' generic one ("Opened 2 NVDA Close Call: NO
  NVDA > $185.00 contracts ..."), and "Just call it" names the question and a readable date instead of 2026-11-27.
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-21 ~08:45 UTC (Builder routine): Close Call trades the spread centred on the line
- No HQ messages from Murad; no proposals open in feature_ideas.md, so this fixes a misleading Close Call price.
- When the line was a listed strike, `yesno.strikes_around` took the line and the next strike up: NVDA $185 on $2.50
  strikes traded $185/$187.50, which replicates a close above $186.25. The screen said "Market's odds 50%" while YES
  cost $109 of $250 (44%) and both breakevens sat above the line ($186.09). Now a line on a strike takes the strikes
  either side ($182.50/$187.50, $500 payout, the same pair `digital_from_spread` reads the odds from): YES $248 of
  $500, breakevens $184.98 / $184.99. A line between two strikes keeps those two; the lowest strike falls back as before.
- `spread_note(..., level)` adds "Its strikes sit $2.50 either side of the $185.00 line, so YES's share of the payout
  is about the market's odds". YesNoPage prints strikes as $182.50 (was $182.5). WhatsNew line.
- Not changed: odds, pricing (per-strike vols), grading (close vs line), open trades, `real_money_order` code
  (still off; its proposed order now uses the same centred spread). Payouts per contract are now usually 2 strike gaps.
- Tests updated to the centred pair (skew test now pins YES price = market odds within 0.5 pt); 224 passed (fresh venv).
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, frontend/src/components/YesNoPage.jsx,
  frontend/src/components/WhatsNew.jsx, docs/expert_review.md, docs/hq/status/builder.json.

## 2026-11-21 ~09:50 UTC (daily polish walk): Close Call's "bigger move" line knows a market-wide fear spike
- No HQ messages from Murad. Display only: odds, practice prices, lean, grading, research gates unchanged.
- Close Call's move box told AAPL/MSFT/NVDA "news is due, like an earnings report" when SPY's options were just as
  rich (2.2x realized; November selloff). `yesno.market_iv_rv` (SPY ratio, same expiration, 15-min cache) now feeds
  `move_text`, which says "market-wide nervousness" unless the stock is over 1.5x the market's ratio.
- Price Check's "expensive" sentence also names a nervous market.
- Files: backend/v4/yesno.py, backend/v4/pricecheck.py, backend/v4/tests/test_v4.py, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-21 ~11:30 UTC (Builder routine): Close Call centres the spread on the line on uneven strike grids too
- No HQ messages from Murad; no proposals open in feature_ideas.md, so this fixes a misleading Close Call price.
- Live SPY Nov 27 lists $699, $700, $705 and nothing $701-704. For the suggested $700 line, `strikes_around` took the
  nearest strikes ($699/$705, a digital at $702): YES $244.59 of $600 (40.8%) beside "Market's odds 43%", both
  breakevens $701.45. Same for lines between strikes ($702 -> $700/$705, middle $702.50).
- `yesno.strikes_around` now first looks for two listed strikes the same distance either side of the line, no wider
  than 2x the nearest pair (SPY $700 -> $695/$705, $702 -> $699/$705); else the nearest pair as before.
  `spread_note` on an uneven pair now says YES's price is about the odds of a close above the strikes' middle.
- Not changed: odds (`digital_from_spread` already read them at the line), grading, open trades, `real_money_order`
  (still off; uses the same pair). Even grids (NVDA $185 -> $182.50/$187.50) pick the same pair as before.
- Seen, not fixed (weekend quotes): SPY Nov 27 $705 read 45% from stale spread mids while $702 read 41% at one vol.
  The stale guard (10 pts off one-vol) let it through; worth a look on a weekday if it persists in market hours.
- Test: test_yesno_uneven_strikes_still_centre_the_spread_on_the_line.
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, frontend/src/components/WhatsNew.jsx,
  docs/expert_review.md, docs/hq/status/builder.json.

## 2026-11-21 ~12:10 UTC (Builder, same run, follow-up): Close Call reads the odds off the trade's own centred spread
- Live after 74dc248: SPY $700 traded $695/$705 (cost 50.2% of payout) but the odds still came from the finer
  $699/$700/$705 pairs (46.7%), so the screen still didn't add up on uneven grids.
- `yesno.quote`: when the trade's strikes are centred on the line and the full reading isn't stale, the odds come from
  that one spread ((C(k1) - C(k2)) / width, its middle = the line), unless it is over 10 pts off the one-vol answer.
  On even grids this is the same number as before (the interpolation at a listed line is that same spread).
- Test extended (skewed quotes on an uneven grid: YES cost / payout = market odds within 0.5 pt).
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, docs/hq/status/builder.json.

## 2026-11-21 ~12:40 UTC (daily polish walk): Close Call says "prices didn't load" instead of a 500
- No HQ messages from Murad. Display/error handling only: odds, prices, grading, research gates unchanged.
- `router._yesno` now also catches `market.MarketDataError` and returns a plain status-error message (was a bare 500
  with no CORS headers -> blank card, 4 retries, then "Check your connection").
- Brain feed reads "The market graded 1 pick / It didn't beat the S&P 500" for single gradings.
- Files: backend/v4/router.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-21 ~14:30 UTC (Builder routine): Close Call reads odds off a quiet spread; put-call parity guard
- No HQ messages from Murad; no proposals open in feature_ideas.md, so this fixes misleading Close Call odds.
- Live this morning, SPY $693.89, Nov 27: $695 line 48%, $700 50.2%, $705 44.7% (odds rising from $695 to $700).
- First push (130e98a) blamed stale quotes and added a put-call parity guard. Checked after deploy with listed bids/asks
  (price_check): parity F = $693.5-693.9 at $695-$710, so the quotes AGREE with the price and the guard stayed quiet
  (correctly). $700's 50% is real skew: a digital call is N(d2) - vega * dsigma/dK and equity skew (dsigma/dK < 0)
  lifts it above the one-vol 43%. The guard stays as a safety check (`yesno.parity_forward`, `quotes_out_of_step`:
  F over 0.1 sd of the move above the last price, or that + 2% below for dividends -> one-vol odds, source line names
  the price the quotes imply). Its earlier comments/WhatsNew line claiming SPY was stale were corrected.
- The real bug: the $695 line on $1 strikes. $694/$695/$696 mids read 78% then 51% one step apart (weekend quotes,
  bid/ask $0.17-0.28 on $1 gaps blur each reading ~9 pts), so the reading was >10 pts off one-vol and fell back to 48%.
  `yesno.spread_noise` / `quiet_pair`: when the fine reading is inverted or >10 pts off, step out to the narrowest
  centred pair (within 4% of the line) whose quotes blur the odds by <= 3 pts, trade it and read the odds off it
  (only if that reading is itself within 10 pts of one-vol). Otherwise unchanged; quiet fine spreads untouched.
- Not changed: grading, research gates, the 10-pt stale guard, listed bid/ask box, real_money_order (still off).
- Tests: test_yesno_quotes_set_at_another_stock_price_fall_back_to_one_vol,
  test_yesno_noisy_fine_strikes_step_out_to_a_quiet_centred_spread. WhatsNew line.
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, frontend/src/components/WhatsNew.jsx,
  docs/expert_review.md, docs/hq/status/builder.json.
- Live after 654b347 (SPY $693.89, Nov 27): $695 56.7% ($691/$699, YES $453 of $800), $700 50.2%, $705 44.7%,
  $710 31.4% (one-vol, wide quotes): in order. Still open: $690 shows one-vol 54.7%. Its quiet pairs ($687/$693,
  $684/$696) read ~64-67%, which looks like real skew (it lifts $695 by 8.5 pts and $700 by 7), but that is over the
  10-pt guard vs one-vol, so they are refused. Not loosened here; a skew-aware guard (compare with one-vol plus the
  skew term from listed IVs) is the next step, but Alpaca's call/put IVs at one strike disagree (41% vs 31% at $700
  while parity holds), so it needs IVs backed out of the mids first.

## 2026-11-21 ~16:30 UTC (daily polish walk): "I don't think tungsten ..." not "Tungsten"
- No HQ messages from Murad. Wording only: news opposites keep names capitalised but no longer treat a capital inside
  a longer name ("Sunrise Tungsten Project") or a capitalised word before an acronym ("Cheaper AI") as a name.
- Files: backend/v4/seeder.py, backend/v4/tests/test_v4.py, frontend/src/lib/text.js, docs/polish_log.md,
  docs/hq/status/polish.json.

## 2026-11-21 ~17:30 UTC (Builder routine): Close Call odds use the option smile (skew-aware guard + fallback)
- No HQ messages from Murad; no proposed ideas open in feature_ideas.md. Picked my own open item: live SPY Nov 27
  ladder (weekend quotes) read $685 63.4%, $690 54.7%, $695 56.7% (odds rising with the line). $690 fell back to
  one vol (the line's feed IV, 34.7%) because its quiet spread read ~64-70%, over 10 pts from one vol. That gap is
  skew: SPY's one-week smile falls ~0.35 vol pts per $1, lifting $690 ~12 pts over N(d2).
- New `yesno.skew_odds(chain, spot, level, years)`: our own IVs from OTM mids (puts below the forward, calls above)
  within 2% of the line, straight-line fit, P = N(d2(sigma_L)) - e^{rT} vega(L) dsigma/dK. None with < 2 strikes a
  side, RMS fit miss > 8% of the vol (junk quotes make a V), or a skew term > 15 pts.
- `quote`: the 10-pt stale guard (and quiet-pair / own-spread checks) now compares with the smile's odds, not one
  vol. A trade pair whose quotes blur its odds by > MAX_NOISE now also steps out to a quiet pair (with skew in the
  yardstick a noisy $694/$696 reading no longer looked "far off"). Outside market hours (`market.is_open()` False),
  or when the spread is stale/wide/missing, the smile sets the odds (source line says so) and prices the trade's two
  strikes at the smile's vols (`price_source` "smile", `leg_vols`), keeping the narrow pair. New `market_p_smile`.
  Not when the quotes imply another stock price (parity guard): then one vol as before. Market-hours readings of a
  clean spread are unchanged.
- Checked on a fixture of the live SPY Nov 27 quotes (114 calls/puts from /v4/price_check): closed, $682..$708 read
  70.5, 69.4, 68.9, 66.3, 64.6, 63.1, 59.6, 56.1, 53.5, 50.3, 45.4, 40.3%: falling, YES cost = odds each time.
  Screen checked locally at 390 (SPY $690: 65% YES, risk $129.11 to make $70.89, footer names the smile vols).
- Not changed: grading, research gates, the 10-pt threshold, the parity guard, listed bid/ask box, real_money_order.
  The brain only asks in market hours, so its seeded questions still read clean spreads first.
- Tests: test_yesno_smile_odds_keep_skew_and_fall_as_the_line_rises (new); the wide-quotes test now expects the smile
  after hours (renamed ..._read_the_smile_for_odds_and_price).
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, frontend/src/components/YesNoPage.jsx,
  frontend/src/components/WhatsNew.jsx, docs/expert_review.md, docs/hq/status/builder.json.
- Follow-up (same run, after the live check): live NVDA ($129.17) showed no smile at most lines because its quotes
  imply ~$126.15 by put-call parity (put IVs ~140% beside ~90% for calls). `skew_odds` now refuses a fit when the
  quotes' parity forward is over 0.1 sd (+ mid noise) from the last price, with no dividend allowance, and on coarse
  grids takes the two nearest strikes each side out to 8%. NVDA keeps its earlier behaviour (spread / one vol).
  Next: the parity guard in `quote` still allows 2% for dividends, which let NVDA's 2.3% gap through; and NVDA $118
  shows one-vol 62% odds beside a YES costing 64.7% (spread_vol pricing): pre-existing, worth a look on a weekday.

## 2026-11-21 ~20:00 UTC (daily polish walk): story hooks keep the article's hedge
- No HQ messages from Murad. Story mode's big hook read "8 million barrels" where the article says "up to 8 million";
  `movers._hook` now takes the article text and puts a dropped hedge back ("Up to 8 million barrels"), or drops the
  hook if it gets too long. Cached stories fixed when served.
- Files: backend/v4/movers.py, backend/v4/tests/test_v4.py, docs/polish_log.md, docs/hq/status/polish.json.

## 2026-11-21 ~19:05 UTC (CTO scout routine): idea 17 recorded, idea 18 (trading-activity variability) added
- No HQ messages from Murad. Idea 17 (coskewness) final: lift +0.83% (t 3.00, t_nw 3.12), risk-matched +0.87% (t_nw
  3.95, tops `clear_adj_nw`), but lift_diff vs the app +0.40% (t_nw 0.58): mostly restates the app. Idea 16 (rskew)
  is-it-new: same_as_app 25%, lift_diff +1.23% (t_nw 2.44). Both written up in docs/research_ideas.md.
- New feature `cvvol` (Chordia, Subrahmanyam & Anshuman 2001): CV of daily dollar volume over ~1 year, as of each
  pick's date. Added to market.cvvol / cvvol_features / features(), nn.make_features num (not MODEL_NUMERIC),
  research.FEATS + DIRECTIONAL, research.enrich backfill, fixed rule "steady trading activity (-z_cvvol)".
  Result pending until `cvvol` leaves `provisional`.
- Proposal (docs/feature_ideas.md): "Does it hold every year?" lift per chronological time block + sign count,
  reporting only. Side note there: coskew row shows n_eff = n with t_nw > t; may be worth a look at `_se_overlap`.
- Not changed: gates, `_passes`, `fit_production`, luck bar.
- Files: backend/v4/market.py, backend/v4/nn.py, backend/v4/research.py, backend/v4/tests/test_v4.py,
  docs/research_ideas.md, docs/feature_ideas.md, docs/hq/status/scout.json.

## 2026-11-21 ~21:00 UTC (Builder routine): "Does it hold every year?" — research results split into time stretches
- No HQ messages from Murad. Built the scout's proposal (docs/feature_ideas.md, 2026-11-21), reporting only.
- `research._time_blocks`: each method's test calls split into 4 chronological stretches of ~equal call count, cut on
  call dates (a date never splits; outcomes never decide a cut). `_metrics` (when calls carry dates) adds `blocks`
  (from/to/n/lift/beat), `pos_blocks`, `n_blocks`, `last_block_lift`, `block_spread`. `luck` adds `steady` /
  `steady_nw` (cleared the bar and ahead in 3+ of 4), `steady_min`, `app_blocks` (app as stored) and `app_pit_blocks`
  (no look-ahead). `is_new` rows carry pos_blocks / last_block_lift.
- Brain page luck check: new "Through time." line (stretch lifts with month ranges, the no-peek count, how many of
  the cleared ways held in 3+ of 4). Checked at 390 with the live /v4/brain plus injected blocks: no overflow.
- Scout's side note (coskew n_eff = n with t_nw > t): `_se_overlap` can be below the plain se when nearby dates'
  residuals lean opposite ways and n_eff is capped at n; not a bug, noted in docs/research_ideas.md.
- Not changed: `_passes`, `fit_production`, luck bar thresholds, MIN_LIFT/MIN_T, grading. Numbers appear after the
  next research run.
- Test: test_research_time_blocks_flag_a_rule_carried_by_one_stretch.
- Files: backend/v4/research.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx,
  frontend/src/components/WhatsNew.jsx, docs/research_ideas.md, docs/feature_ideas.md, docs/hq/status/builder.json.

## 2026-11-21 ~22:30 UTC (weekly brain upgrade, key `brain`): lone ranker gets the real-time check
- No HQ messages from Murad. Health OK. Ranker v2 is on (mlp alone, lift +1.69%, t_nw 3.58) through the unchanged gate.
- research.live_check: `alone=True` scores the model by its own order; beliefs whose picks carry `rv2` (ordered by
  ranker v2) are skipped (`ranker_ordered`), since their stored #1 isn't the app's. load() flags them (`b["rv2"]`).
- research.live_veto + fit_production: a lone passing candidate is skipped once 300+ real-time calls graded at 30 days
  show its #1 doing worse than the app's #1; with fewer it goes live as before. Stricter only; _passes etc. unchanged.
- Note for everyone: the legacy nn.py network retrains nightly on identical data (n_train 11,408 since Nov 3, 90-day
  labels wait on real-time calls reaching 90 days); its "versions" panel numbers won't move until ~late January.
- Files: backend/v4/research.py, backend/v4/tests/test_v4.py, docs/brain_upgrades.md, docs/agent_handoff.md,
  docs/hq/status/brain.json.

## 2026-11-21 ~21:45 UTC (Daily polish, key `polish`): What's new no longer says Close Call breaks even at the line
- No HQ messages from Murad. Live public pages clean at 390; signed-in screens clean locally.
- WhatsNew.jsx: the Nov 21 Close Call line said "both sides break even at the line"; they break even at about the same
  price between the strikes (k1 + payout x odds; live AAPL $350 -> $349.45). Wording only.
- For whoever works on Close Call next: weekend NVDA Nov 27 reads 51% above $125 and 51% above $130 (last $129.17).
  Call-spread mids $122/$128 $3.05 vs $127/$133 $3.06 break convexity; the one-vol yardstick uses the nearest put IV
  (150%) and `quotes_out_of_step` gives 2% dividend room, so the junk spread passes. Not changed (details in
  docs/polish_log.md).
- Files: frontend/src/components/WhatsNew.jsx, docs/polish_log.md, docs/agent_handoff.md, docs/hq/status/polish.json.

## 2026-11-21 21:50 UTC (HQ chair, key `chair`): SPRINT — Murad wants serious changes live by 7:00 pm MST (02:00 UTC)
- Murad, live, 2:37 pm MST: "this has been a toy for too long... get this out to the masses... do or die". Every run
  between now and 02:00 UTC drops backlog research polish and works on GROWTH and LAUNCH READINESS instead.
- Builder (15:51 MST run): build ONE shareable growth feature end to end: a "Share my call" button on a call / graded
  result that makes a link with its own preview card (OG image + title), so people can post their calls and friends
  land on /welcome. If the scout's newest Part B proposal in docs/feature_ideas.md is a share/referral feature, build
  that. Must be live (deployed and checked on the live site) before 02:00 UTC.
- Polish (17:23 MST run): walk the new-user path /welcome -> sign up -> first call on a phone and fix the top friction
  points. Treat it as launch day: nothing confusing, broken or empty on that path.
- Growth (running now): docs/growth_plan.md. Note scripts/social/ already has a dry-run auto-poster (IG + TikTok via
  official APIs); the plan should say exactly what's left to switch it on, not redesign it.
- Same hard rules as always (no posting, no secrets/env vars, no gates loosened, tests must pass). Bundle changes:
  build minutes are limited.
- Chair compiles a 7 pm summary for Murad from every status file.

## 2026-11-21 ~22:00 UTC (Health watch, key `health`): extra debugging sweep on the chair's call; /v4/trending cached 60 s
- No Render alert or user emails (12h), no HQ messages. Jobs ok (learning 21:21 UTC, grading Fri 22:48 UTC).
- Logs, last 24h (backend + both crons): only the harmless pip "yanked click 8.2.2" warning on every build; no errors.
  Brief 502s on /v4/brain ~21:37-21:39 UTC were the bc44ff3 deploy swapping instances, not a crash.
- Endpoint timings: most public GETs 0.2-0.9 s; /v4/yesno/scorecard 17 s only on the first cold hit after deploy, then ~1 s.
  Worst steady one: /v4/trending at 3-5 s every time (~20 fresh DB connections per build). Fixed: router caches the
  result per (days, limit) for 60 s (`_trending_cached`); engine.trending unchanged, so its tests are untouched.
- hq_messages: the table is empty (0 rows for any author), on the same Postgres the backend uses. Backend logs since
  Nov 14 show no successful GET or POST on /v4/hq (only 403s/404s from unsigned tools). So Murad has never posted
  from /hq; his "all hands" words reached the chair some other way. Posting code (hq.post) looks right; not verified live
  (would need his signed-in session).
- Files: backend/v4/router.py, docs/agent_handoff.md, docs/hq/status/health.json.

## 2026-11-21 ~23:30 UTC (brain upgrade, extra run on the chair's all-hands wake, key `brain`): grades survive splits
- No HQ messages from Murad (hq_messages is empty). Health OK.
- Bug: bars are split-adjusted, real-time entry_price is raw, so ITA (3-for-1) and SOXX splits graded 76 real-time
  calls at ~-66%/-69% (5 were #1 picks), right in the first pool the 30-day live_veto will read.
- market.split_factor (entry vs the history's own close that day; 1.0 / split ratio / None for bad data). grader.grade
  uses it (None -> not graded, counted `suspect`); grader.repair_splits is a one-time re-grade of old rows (kv
  `grader:split_repair_v1`; delete that key to rerun it); engine.my_beliefs uses it for "My calls".
- Gates unchanged. Test: test_grades_put_a_real_time_entry_on_the_split_adjusted_scale.
- Files: backend/v4/market.py, backend/v4/grader.py, backend/v4/engine.py, backend/v4/tests/test_v4.py,
  docs/brain_upgrades.md, docs/agent_handoff.md, docs/hq/status/brain.json.
## 2026-11-21 ~22:15 UTC (CTO scout routine, key `scout`): idea 19 (timing of the 52-week high) added; PBO proposal
- No HQ messages from Murad. Idea 18 (`cvvol`) still pending: coverage 12.6% at the 2026-11-21 21:05 run.
- New feature `hi_age` (Bhootra & Hur 2013): sessions since the highest close of the past 252, / 251 (0 = today), as
  of each pick's date; neutral 0.5 (research.NEUTRAL). Added to market.hi_age / hi_age_features / features(),
  nn.make_features num (not MODEL_NUMERIC), research.FEATS + DIRECTIONAL, research.enrich backfill, fixed rule
  "recent 52-week high (-z_hi_age)". Result pending until `hi_age` leaves `provisional`.
- Proposal (docs/feature_ideas.md): probability of backtest overfitting (CSCV, 8 date blocks, 70 splits) across all
  research rules, reporting only. Evidence: the no-look-ahead app #1 was -1.65% in the latest stretch after three
  positive ones.
- Not changed: gates, `_passes`, `fit_production`, luck bar.
- Files: backend/v4/market.py, backend/v4/nn.py, backend/v4/research.py, backend/v4/tests/test_v4.py,
  docs/research_ideas.md, docs/feature_ideas.md, docs/hq/status/scout.json.

## 2026-11-21 ~22:45 UTC (CTO scout, extra run on the chair's sprint wake, key `scout`): idea 20 + "I called it" cards proposal
- No HQ messages from Murad (hq_messages still empty). Ideas 18 (`cvvol`) and 19 (`hi_age`) still pending backfill.
- New feature `ldvol` (Brennan, Chordia & Subrahmanyam 1998): log mean daily dollar volume over ~1 year, as of each
  pick's date; neutral 15.0. Added to market.ldvol / ldvol_features / features(), nn.make_features num (not
  MODEL_NUMERIC), research.FEATS + DIRECTIONAL + NEUTRAL, research.enrich backfill, fixed rule
  "low dollar volume (-z_ldvol)". Result pending.
- Part B on the chair's growth call: docs/feature_ideas.md "I called it" cards: per-call share link `/c/{belief_id}`
  with its own og tags + Pillow PNG, redirect to /welcome?ref=card&c=id, Wordle-style copy text, Share button on graded
  calls. Builder: this is the share/referral proposal the chair's sprint note refers to; honesty and privacy rules
  are in its Risks section (graded checkpoints only, misses shown like wins, no names).
- Not changed: gates, `_passes`, `fit_production`, luck bar.
- Files: backend/v4/market.py, backend/v4/nn.py, backend/v4/research.py, backend/v4/tests/test_v4.py,
  docs/research_ideas.md, docs/feature_ideas.md, docs/hq/status/scout.json.

## 2026-11-21 ~23:10 UTC (Builder, key `builder`): "I called it" share cards (the chair's sprint item)
- No HQ messages from Murad (hq_messages empty). Built the scout's Part B proposal from docs/feature_ideas.md.
- Backend: new backend/v4/share.py, mounted at the root in backend/app.py. `GET /c/{belief_id}` = tiny HTML with the
  call's own og/twitter tags + instant redirect to `<MP_SITE_URL>/welcome?ref=card&c=<id>`; `/c/{id}.png` = 1200x630
  Pillow card (DejaVu from matplotlib's mpl-data, in-memory cache of 64); `/c/{id}.json` = same facts + Wordle-style
  copy text. Grades come only from stored outcomes (same per-call measure as engine._graded_checks / baserate);
  ungraded checks say "not graded yet"; misses drawn like wins; no user id/name; only `source='user'` calls, else 404.
- Frontend: My beliefs "↗ Share" now shares the link + copy text (navigator.share, clipboard fallback "Copied"), shown
  on every call; the old tall image is a small "Image" button, its kicker no longer says "I called it" on ungraded
  live returns ("My call, so far"). WelcomePage shows the shared call in place of the example when `?c=` is present.
  WhatsNew line added.
- test_security PUBLIC list now allows `/c/{belief_id}(.png|.json)` (public by design). New test:
  test_share_card_shows_only_stored_grades_and_its_own_tags.
- Not changed: grading, research gates, auth, env vars. `ref=card` is in the landing URL only; sign-ups don't store it yet.
- Files: backend/v4/share.py, backend/app.py, backend/v4/tests/test_v4.py, backend/v4/tests/test_security.py,
  frontend/src/components/MyCallsPage.jsx, frontend/src/components/WelcomePage.jsx, frontend/src/components/WhatsNew.jsx,
  frontend/src/lib/api.js, docs/feature_ideas.md, docs/agent_handoff.md, docs/hq/status/builder.json.

### 2026-11-21 · growth agent (scheduled)
- Added `docs/growth_plan.md`: guerrilla-first launch plan, 7 yes/no launch items for Murad, 3 free channels, and a spec for extending `scripts/social/` (add Facebook Page Reels + auto-queue the daily `make_reel.js` reel). Nothing built yet; build chat owns the code.
- Key finding: the app is already open, but reels still end "coming soon" (`LIVE` flag in `make_reel.js` / `?live=1` on `/reel`). Don't flip it without Murad's "launch".
- Updated `docs/hq/status/growth.json`. No code or deploy changes.

## 2026-11-22 ~00:40 UTC (Polish walk, key `polish`): share cards say what the grade was measured on
- The builder's "I called it" cards showed the theme's grade beside one ticker ("CHWY, calling up +1.2 pts" while CHWY
  fell 11.5%). Now the card lists up to 3 shown picks and says "Graded on <fund> / the average of N related stocks".
  New card/json fields `picks`, `measured_on`. Grades and grading unchanged. Double period in og description fixed.
- Files: backend/v4/share.py, backend/v4/tests/test_v4.py, frontend/src/components/WelcomePage.jsx,
  docs/polish_log.md, docs/agent_handoff.md, docs/hq/status/polish.json.

## 2026-11-22 ~02:30 UTC (Builder, key `builder`): "Would we have picked the winner?" (probability of backtest overfitting)
- No HQ messages from Murad (hq_messages empty). Built the scout's proposed PBO item from docs/feature_ideas.md.
- research.pbo (CSCV, Bailey et al. 2017): test calls cut on dates into 8 blocks (same date rule as _time_blocks, via
  new `_date_blocks`), 70 in/out-of-sample splits; stores `luck.pbo` (all methods except the look-ahead app row) and
  `luck.pbo_learned` (ranker v2 candidates + mixes): pbo, oos_lift_med, p_loss, slope, winners, n_methods. Wrapped in
  try/except inside run(); a few hundred numbers, no new data or memory.
- Brain page luck card: new "Would we have picked the winner?" paragraph (shows after the next research run).
  WhatsNew line added (UPDATED Nov 22).
- Reporting only: _passes, fit_production, luck bar, MIN_LIFT/MIN_T untouched.
- Tests: test_pbo_is_near_half_for_noise_rules_and_near_zero_with_a_real_edge; walk-forward test now checks luck.pbo.
- Files: backend/v4/research.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx,
  frontend/src/components/WhatsNew.jsx, docs/research_ideas.md, docs/feature_ideas.md, docs/agent_handoff.md,
  docs/hq/status/builder.json.

## 2026-11-22 ~03:45 UTC (Polish walk, key `polish`): share cards word big-move calls correctly
- Big-move ("volatile") calls are graded on |theme| - |S&P|, but share cards said "ahead of the S&P 500 by 1.7 pts ...
  in the direction called" (live: SMH fell 3.6% vs S&P -1.9%). Now "moved 1.7 pts more than the S&P 500" and "How much
  more it moved than the S&P 500, up or down". New json field `vs_label`. Grades/grading unchanged.
- Files: backend/v4/share.py, backend/v4/tests/test_v4.py, frontend/src/components/WelcomePage.jsx,
  frontend/src/components/MyCallsPage.jsx, docs/polish_log.md, docs/agent_handoff.md, docs/hq/status/polish.json.

## 2026-11-22 ~05:30 UTC (Builder, key `builder`): Agent HQ says when each agent next runs, and dates old messages
- No HQ messages from Murad (hq_messages empty); no "proposed" items left in feature_ideas.md. Finishing touch on HQ.
- Found: the table said Builder runs "9:51am-9:51pm" and polish "8:23am-11:23pm", but both run every 3 hours around the
  clock (scheduled tasks updated Nov 14). The meeting thread showed only a weekday, so the CTO's Nov 13 note read
  "Fri 4:40 PM", like last night. "Needs you" items had no age, and the composer only said "next run".
- docs/hq/agents.json: each scheduled agent now carries `cron`, the same string as its scheduled task (Denver time);
  Builder/polish labels fixed. If you change a scheduled task's time, change its `cron` here too.
- backend/v4/hq.py: `next_run(cron)` (5-field cron, CRON_TZ prefix, ranges/steps/lists, dom/dow OR rule, DST via
  zoneinfo) -> roster `next_run` (UTC ISO); `needs` items carry `at` (the status file's updated_at).
- HQPage.jsx: "next run in 3 h (12:51 AM)" chip on each card (viewer's time zone); thread times "Today / Yesterday /
  Fri / Nov 13, 4:40 PM"; need items show their age; the composer says when the chair checks next and the chosen
  agent's next run (CTO: only in the build chat).
- Tests: test_hq_next_run_reads_each_agents_cron_in_its_own_time_zone (values match the scheduler's next_run_at);
  test_hq_board_and_messages checks next_run and needs `at`.
- Files: backend/v4/hq.py, backend/v4/tests/test_v4.py, frontend/src/components/HQPage.jsx, docs/hq/agents.json,
  docs/agent_handoff.md, docs/hq/status/builder.json.

## 2026-11-22 ~06:45 UTC (Polish walk, key `polish`): Brain page units and the 49-vs-48 count
- Brain page "Just graded by the market" now says "-0.3 pts" (a difference of returns), not "-0.3%"; My beliefs Image
  share card on up/down calls says pts too (shareCard.js shrinks wide values to fit). The PBO paragraph explains why
  it compares 48 ways when the luck check says 49 (the old #1's peeked score is left out). Wording/units only.
- Files: frontend/src/components/BrainPage.jsx, frontend/src/components/MyCallsPage.jsx, frontend/src/lib/shareCard.js,
  docs/polish_log.md, docs/agent_handoff.md, docs/hq/status/polish.json.

## 2026-11-22 ~08:45 UTC (Builder, key `builder`): Close Call's brain record shows its graded questions
- No HQ messages from Murad (hq_messages empty); no "proposed" items in feature_ideas.md.
- Found: the record said "15 questions graded ... right side 73%", but its list was the 12 newest-ASKED questions, and
  the brain asks ~11 a day 5+ days out, so all 12 were open. None of the right/wrong answers behind the 73% ever showed.
- yesno.brain_questions(graded=True): the brain's graded questions, latest expiration first. scorecard returns them as
  `graded_recent` (beside the unchanged `recent`).
- YesNoPage: record card now has "Latest graded" (right/wrong, close, "Its side was right on X of these N") and
  "Waiting for the close" (open ones only, 3 shown when graded ones exist). WhatsNew line.
- Not changed: grading, odds, the brain's lean, research gates. Test: the scorecard test checks graded_recent order,
  users excluded, empty case.
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, frontend/src/components/YesNoPage.jsx,
  frontend/src/components/WhatsNew.jsx, docs/agent_handoff.md, docs/hq/status/builder.json.
- Noticed, not changed (unsure): weekend option IVs read high (SPY ATM 42% on Friday-close quotes; a 7-calendar-day
  clock gives ~35%). Alpaca's snapshot IV convention isn't documented here, so I left Price Check / "How far it could
  move" wording alone. Odds are unaffected (they use sigma*sqrt(T) consistently).

## 2026-11-22 ~09:45 UTC (Polish walk, key `polish`): Story hook keeps "potentially" on a deal size
- Live Story hook said "$45 billion" for an article's "deal potentially valued at $45 billion". movers._hedged now also
  carries a soft hedge (potentially/possibly/could/may/might, up to 3 words before the number) onto the hook:
  "Potentially $45 billion". Re-applied on read, so cached stories change too. No other behavior changed.
- Files: backend/v4/movers.py, backend/v4/tests/test_v4.py, docs/polish_log.md, docs/agent_handoff.md,
  docs/hq/status/polish.json.

## 2026-11-22 ~11:30 UTC (Builder, key `builder`): option volatility measured from the quotes' own close (no weekend inflation)
- No HQ messages from Murad (hq_messages empty); no "proposed" items in feature_ideas.md. Followed up my own note from
  the last run (weekend SPY IV 42%).
- Found: off-hours, Alpaca's snapshot IV divides Friday's closing prices by the time left from NOW. Live Sun Nov 22:
  SPY Nov 27 ATM read 42% (Price Check "Expensive", 2.45x realized); re-reading the same mids from Friday's close gives
  ~36% (call $695 35%, put $695 37%, $690 call 37%, $700 call 34%). The feed was also inconsistent across contracts
  (the $695 call 47% vs the put 37%).
- market.py: `last_close_dt`, `quote_years(exp)` (from now while open, else from the last session's close, to the
  expiration's close; NYSE holidays / 1pm early closes 2026-27 listed in NYSE_HOLIDAYS / NYSE_EARLY_CLOSE: extend them
  for 2028).
- yesno.py: `quote_iv` (one contract's IV from its own two-sided mid) and `atm_quote_iv`; `expected_move(...,
  quote_years=)` reads the ATM vol off the quotes on that clock and the range uses the same clock (so the range is
  what the prices carry; only the yearly-vol label and the implied/realized ratio change). Odds, lean, trade pricing,
  grading untouched.
- pricecheck.py: `_atm(..., years_fn)` and the contract's own IV from its quotes (feed IV is the fallback); off-hours
  line "these are the Fri Nov 20 closing quotes, so volatility is measured from that close"; when there's no realized
  history the card now says the IV instead of "No implied volatility". log_daily uses the same clock.
- Test: test_option_vol_uses_the_quote_clock_so_a_weekend_does_not_inflate_it.
- Files: backend/v4/market.py, backend/v4/yesno.py, backend/v4/pricecheck.py, backend/v4/tests/test_v4.py,
  docs/agent_handoff.md, docs/hq/status/builder.json.

## 2026-11-22 ~13:00 UTC (Polish walk, key `polish`): Close Call doesn't read odds off calls and puts that don't fit together
- Live NVDA Nov 27 $130 read "51%" from the $127/$133 call spread while its put spread cost $3.85 (YES + NO $6.91 on a
  $6 spread): calls and puts set at different stock prices (~$126 vs $129.17), inside quotes_out_of_step's 2% dividend room.
- yesno.calls_puts_disagree(chain, k1, k2, years) -> stale (one-vol answer, no smile, plain source text).
  listed_costs gains `out_of_step`; YesNoPage's "What a real order would pay" box says the quotes don't fit together.
- Builder: quotes_out_of_step's 2% room is untouched; the new check is dividend-free (parity sum). Still open: NVDA Dec 4
  $125 smile reads 46% with the stock at $129.17 (skew_odds' parity guard is borderline there).
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, frontend/src/components/YesNoPage.jsx, docs/polish_log.md,
  docs/agent_handoff.md, docs/hq/status/polish.json.

## 2026-11-22 ~14:30 UTC (Builder, key `builder`): Close Call reads weekend quotes' volatility at the price they were set at
- No HQ messages from Murad (hq_messages empty); no "proposed" items in feature_ideas.md. Took polish's open note
  (NVDA Dec 4 $125 reading 46% with the stock at $129.17).
- Found (live, public price_check per contract): NVDA's Dec 4 quotes were set as if NVDA were ~$125.8 (parity at
  every strike 120-132 agrees). Read at the last price $129.17, every put looked dear (~1.19 vol) and every call cheap
  (~0.81). skew_odds' parity allowance (0.1 sd at the fit's vol) was computed on the puts' inflated vol, so it passed
  the very gap it measured, and the all-puts "smile" read $124 56%, $125 46%, $126 42% (14 points for $2).
- yesno.quotes_own_price(chain, spot, level, years, strikes=None): the quotes' own stock price (parity), the vol they
  price once read at that price (call and put at the line's strike, must agree within 15%), and `out` (gap over 0.1 sd
  at that vol + mid noise; no dividend room). None for junk quotes (per-strike parity prices that disagree).
- skew_odds: parity allowance uses that vol (falls back to the fit's). quote(): when `out`, the one-vol answer uses the
  quotes' own vol instead of the feed's (NVDA 1.22 -> ~1.03) and names the price ("set as if NVDA were near $125.78,
  not its last price $129.17"); the call/put "disagree" label still wins when that check fires. The spread reading is
  NOT forced stale by this (quotes_out_of_step's 2% dividend room is unchanged), so dividend payers behave as before.
- On the live quotes: NVDA Dec 4 now $124 55%, $125 54%, $126 52%, $128 49%, $130 45%. SPY Nov 27 not flagged.
- Test: test_yesno_quotes_set_at_another_price_read_their_vol_at_that_price. Not changed: grading, lean, research gates.
- Files: backend/v4/yesno.py, backend/v4/tests/test_v4.py, docs/agent_handoff.md, docs/hq/status/builder.json.

## 2026-11-22 ~15:45 UTC (Polish walk, key `polish`): Story hook "Up 10% supply" -> "Forecast: Supply up 10%"; Brain ranker date wording
- movers._hook now runs _reordered ("Up 10% supply" -> "Supply up 10%") and _forecast ("Forecast:" when the article
  only gives the number after projects/expects/forecast/guidance/outlook in its sentence). Read-time, so cached stories
  change too. Existing hedge rules (_hedged) unchanged.
- BrainPage.jsx: ranker card says "last retrained <date>" and the nightly-runs note no longer says the ranker "has
  shaped the #1 since <date>" (that field is its latest refit, not its start).
- Files: backend/v4/movers.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx, docs/polish_log.md,
  docs/agent_handoff.md, docs/hq/status/polish.json.

## 2026-11-22 ~16:35 UTC (Meeting chair, key `chair`): REQUEST FROM MURAD for the Builder (`builder`)
- Murad asked (in the chair chat, so it is not in hq_messages): "add a search feature if the user is looking for
  something specific." Builder: take this as your next feature. Suggested scope: one search box that finds stories on
  the News page (company, ticker or topic) first; extend to tickers/ideas elsewhere if it fits. Plain-word empty state.
- When done, answer it in docs/hq/status/builder.json replies (re: "Search feature (via chair)") so Murad sees it in HQ.

## 2026-11-22 ~17:10 UTC (Builder, key `builder`): News search (Murad's request via the chair)
- News page (/trending) gets a search box: company name, ticker or topic. ?q= in the URL keeps it shareable/back-able.
- Searches this week's "Moving now" stories: new kv `movers:archive` (movers._archive / archived(): every story Claude
  picked, last 7 days, max 150, story text only; prices re-read when shown). Written only when a fresh AI feed is stored.
- backend/v4/newssearch.py: search(q) -> {company, stories, headlines, days}. A word must start a story word ("chip"
  finds "chipmakers"); stories that move the searched company rank first. Company = a ticker typed as one ($nvda,
  NVDA, or lowercase when it's in this week's stories / no story uses the word: "gold" stays a topic, not Barrick's
  GOLD), or a company in this week's stories whose name starts with the search ("nvidia"). Company card adds its
  latest headlines from Alpaca news (symbols=, cached 20 min/ticker). No Claude call.
- movers.story() also opens archived stories (still only curated ones, never arbitrary text).
- Route GET /v4/movers/search?q= (public, like /v4/movers). Frontend: NewsSearch.jsx, TrendingPage.jsx, api.searchMovers.
- Test: test_news_search_finds_this_weeks_stories_by_company_ticker_or_topic. Archive starts filling after deploy, so
  search only covers stories picked from then on (plus today's feed).
- Files: backend/v4/movers.py, backend/v4/newssearch.py, backend/v4/router.py, backend/v4/tests/test_v4.py,
  frontend/src/components/NewsSearch.jsx, frontend/src/components/TrendingPage.jsx, frontend/src/lib/api.js,
  docs/agent_handoff.md, docs/hq/status/builder.json.

## 2026-11-22 ~18:10 UTC (Polish walk, key `polish`): News search doesn't pass off a topic word as a company
- Live: "gold" -> Gold.com card, "car" -> Avis, "now" -> ServiceNow, presented as the answer; "apple"/"tesla" found
  nothing (company lookup only covered this week's stories).
- newssearch._company: lowercase non-ticker-looking word not in this week's stories -> company gets guess=True;
  NewsSearch.jsx shows 'No stories mention "<q>" ... here it is in case you meant the company' above the card.
  New newssearch._KNOWN name map (apple -> AAPL etc.; no topic words). Builder: search() return shape only gains
  company.guess; nothing else changed.
- Files: backend/v4/newssearch.py, backend/v4/tests/test_v4.py, frontend/src/components/NewsSearch.jsx,
  docs/polish_log.md, docs/agent_handoff.md, docs/hq/status/polish.json.

## 2026-11-22 ~19:00 UTC (Research scout, key `scout`): idea 21 vol-of-vol; ideas 18-20 recorded; composite proposal
- No HQ messages from Murad (hq_messages empty for all/scout).
- Recorded results (run 17:21 UTC, n=2,703, full coverage): 18 cvvol -0.48% (t -1.55), 19 hi_age -0.18% (t -0.53),
  20 ldvol +0.81% (t 2.90, t_nw 1.43, under the 3.28 bar; a weaker copy of amihud). None is a candidate.
- Idea 21: `vov` (Baltussen, van Bekkum & van der Grient 2018) = CV of 12 monthly realized vols over ~1 year.
  market.vov / vov_features, market.features, nn.make_features (not MODEL_NUMERIC), research.FEATS / DIRECTIONAL /
  NEUTRAL (0.35), enrich backfill (as of each pick's date), rule `steady volatility (-z_vov)`. Luck bar now 50 tries.
- Part B proposal in docs/feature_ideas.md: equal-weight composite of research rules chosen inside each fold
  (reporting only). Gates untouched.
- Test: test_vol_of_vol_rule_and_enrich_backfill. Files: backend/v4/market.py, research.py, nn.py, tests/test_v4.py,
  docs/research_ideas.md, docs/feature_ideas.md, docs/agent_handoff.md, docs/hq/status/scout.json.

## 2026-11-22 ~20:30 UTC (Builder, key `builder`): Research "many weak signals, one vote" (feature_ideas 2026-11-22)
- No HQ messages from Murad. Built the scout's composite proposal; reporting only (no gate, `_passes`, fit_production,
  ranker v2 or grading change).
- research.run(): per walk-forward fold, `composite_members(train, rules)` picks fixed rules on that fold's TRAINING
  calls only (training lift > 0, plain t >= COMP_MIN_T 2, at most COMP_MAX 8 by t, skip a rule whose training #1 matches
  a kept rule's > COMP_OVERLAP 70%). Candidates: every fixed rule except the two app rows and provisional rules. Test
  calls: `composite_scores` = mean of each kept rule's within-belief z-scored scores; no members -> app no-look-ahead
  (pit) #1. New result "equal-weight composite (chosen in-fold)" (all usual metrics, vs-app, joins the luck bar
  tries and PBO pool), `out["composite"]` (members kept per fold, folds, fallback_folds, cutoffs),
  `luck.composite` = composite_summary (vs median and best single fixed rule).
- BrainPage.jsx: luck card paragraph "Many weak signals, one vote." (between PBO and "New, or the app restated?").
  Shows after the next research run.
- Tests: test_equal_weight_composite_beats_two_weak_signals_and_picks_rules_on_training_calls_only,
  test_composite_in_run_never_keeps_a_rule_that_only_works_in_its_own_test_period.
- Files: backend/v4/research.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx,
  docs/feature_ideas.md, docs/agent_handoff.md, docs/hq/status/builder.json.
- First live run (20:36 UTC, n=2,703): composite lift +0.57% (t 1.71, t_nw 0.99), 3 of 4 stretches, beats 21 of 34
  singles; best single negative coskewness t_nw 3.12. Members mostly momentum-family (12-7, resid, frog 5/5). Verdict
  wording on the Brain page adjusted to "short of the best one, so averaging hasn't added an edge of its own yet".

## 2026-11-22 ~21:00 UTC (Weekly brain upgrade, key `brain`): nothing built (docs only)
- Ranker v2 switched off at the 20:37 refit through the unchanged gate (net +1.19%, risk-matched beat 53.7% < stored
  app 54.2%). Not a bug. Details and the checks behind "no clear win" in docs/brain_upgrades.md.
- Files: docs/brain_upgrades.md, docs/hq/status/brain.json, docs/agent_handoff.md. No code changed.

## 2026-11-22 ~21:45 UTC (Daily polish, key `polish`): nationality capitals in "other side" beliefs; ranker-off wording
- seeder._PROPER now matches frontend lib/text.js PROPER (added european, spanish, korean, british, ... ; app list
  lost 'silicon'). Only affects how new "I don't think ..." opposites are capitalised; which hunches get one is unchanged.
- BrainPage PBO line says the ranker is switched off when skill.ranker.active is false. No research/gate change.
- Files: backend/v4/seeder.py, backend/v4/tests/test_v4.py, frontend/src/lib/text.js,
  frontend/src/components/BrainPage.jsx, docs/polish_log.md, docs/agent_handoff.md, docs/hq/status/polish.json.

## 2026-11-22 ~23:10 UTC (Builder, key `builder`): Agent HQ thread labels, newest replies, reachable message box
- No HQ messages from Murad (hq_messages has never had a row; logs show him opening /hq on Nov 22 but no POST). Local
  check: posting from the page works. On a phone the message box sat under 12 "Needs you" items, 9 agent cards and the
  thread, so it was several screens down.
- hq.board(): agent replies now come from `newest_replies` (sorted by `at`, newest 10; it took replies[-10:], which
  drops the newest once a status file that lists newest first passes 10). Each reply gets `reply_to(re)`:
  `re_id` + `re_body` (first 80 chars of Murad's message) when `re` is an id (12, "12", "#12"); `re` = topic text;
  `re` = None for "(no new messages)". needs[] sorted newest first.
- HQPage.jsx: "Write to the team ↓" button at the top (scrolls to and focuses the box); Needs you shows the newest 4 with
  "Show all N"; reply labels read 're your “...”', 're: <topic>' or 'update' instead of 're #(no new messages)'.
- Agents: keep writing `re` as Murad's message id when you answer one of his HQ messages; it now quotes him.
- Test: test_hq_thread_labels_replies_and_keeps_each_agents_newest.
- Files: backend/v4/hq.py, backend/v4/tests/test_v4.py, frontend/src/components/HQPage.jsx, docs/agent_handoff.md,
  docs/hq/status/builder.json.

## 2026-11-23 ~00:50 UTC (Daily polish, key `polish`): range-bound beliefs say their ideas take a side; Brain feed wording
- Frontend only. StrategyCard: note under the summary when interpretation.direction is neutral and picks are
  bullish/bearish. BrainPage: "Expecting a range" for neutral shared beliefs; health line's "Last learning round" uses
  the later of health.learning.at and the newest news event when the round was ok.
- Not done (build chat, M): real range strategies for neutral beliefs; when that lands, the StrategyCard note's
  condition (picks taking a side) hides it automatically for neutral picks.
- Files: frontend/src/components/chat/StrategyCard.jsx, frontend/src/components/BrainPage.jsx, docs/polish_log.md,
  docs/agent_handoff.md, docs/hq/status/polish.json.

## 2026-11-23 ~02:30 UTC (Builder, key `builder`): Brain page luck check "At a glance"
- No HQ messages from Murad. Frontend only; no research, gate, ranker or grading change.
- New frontend/src/lib/luck.js `luckGlance(skill, forward)`: one row per check (ahead of other ideas, clear of luck
  plain, clear of luck counting overlap, not carried by a few huge calls, holds through time, PBO, real-time calls),
  each pass / partly / not yet / too early, plus a one-line verdict. All rows judge ONE version: the live ranker's oos
  when active, else our #1 rebuilt without the peek (ranker.old_pit) when the stored one flatters, else as stored.
- BrainPage luck card: the glance sits under the intro; the detail paragraphs (Still filling in ... New, or the app
  restated?) are behind "How each check works" (collapsed by default). New paragraphs added inside that block stay
  inside the toggle. "Without the extremes" adds the no-peek capped lead and top-10 share (live: 10 best calls are 73%
  of the no-peek lead vs 27% stored), so "the lead is broad" no longer stands alone.
- Test: frontend/src/lib/luck.test.mjs (added to `npm test`).
- Files: frontend/src/lib/luck.js, frontend/src/lib/luck.test.mjs, frontend/package.json,
  frontend/src/components/BrainPage.jsx, docs/agent_handoff.md, docs/hq/status/builder.json.

## 2026-11-23 ~03:40 UTC (Daily polish, key `polish`): wrong-company story links dropped; PBO glance wording
- backend/v4/movers.py: new `story_url(url, tickers)`; /v4/movers items and News search drop a link that is a stock
  quote page for a ticker the story doesn't touch (fiscal.ai linked an Enphase story to O-I Glass). Nothing else in
  the feed changes. frontend/src/lib/luck.js: PBO glance row states the 10% pass bar.
- Files: backend/v4/movers.py, backend/v4/newssearch.py, backend/v4/tests/test_v4.py, frontend/src/lib/luck.js,
  docs/polish_log.md, docs/agent_handoff.md, docs/hq/status/polish.json.

## 2026-11-23 ~05:30 UTC (Builder, key `builder`): Brain page scorecard headline shows the no-peek numbers
- No HQ messages from Murad. Frontend only; no research, gate, ranker or grading change.
- The honest scorecard's two big tiles (53% beat the S&P, +1.2 pts vs other ideas) were the stored #1 on graded
  practice calls, which carry the look-ahead peek, while the paragraph below said to read them as too generous and the
  luck glance judged the no-peek rebuild. New `scoreHeadline(sk)` in frontend/src/lib/luck.js: when luckSubject picks
  ranker.old_pit (stored flatters), the tiles show old_pit beat / avg / lift on research's test calls (live: 52%,
  +1.5 avg, +0.5 pts on 2,703) with a small line giving the stored numbers "with the peek"; otherwise unchanged
  tiles. The edge tile is green only when clear of luck (overlap-counted t >= bar), so a +0.5 that isn't clear of luck
  is no longer green. If the ranker goes live or the peek gap closes, the tiles fall back to the stored graded picks.
- Test: frontend/src/lib/luck.test.mjs (scoreHeadline cases).
- Files: frontend/src/lib/luck.js, frontend/src/lib/luck.test.mjs, frontend/src/components/BrainPage.jsx,
  docs/agent_handoff.md, docs/hq/status/builder.json.

## 2026-11-23 ~06:50 UTC (Daily polish, key `polish`): "How sure are you?" no longer reads backwards on bearish calls
- No HQ messages from Murad. Frontend wording only; no grading, research or gate change.
- HowSure prompt/locked line now say "the area your idea is about (its theme) does worse than the S&P 500" instead of
  "your idea does worse" (which read as "your call fails"). New glossary term 'theme' in Term.jsx matches
  grader._group_scores (fund(s) among the ideas, else the same-direction ideas on average). If the grading benchmark
  changes, update that glossary line.
- Files: frontend/src/components/chat/HowSure.jsx, frontend/src/components/ui/Term.jsx, docs/polish_log.md,
  docs/agent_handoff.md, docs/hq/status/polish.json.

## 2026-11-23 ~07:40 UTC (Meeting chair, key `chair`): REQUEST FROM MURAD for the Builder (`builder`), CORRECTS the Nov 22 search ask
- Murad (chair chat, not in hq_messages): the News search shipped in 98ae87f only finds stories we already have. What he
  wants: "not search what we already have but be able to search something new, let the AI do its magic and create the
  custom story." So: a user types any company, ticker or topic (e.g. "uranium", "Costco earnings"), the app pulls fresh
  headlines/data for it and the AI writes a new story in the same Story-mode cards (hook, helps/hurts, move vs S&P,
  "See how to invest in this"), even when nothing in this week's feed covers it.
- Builder: take this as your next feature. Keep the existing search results as the fast first answer and add
  "Make a story about this" (or do it automatically when nothing is found). Facts only from real fetched headlines/prices;
  if there's nothing real to go on, say so plainly. Keep AI cost small: cache by query for the day and cap stories per
  user/day. No real money involved.
- When done, answer in docs/hq/status/builder.json replies (re: "Custom AI story from search (via chair)"). The reel
  agent's promo v2 shows the old search; the chair will ask for a v3 once this is live.
- ~07:42 UTC addendum from Murad: he wants it tested and then a reel of it. Builder: after the deploy is live, test it
  on the live site (Playwright on https://marketplayground-web.onrender.com News tab: search 2-3 things not in this
  week's feed, check the story cards render with real facts and nothing breaks on phone width) and say in your reply
  what you tested. Then write a line here: "custom story LIVE, tested".
- Reel agent (`reel`): on your next run, if the Builder's status/handoff says the custom story is live and tested, make
  "News page promo v3" FIRST: real footage on the live News tab of typing something new (pick a query that isn't in
  this week's feed, e.g. a well-known company or topic), the AI making the story, and swiping through its cards. Same
  style as v2 (voiceover, brand-blue captions, invited-only end card, no app link, no user idea created). Send it with
  TikTok + Instagram captions, then do the regular Market's open reel. If it isn't live yet, say so in your reply.

## 2026-11-23 ~08:50 UTC (Builder, key `builder`): "Make a story about this": a fresh AI story for anything searched
- Murad's request via the chair (Nov 23 07:40 entry above). No HQ messages from Murad in hq_messages.
- New backend/v4/customstory.py + GET /v4/movers/custom?q=. Company searches ("nvidia", "$NVDA", "Costco earnings")
  use that company's own recent headlines (extra words like "earnings" put matching headlines first); topics
  ("uranium") ask Haiku for 3-5 related tickers (validated with asset_info), fetch their tagged news plus the general
  feed and this week's archive, and keep only headlines that contain the search words. Max 8 sources, max 14 days old.
  Then one Haiku call writes title, hunch, companies and the Story-mode fields; figures must pass movers._grounded,
  hook goes through movers._hook, tickers through asset_info; the item lists the headlines it `used`.
- Nothing real found: says so (code no_news, remembered an hour per process), writes nothing.
- Cost: one story per subject per UTC day in kv_cache (`custom:v1:<day>:<hash>`), shared by everyone; a new story
  counts against MP_CUSTOM_STORY_PER_DAY (5) per account, or per IP when signed out (`custom:n:` keys), and
  MP_CUSTOM_STORY_DAILY_MAX (150) for the app. Cached stories are free. custom:% rows older than 3 days are deleted.
- Frontend: NewsSearch `MakeStory` button (primary inside "No stories about X", secondary under other results).
  Success shows a "Made for your search" MoverCard (blue border, "Show the N headlines it's based on") and opens
  Story mode at once. StoryViewer takes `preloaded` data; custom stories say "Your story" on the hook and add a
  "Where this comes from" card listing the real headlines. MoverCard takes `storyData` / `openNow`.
- Test: test_custom_story_from_search_is_grounded_cached_and_capped.
- Files: backend/v4/customstory.py, backend/v4/router.py, backend/v4/tests/test_v4.py, frontend/src/lib/api.js,
  frontend/src/components/NewsSearch.jsx, frontend/src/components/MoversFeed.jsx,
  frontend/src/components/StoryViewer.jsx, docs/agent_handoff.md, docs/hq/status/builder.json.
