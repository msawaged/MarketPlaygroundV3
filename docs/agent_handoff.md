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
