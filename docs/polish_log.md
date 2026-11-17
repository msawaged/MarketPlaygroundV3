# Polish log

Daily rough-edge fixes found by walking the app like a new user on a phone (390x844). Newest at the bottom.

## 2026-11-05

Walked /welcome, /trending, /live, /story, /account, /brain on the live site. No page errors, no 4xx/5xx, no horizontal overflow.

Found:
- Brain page, strategist leaderboard: "live: +2.1 pts on 1999" reads like the year 1999 (it is 1,999 graded calls).
- Brain page, smarter #1 pick card: "Tested on 2707 past calls" had no thousands separator, unlike every other count on the page.
- Brain page, health line said "Last market grading 23h ago" while the activity feed right below said "The market graded 118 picks 13h ago". The line only read the daily grade-and-train job's timestamp; the hourly catch-up grades picks too (/v4/brain: health.grading.at 2026-11-04 22:48 UTC, latest graded event 2026-11-05 08:18 UTC).
- Brain page, "It grades itself": the "On probation" pill wrapped onto two lines at 390px.
- Moving now (/trending): every "What it could mean" line ended in a double period ("...next year..") because the hunch already ends with one and the UI added another.

Changed:
- Leaderboard shows "live: +2.1 pts / over 1,999 calls" (two short lines so strategist names don't get truncated).
- Counts use thousands separators; probation/rejected pills never wrap.
- Health line uses the latest of the daily job and any graded activity, so it matches the feed; it still flags a daily run that didn't finish.
- Hunch text has trailing punctuation stripped before the single period is added.

Checks: vite build passes, payoff/figures tests pass, backend tests 98 passed. Verified locally against the live API with mobile screenshots.

## 2026-11-05 (reel and story pass)

Found:
- Story figure card showed a red "-99%" for Evergy's "350-400 MW" -> "About 2.25 GW" (units ignored, range misread, GW unknown), with bars drawn backwards. It went into the daily reel.
- Recorded reels opened on the "Writing the story..." spinner and a blank frame; the script's trim point was measured from the wrong clock.
- The big hook was clipped at 28 chars with "…", which can flip its meaning: "Credit stress looks contained" became "Credit stress looks…" in today's reel.
- A long single word in the hook ("Semiconductors") overflowed the 6xl hook, and descenders were cut by the gradient text clip.

Changed:
- frontend/src/lib/figures.js: figures parse value + unit (SI prefixes for W/Wh, scale words, currency, %); the badge and bars only compare like units; % changes show in points. Tests in figures.test.mjs (npm test).
- scripts/make_reel.js trims from the page's own __reelStart (+0.3s LEAD_IN), and fails fast on window.__reelError instead of a 90s timeout.
- backend/v4/movers.py: hook shown whole (<=40 chars, <=5 words) or replaced by the headline's number / "Moving now", never clipped. Test added.
- Hook text size steps down for long words; bottom padding keeps descenders.

Checks: vite build passes, payoff/figures tests pass, backend tests 98 passed. Verified with mocked stories in mobile screenshots and a live test recording.

## 2026-11-05 (second pass: signed-in screens)

New: `scripts/dev_offline_server.py` runs the API with a fake Claude and synthetic prices for real tickers, so chat picks, option cards and the practice portfolio can be walked locally without keys (refuses to start if DATABASE_URL is set).

Found:
- Practice shares were whole shares only, with a minimum of 1. The card said "You buy about $1,000 of NVDA (5.41 shares)" but the trade bought 5 shares ($925). $1,000 of a $5,000 stock like BKNG bought 1 share ($5,000), contradicting "Any amount, even $10".
- When the practice price lookup (Yahoo) failed, a trade filled at a made-up $100 (hard-coded fallback). It also used a different feed from the card (Alpaca).
- Option spread cost $245 on the card but $246 in Portfolio: the card rounds each leg to cents, practice used unrounded model prices.
- Payoff chart axis labels showed padded values no price can reach (+$487 / −$277 for a spread whose max is +$455 / −$245).
- Shares chart legend said "At expiration"; shares don't expire.
- After a queued trade: "Find it under Practice", but the tab is called Portfolio (the Account page tile also said Practice).

Changed:
- Practice stock trades are fractional (4 decimals), so the amount bought matches the card; amounts too small for any share are refused clearly. Portfolio shows "5.4054 shares".
- Practice prices come from the card's feed first, then Yahoo, then the last real cached price; never an invented one (the trade is refused instead).
- Option legs are priced in whole cents in practice, like the card.
- Chart labels the real best/worst P/L; the shares legend reads "When you sell"; Portfolio naming is consistent.
- Tests: fractional shares (incl. $5,000 stock) and "no made-up price".

Checks: vite build passes, backend tests 100 passed; verified locally (card $254 = Portfolio $254; NVDA $1,000 → 5.4054 shares).

## 2026-11-06

Walked /welcome, /trending, /live, /story, /account, /brain on the live site at 390x844. No page errors, no 4xx/5xx, no horizontal overflow (only a blocked third-party request from the sandbox proxy).

Found:
- Welcome "What's new" claimed "Smarter #1 pick: beats the S&P more often than the old way". The live scorecard (/v4/brain skill.ranker.oos) says otherwise for the ranker live since Nov 6: beat 52.0% vs old way 52.3% on 2,703 unseen calls. Its real edge is vs our other ideas (+0.75 pts, t 2.23, vs +0.37) and risk-adjusted (53.9% vs 52.9%), not the raw S&P beat rate.
- Moving now (/trending) footnote said "vs S&P" is measured "30 days after it was suggested"; ticker_stats grades at LABEL_DAYS = 90 (the Brain page says 90 days). The footnote also showed when no card had a "vs S&P" figure.
- Chat pick card: "Track record ... after 3 months", but its tap-to-explain tooltip said "graded automatically after 30 days".

Changed:
- What's new line no longer makes a comparative claim: "Smarter #1 pick, tested on past calls it never saw (live scorecard on the Brain page)".
- /v4/trending returns label_days; the footnote uses it and only shows when a "vs S&P" figure is on screen.
- Track record tooltip: "graded automatically 90 days (about 3 months) after each pick".

Checks: vite build passes, payoff/figures tests pass, backend tests 106 passed.

## 2026-11-07

Walked /welcome, /trending, /live, /story, /account, /brain on the live site at 390x844: no page errors, no 4xx/5xx,
no horizontal overflow (only a sandbox-proxy-blocked third-party request).

Found:
- Brain page "Just learned" showed the opposite side of news hunches with names and acronyms lower-cased:
  "I don't think microsoft pulling back on AI computing deals...". In the live DB, 49 "I don't think aI ..." beliefs,
  plus "uK", "iran", "tesla's", "ukraine's", "european", "microsoft" (seeder.news_beliefs lower-cased the first letter blindly).
- "Just graded by the market" showed the signed call result next to the stock: "FXA bearish ✗ -3.8% vs S&P 500".
  A reader sees FXA lagging the S&P by 3.8% (a win for a bearish call) next to a red ✗; in fact FXA beat the S&P.
- The ranker box said "live since Nov 7" (yesterday "since Nov 6"): the date is the last daily refit, not when it went live.

Changed:
- seeder._lower_first: keeps acronyms, possessives, multi-word names, nationalities, a short list of common names, and
  any word written capitalised mid-sentence in the story's own summary/reasons; lower-cases the rest ("a", "the" too). Test added.
- /v4/brain graded items carry stock_vs_market (ret - spy_ret); the feed shows it for bullish/bearish as
  "stock vs S&P 500" (FXA bearish ✗ +3.8%), and labels volatile calls "size of move vs S&P".
- Ranker box: "retrained Nov 7".

Checks: vite build passes, payoff/figures tests pass, backend tests 107 passed.

## 2026-11-08

Walked /welcome, /trending, /live, /story, /account, /brain on the live site at 390x844: no page errors, no 4xx/5xx,
no horizontal overflow (only a sandbox-proxy-blocked third-party request). Focused on today's new Brain boxes.

Found:
- Welcome "What's new" still said "Smarter #1 pick, tested on past calls it never saw", but /v4/brain now reports
  skill.ranker.active = false (after the rank-0 fix, ranker v2 lost to the real #1: lift +0.74 vs old way +1.49 pts).
- "When the AI is most sure" promised live results by confidence "below", but the forward-test box never rendered
  forward.by_confidence. It also said "beat the average of the other ideas"; research/_forward lift is #1 minus the
  average of ALL the belief's ideas (the #1 included).
- Forward test card: "7 days · 108 calls" read like a duration; "since 2026-10-28" wrapped mid-date at 390px; "+1.1 pts"
  shown green with t = 1.24; footer pointed to "the 90-day column", which doesn't exist yet.
- Confidence badge tooltip claimed the most confident #1 picks "beat the S&P 500 more often" than the least confident:
  true by 1 pt raw (54.8% vs 53.8%) but false risk-adjusted (54.4% vs 55.4%). The robust claim is the lift (+2.5 vs +0.9, t 4.5).

Changed:
- WhatsNew: dropped the "Smarter #1 pick" claim; added the confidence badge and the live forward test; updated Nov 8.
- BrainPage forward test: "After N days" + call count, date as "Oct 28", "vs our average idea", t-stat note
  ("could still be luck" below t 2; green only when t >= 2), by-confidence row (High/Medium/Low) from
  forward.by_confidence, and the date the first live calls reach 90 days. Confidence-box wording fixed.
- StrategyCard confidence tooltip states the lift claim, "a guide, not a promise".

Checks: vite build passes, payoff/figures tests pass, backend tests 113 passed. Verified with a mocked /v4/brain
(30-day checkpoint + by_confidence) at 390px.

## 2026-11-09

Walked /welcome, /trending, /live, /story, /account, /brain on the live site at 390x844 at ~21:24 UTC.

Found (outage):
- Every API call failed: the backend returned 502 on /health, /v4/brain, /v4/movers, /v4/trending (the browser showed
  them as CORS errors because Render's 502 page has no CORS headers). Trending, Story, Live and Brain were empty.
- Render: the 21:00 deploy of d856c72 timed out ("No open ports detected"); the instance logged "Waiting for application
  startup." and never finished, and the rollback instance hung the same way. Disk-backed service, so no old instance
  kept serving: down from ~21:00 to ~21:40 UTC.
- pg_stat_activity: an ad-hoc read-only SELECT (correlated subqueries over outcomes/picks, run through the Render
  Postgres query tool, no application_name) had been running 44 min. Startup's `ALTER TABLE picks ADD COLUMN spy_entry`
  (a migration that runs on every start and normally fails "already exists") queued for an ACCESS EXCLUSIVE lock behind
  it, and every later statement on picks (startup `CREATE INDEX IF NOT EXISTS`, all reads) queued behind the ALTER.

Changed:
- Cancelled the runaway SELECT (pg_cancel_backend); the backend came back within a minute.
- backend/v4/db.py ensure_schema: on Postgres, migrations whose column already exists are skipped (information_schema
  lookup, no lock); all schema/migration DDL runs with `SET LOCAL lock_timeout = '10s'`; if the one-pass schema fails on
  Postgres it retries statement by statement and logs skips instead of hanging or crashing. Reproduced the hang on a
  local Postgres 16 (old code still blocked after 25s behind an open reader; new code 0.0s) and checked a missing
  column is still added. Test added for the migration parser.

Checks: backend tests 118 passed. No frontend change.

## 2026-11-10

Walked /welcome, /trending, /live, /story, /account, /brain, /journey on the live site at 390x844: no page errors,
no 4xx/5xx, no horizontal overflow (only a sandbox-proxy-blocked third-party request). Walked a signed-in options idea
locally (offline server) and called the live /v4/price_check on AAPL and NVDA contracts. Focus: today's new Price check.

Found:
- "Fairly priced" headline on every normal result, although only implied vs realized vol was judged (parity is skipped
  outside market hours). Overclaims next to the honest "Cheap/Expensive vs how much the stock moves" headlines.
- "the stock actually moved 43% (60 days)" describes realized volatility as if it were a 43% price move.
- NVDA at 1.33x implied/realized (the "expensive" line is 1.35x) was called "normal (implied usually runs a bit above
  realized)"; 1.33x is not "a bit".
- Bid-ask cost "about 0% of the price" for an NVDA $185 put ($25.12 / $25.20, really 0.3%).
- The check prices the closest LISTED contract (e.g. $170 put for the card's $167.5 leg) with no sign that it differs;
  dates shown as 2027-02-19 while the card says Feb 19, 2027; the same footnote repeated under each leg and mentioned
  parity even when parity wasn't checked.

Changed (backend/v4/pricecheck.py, frontend chat/PriceCheck.jsx):
- Headline "Normal price vs how much the stock moves" (parity-gap variant to match).
- Vol line: "priced for X% yearly volatility. The stock's actual daily swings work out to Y% a year over the last 60
  trading days (Z% over the last 20)"; normal band split into low end (<1.0x), plain (1.0-1.2x) and high end (>1.2x,
  "a buyer needs bigger moves than the stock has been making"). Footnote defines realized vol; parity sentence only
  when parity was computed.
- Spread shown to one decimal under 10% ("0.3%"), "less than 0.1%" for tiny.
- UI: "Closest listed contract to the idea's $167.5 · Feb 19, 2027" when strike/date differ; nice dates; footnote once.
- Test: vol wording tiers and percentage formatting.
- (after deploy) Live NVDA $185 put said "its own volatility is 48% vs 48% at the money. That difference (the volatility
  smile) is normal": the smile line now shows only when the strike's IV differs from at-the-money by 2+ vol points.

Checks: vite build passes, payoff/figures tests pass, backend tests 124 passed. Verified at 390px with a mocked
price_check (live NVDA data) on a local Bear Put Spread card.

## 2026-11-11

Walked /welcome, /trending, /live, /story, /account, /brain, /journey on the live site at 390x844 at ~21:25 UTC: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request; the hero SVG on /live
and /brain extends past 390px but is clipped, scrollWidth 390).

Found:
- Trending "What people believe": the Ski resorts card was tagged **Bearish** but its sample said "Artificial snowmaking
  will grow ..." (a bullish belief), next to MTN / UAL / DAL. DB: the theme holds 1 bullish (snowmaking, newest) and
  bearish "no snow in Denver hurts ski resorts and travel" beliefs; engine.trending took the label from the majority
  direction and the sample from the newest belief, so they could disagree.
- Welcome "What's new" still dated Nov 8 and didn't mention the option Price check shipped Nov 10.

Changed:
- backend/v4/engine.py trending: the sample view is the newest summary whose direction matches the card's label.
  Test added (test_trending_example_matches_the_theme_direction).
- frontend WhatsNew.jsx: Price check line, updated Nov 11.

Checks: vite build passes, backend tests 127 passed.

## 2026-11-12

Walked /welcome, /trending, /live, /story, /account, /brain, /journey on the live site at 390x844 at ~21:20 UTC: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). Focus: today's new
Yes / No page, walked locally at 390px (fake local account, read-only GETs proxied to the live /v4/yesno/*), plus live
/v4/yesno/quote calls on NVDA, SPY, TSLA after the close.

Found:
- Free money in practice: YES and NO were priced separately (call spread with the calls' IVs, put spread with the puts'),
  so when the feed's call and put IVs disagree they don't add up to the payout. Live after the close: NVDA $170 Nov 13
  YES $74 + NO $162 = $236 for a $250 payout; SPY $750 Nov 13 YES $76 + NO $19 = $95 for $100. Buying both = a sure
  practice profit, and YES's cost didn't match the market's odds shown above it.
- "The brain is proven on 90-day calls" overclaims (its 90-day edge is small: 53.4% vs 51.3%), and the "Brain's lean"
  bar didn't say it comes from fixed, untested starting rules (no learned model yet).
- The trade differs from the answer between the two strikes (NVDA 165/167.5 call spread costs $121: a "right" YES at a
  $166 close still loses money) and no breakeven was shown.
- "Of the app's last 666 ideas on NVDA" reads oddly (DB: 666 beliefs in 14 days each had NVDA as an idea).

Changed:
- yesno.quote prices YES and NO with one volatility, the line strike's IV (the one behind the market's odds), via a new
  optional `vol_override` on practice_options.quote/open_trade (other option trades unchanged; marks use the stored vol).
- Each side carries `breakeven` (YES k1 + cost, NO k2 - cost); the card shows "Breaks even above/below $X"; the note
  names the call/put spreads and says the trade can differ from the answer between the strikes.
- Lean label "Brain's lean (starting rules, untested)" (or "(learned)"), honest track-record sentence; reason line
  "In the past 14 days the app suggested NVDA 666 times: 500 as a bullish idea, 166 as a bearish one."
- Tests: breakeven, and YES + NO add up when call and put IVs differ.

Checks: vite build passes, backend tests 135 passed.

## 2026-11-13

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844 at ~21:25
UTC: no page errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). Walked a
signed-in DAL Bull Call Spread locally (offline server): $58/$64, $218 per contract, 4 for $872, max gain $1,528,
breakeven $60.18, +175% on a 20% rise; all add up. Live /v4/yesno/quote NVDA $190 Nov 20: YES $21 + NO $228 = $249 for
$250 (rounding), breakevens consistent.

Found:
- Brain page "Just learned" showed "I don't think a Tesla-SpaceX merger would face heavy scrutiny and could drag on
  Tesla → TSLA ▼": the opposite side reads as the same bet. DB: both the hunch and its "I don't think" opposite were
  interpreted bearish on TSLA; "Cloud outages will fade slowly, and customers may spread workloads ..." got an opposite
  with a stray capital ("I don't think Cloud outages ...") whose meaning is unclear. Negating two linked claims (", and", "and could", "but", "while", ", so") or an
  already-negative hunch ("... won't change ...", giving "I don't think ... won't") is ambiguous, so the brain learned
  the same side twice. Since Oct 30: 9 such compound pairs, 5 with the same direction on both sides.
- Close Call said "We couldn't find listed options on SPY right now. Try a bigger company." when the chain failed to
  load: SPY is the biggest there is.

Changed:
- backend/v4/seeder.py: news_beliefs adds the "I don't think" opposite only for single, un-negated claims
  (`_negatable`); the hunch itself is still learned. Test: test_news_opposite_side_only_for_single_claims.
- backend/v4/yesno.py: "We couldn't load options on X expiring in the next few weeks. The quote feed may be busy: try
  again in a minute. (Not every company has listed options.)"

Not changed (noted): Moving now showed 1 story at Friday 21:20 UTC (Claude kept 1 of 30 headlines, mostly
press releases after the close); not a bug.

Checks: vite build passes, backend tests 138 passed.

## 2026-11-14

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844 at ~03:30
UTC: no page errors, no horizontal overflow (only the sandbox-proxy-blocked third-party request). First pass hit 502s
on /v4/brain and /v4/journey (shown as CORS errors): that was the 03:24 deploy of 6e15329 starting; fine on re-walk.
Focus: last night's Close Call change (odds now from the call spread around the line), via live /v4/yesno/quote.

Found:
- Cost no longer matched the odds. Odds now come from the market's call-spread mids (skew included), but YES / NO were
  still priced off one strike's IV. TSLA $400 Nov 20: market odds 38.8%, YES $84 for a $250 payout (33.6%);
  NVDA $185 Dec 18: 21.3% vs YES $20/$100. A desk would ask why the price disagrees with the odds above it.
- Brain page: "Beliefs learned ... 22 today" right under "Learned 24 beliefs from today's news" (6m ago): "today" was
  the UTC date, which rolls over at 7 PM ET, while every other time on the page is ET. DB: 22 since UTC midnight,
  129 since New York midnight.
- "Both sides of each story" stopped being true on Nov 13 (compound hunches get no opposite now).

Changed:
- backend/v4/yesno.py: `spread_vol` finds the one volatility at which the k1/k2 call spread prices at its listed mid
  (root closest to the line IV); YES / NO and the practice trade use it, so YES costs the market's own spread price
  and YES + NO still add up to the payout. Falls back to the line IV, then an estimate. Quote returns `price_vol`,
  `price_source`. A fit more than 20% away from the line IV is treated as noisy quotes and ignored (first deploy:
  NVDA $185 Dec 18 fitted 0.41 vs line IV 0.58 on thin $1 strikes after hours, YES $13 vs odds 21%). Brain features still use the line IV (unchanged inputs). Test:
  test_yesno_spread_vol_prices_yes_at_the_listed_spread_mid.
- Odds sanity check: live after hours SPY (spot $752) showed "61% to close above $755" (one-vol 46%) and 53% above
  $760 (35%) from the $1-strike spread mids, which lag the stock after the close. A spread digital more than 10
  points from the one-vol answer is now not shown; the screen says "From one implied volatility (the spread quotes
  looked out of date)". Test: test_yesno_stale_spread_quotes_fall_back_to_one_vol.
- YesNoPage note says which price the practice trade used ("listed mid price of the same $X/$Y spreads").
- backend/v4/brain.py: beliefs_today counts from New York midnight. BrainPage: "Both sides of most stories".

Checks: vite build passes, backend tests 142 passed.

## 2026-11-14 (morning run)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844 at ~06:25
UTC (Saturday): no page errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request).
No new HQ messages from Murad.

Found:
- "Moving now" cards said "AMD stock -8.8% today", "ARM -5.9% today" on a Saturday: the move is Friday's session
  (feed: market closed, next open Mon 9:30 ET; snapshot dailyBar Fri, prevDailyBar Thu). Same in the 30-second story
  ("stock today"). An expert reading on a weekend or before the open sees a "today" that never happened.
- Close Call cross-check (live /v4/yesno/quote, Saturday stale quotes): AAPL $360 Nov 20 shows 42.7% odds from the
  $357.5/$362.5 spread while YES costs $83 for $250 (33%) priced at the line IV, because the trade's own $360/$362.5
  mid fit a vol >20% from the line IV and was rejected as noisy. Part of the gap is structural (the YES spread sits
  above the line, breakeven $360.83). AAPL $370: odds 7.3%, YES $22/$500 (4.4%) from the spread fit. Not changed;
  re-check on a weekday with live quotes before touching the 20% / 10-pt guards.

Changed:
- backend/v4/movers.py: snapshots carry `change_day` (the session date of the move; None when the move is untrusted).
- frontend MoversFeed.jsx: `sessionLabel` says "today" only for today's New York session, otherwise "on Fri" (or
  "on Nov 2" if older); StoryViewer uses it too. Test: test_movers_snapshot_says_which_session_the_move_is_from.

Checks: vite build passes, backend tests 147 passed.

## 2026-11-14 (late-morning run)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844 at ~09:30
UTC (Saturday): no page errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request).
Signed-in screens locally (offline server, throwaway SQLite): chat -> options cards -> paper trade -> Portfolio,
My beliefs, Close Call. No new HQ messages from Murad. Focus: the Builder's new "Greeks today" panel (57e5cc2).

Found:
- Greeks check out: NVDA $185/$202.5 Bull Call Spread, 25% vol, 97 days: panel delta +27 sh, gamma +0.22, theta
  -$1.12/day, vega +$5.03; finite differences of the card's own bs_price give 26.9 / -1.13 per day / ~+4.8 to +5.0
  per vol point, cost $641 = card. Every library structure gives sensible signs (credit spreads short gamma/vega,
  straddle long both).
- Delta-neutral cards read oddly: an Iron Condor (delta -1.1) or Iron Butterfly (+0.5) would say "Moves like being
  short 1 share" / "+1 sh", and a delta under 0.5 printed "−0 sh" and "Moves like owning 0 shares: about $0".
- Practice options contradicted the Portfolio banner: on Saturday the banner said "New trades wait and fill at the
  opening price (Monday 9:30am ET)", but the NVDA spread opened at once ($641 set aside, position live). Shares do
  queue (paper_trading), options (practice_options.open_trade, also used by Close Call) never did.

Changed:
- backend/v4/practice_options.py: open_trade returns `market_closed` and, when closed, the message adds "The market is
  closed, so it opened now at an estimate from the last prices; it doesn't wait for the open." Fill behaviour unchanged.
- PracticePage banner: "New share trades wait and fill at the opening price ... Practice options and Close Calls open
  right away at an estimate from the last prices."
- StrategyCard GreeksPanel: no "−0"; a delta that rounds to 0 shares reads "About neutral today: a $1 move in X
  changes it by less than 50 cents."
- Test: test_practice_options_open_value_close_and_expire checks the open/closed message.

Checks: vite build passes, backend tests 151 passed.

## 2026-11-14 (afternoon run)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844 at ~12:25
UTC (Saturday): no page errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request).
"48 today" on /brain checks out against /v4/brain activity (8 hourly rounds of 6 since New York midnight).
Signed-in screens locally (offline server, throwaway SQLite): a bullish 3-month shares call (NVDA/AMD/AVGO) and a
bearish 1-year options call (CMG Bear Put Spread), then My beliefs. No new HQ messages from Murad. Focus: the Builder's
new "I'm wrong if..." (ccb4e74).

Found:
- The pre-mortem always said "Imagine it's 90 days from now and this call lost", even on a call the card itself labels
  "~12 months" (1-year horizon) or "1 month".
- My beliefs said the price line is "Checked from the first close after your call", but engine.tripwire starts strictly
  after the call's date, so a call made Monday at 10am skips Monday's 4pm close.
- Numbers checked: CMG $38/$28 Bear Put Spread $4.26 - $0.84 = $342, max gain $658, breakeven $34.58, "CMG falls 20%"
  +$418 (spread worth $760); starter price lines are 10% past the entry ($185 -> $166.50, $38 -> $41.80); the saved
  line, the backend check (bullish below entry, bearish above) and the My beliefs text agree.

Changed:
- WrongIf.jsx: takes `horizonDays` and says "Imagine it's ~N months/days from now" with the card's own horizon wording
  (fallback "Imagine this call lost."); ChatInterface passes interpretation.horizon_days, MyCallsPage passes horizon_days.
- MyCallsPage: "Checked against each daily close after the day of your call." Tripwire logic unchanged.

Checks: vite build passes, backend tests 152 passed.

## 2026-11-14 (late-afternoon run)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844 at ~15:25
UTC (Saturday): no page errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request).
Live backend is on 0801caf (Builder's "How sure are you?"). Signed-in screens locally (offline server, throwaway
SQLite): a bullish 3-month shares call and a bearish 1-month call, "How sure" tapped on both, then My beliefs.
No new HQ messages from Murad. Focus: "How sure are you?" (0801caf) and the "I'm wrong if..." starters.

Found:
- "I'm wrong if..." offered the starter "it trails the S&P by 5%+ in 30 days" on every call. On a bearish call that is
  the call going RIGHT (a bearish pick is supposed to trail the market), so the suggested pre-mortem contradicted the
  call. It also said "in 30 days" on a 7-day call.
- The calibration countdown read "0 of 10 calls with a 'How sure' are graded so far (1 waiting for their check)" after
  one tap: "0 of 10" suggests ten such calls exist. The "'Leaning' means the gap could still be luck" footnote showed
  before any verdict existed.
- Checked and fine: calibration grading uses grader's belief-level belief_right (same value on every pick of a belief, so
  MAX() is safe); checkpoint_for matches the frontend (3 months -> 90-day check, 1 month -> 30-day); bearish says
  "does worse than the S&P 500", volatile "moves more", matching grader (b < spy, |b| > |spy|); Brier baseline 0.25
  for always-50% is right; verdict thresholds (10 pts, 2 binomial SEs) behave sensibly on small buckets.

Changed:
- WrongIf.jsx: takes `direction`; the vs-market starter points against the call (bullish "trails the S&P by 5%+",
  bearish "beats the S&P by 5%+", volatile "moves less than the S&P"), over 30 days or the call's horizon if shorter.
  ChatInterface and MyCallsPage pass the call's direction.
- MyCallsPage CalibrationCard: "You've said how sure you are on N calls; none have reached their check yet. Your score
  shows after 10 graded calls (10 to go)"; the "Leaning" footnote shows only once there is a score.

Checks: vite build passes, backend tests 153 passed.

## 2026-11-14 (evening run)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844 at ~18:25
UTC (Saturday): no page errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request).
No new HQ messages from Murad. Focus: the Builder's honest t-stats on /brain (79d600f), now live with numbers.
Signed-in screens not re-walked (no signed-in code changed since the late-afternoon run).

Found (from /v4/brain skill.luck: app_t 4.52, app_t_nw 1.91, app_dates 429, app_n_eff 482, clear 2 of 41, clear_nw 0):
- The scorecard still said "that gap is the skill the brain has learned so far" while the luck card right below now
  says the #1 pick does NOT clear the bar once overlapping calls are counted (t 1.9 vs bar 3.2). An expert reads the
  headline claim as overstated.
- The luck card said "2 of 41 cleared it, including the way we pick the #1" and then "0 of 41 ways do" with no hint
  that the first count is the plain (independent-calls) way, so the two sentences read as a contradiction.
- Live feed "Learned 54 beliefs from today's news · 10 rounds" sat next to "78 today": the feed only lists the last
  rounds (54 = 10 rounds since 09:19 UTC; 78 counts from New York midnight). Checked: n_eff = n*(t_nw/t)^2 = 482, right.

Changed (frontend/src/components/BrainPage.jsx only; no numbers or gates touched):
- Scorecard: when the overlap-honest t exists and doesn't clear, "The #1 pick is ahead of our other ideas so far, but
  the luck check below can't yet rule out luck once overlapping calls are counted honestly." (skill wording kept for
  when it does clear).
- Luck card: "Counting each call as independent, 2 of 41 cleared it ..." when the honest line is shown.
- Feed: "Learned N beliefs from the news" (no "today's"), so it no longer competes with the "today" count.

Checks: vite build passes, backend tests 154 passed.

## 2026-11-14 (night run)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844 at ~21:30
UTC (Saturday): no page errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request).
No new HQ messages from Murad. Focus: the Builder's base-rate line (ae51885) and /brain after tonight's ranker retrain
(ranker v2 went live 21:15 UTC, model mlp).

Found (from /v4/brain skill.ranker and skill.luck):
- The green card said "New: a smarter #1 pick" and then showed its numbers BELOW the old way's: beat 52% (old 53%),
  lift +1.2 pts (old +1.5). An expert reads that as a contradiction. Reason: the "old way" figures are the stored
  practice-call #1, which had look-ahead (d856c72); rebuilt point-in-time it's 52% / +0.5 (old_pit), which the card
  didn't show.
- The luck card called the old app score "the way we pick the #1 you see today", but with the ranker active today's #1
  mixes in the retrained model (engine, weight 0.5). The model's own overlap-honest t (2.2, bar 3.2) wasn't shown.
- Base rate line checked and fine: /v4/base_rates cells are one result per call; all inputs are seed_backfill
  ("practice", 4,398 beliefs to 2026-07-24) plus 7-day checks on news calls, so "Mostly the app's practice calls" is right.
  30d and 90d cells share n (2,651) because practice calls end Jul 24 and news calls start Oct 30 (no 30-day result yet).

Changed (frontend/src/components/BrainPage.jsx only; no numbers, gates or ranking touched):
- Ranker card: title "New: a smarter #1 pick" only when it out-scores the old way's stored numbers, otherwise "Updated #1
  pick"; when it trails them, says the stored old score peeked at later results on practice calls and shows the old way
  rebuilt without the peek (52%, +0.5 pts). "the new #1 beat a risk-matched S&P" (was an ambiguous "it").
- Luck card: with the ranker active, "the old way of picking the #1 (today's #1 also mixes in the retrained model
  below)", and the overlap line adds the retrained model's t both ways and whether it clears the bar.

Checks: vite build passes, backend tests 157 passed.

## 2026-11-15 (overnight run, ~00:25 UTC = Sat 7:25 PM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No new HQ messages from
Murad. Checked the Builder's "Still filling in" luck card with live numbers (seas 83%, dbeta 70%, ivol 26% filled; 6 of
42 clear the plain way, 0 the overlap-honest way): wording and counts agree with /v4/brain. Signed-in screens not
re-walked (no signed-in code changed since the last walk).

Found:
- News feed (/trending, home "Moving now", Story) showed "stock -0.0% on Fri" in red for BA (move -0.01%): a sign and
  color on a move that rounds to zero.
- Story mode opened on a giant "November 30, 2026" under "MOVING NOW" (Latam / Embraer E195-E2 launch date). On
  Nov 14 it reads like the page's own date, in the future. The no-Claude fallback would have been worse: it grabbed
  "195" out of "E195-E2".

Changed:
- lib/figures.js `signedPct` / `pctTone` / `TONE`: a move that rounds to 0.0% reads "0.0%" in grey; text and color come
  from the same rounded value. Used by MoversFeed Pct, StoryViewer Pct, TrendingPage, ToolSelectorPage, ui/Page `pct`.
  Tests in figures.test.mjs.
- movers.py: a bare-date hook becomes "On Nov 30" (year kept only if not this year), applied on read too so cached
  stories are fixed; the story prompt says "never a bare date"; the fallback hook skips digits glued to model names.
  Test in test_story_mode (test_v4.py).

Checks: vite build passes, figures tests pass, backend tests 158 passed.

## 2026-11-15 (early run, ~03:30 UTC = Sat 10:30 PM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No new HQ messages from
Murad. Signed-in screens locally (offline server, throwaway SQLite): a bullish travel call and a bearish restaurant call,
backdated to Nov 2, each with an "I'm wrong if..." line, one answered "Yes" -> My beliefs. Builder's "Did that happen?"
(f4a2e4b) checks out: Yes/Partly/Not yet from a week after the call, "You marked: it happened (Nov 14)", the lesson line
matches the call's state (ahead + "yes" -> "Was your test wrong, or is the result luck"), no overflow at 390px.

Found:
- /brain after the 02:19 UTC retrain: ranker inactive (`skill.ranker.active` false), so the green ranker card, the only
  place that said the old #1 score peeked at later results, disappeared. The page then showed the stored #1 as skill:
  scorecard +1.2 pts on 4,398 mostly-practice #1 picks, luck card "5 of 42 cleared it, including the way we pick the #1
  you see today" (app t 4.52), and "When the AI is most sure ... tested on past calls it never saw" (+2.5 / +1.1 / +0.9,
  which with the ranker off is the app's stored score: research.fit_production confidence = "app (current #1)"). Per
  d856c72 / docs/brain_upgrades.md, about two-thirds of that lift is look-ahead: `old_pit` lift +0.53%, t 1.70 (does not
  clear the 3.24 bar) vs stored +1.49%, t 4.52. An expert would call this look-ahead bias presented as skill.
- Welcome / login "What's new" was dated Nov 12 and missed the user features since then (How sure, I'm wrong if...,
  base rate, Did that happen?).

Changed (frontend only; no numbers, gates or ranking touched):
- BrainPage.jsx: when `ranker.old_pit` exists and the stored lift is higher, the scorecard adds "A catch we found":
  practice calls used each stock's track record including later results; without the peek the #1 beat our other ideas
  by +0.5 pts (t 1.7) instead of +1.5 (t 4.5), the live forward test has no peek. Luck card: "including the way we pick
  the #1 as stored, but not once the peek above is removed (t 1.7)" (only when old_pit is under the bar) and "as stored"
  on the overlap line. Confidence card (ranker off): "uses the #1's score as stored ... these gaps are likely too big too."
- WhatsNew.jsx: Nov 15, two new lines (How sure + base rate + calibration; I'm wrong if... + mark whether it happened).

Checks: vite build passes, backend tests 159 passed.

## 2026-11-15 (morning run, ~06:30 UTC = Sun 1:30 AM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No HQ messages from
Murad. Signed-in screens not re-walked (no signed-in code changed since the last walk). Read every story in today's
feed via /v4/movers/story and the cached stories in kv_cache (read-only SQL).

Found:
- Story cards stopping mid-sentence: 6 of 44 cached stories had a field cut with "…", e.g. Bernie Sanders housing story
  "why" ends "...which may matter for housing-linked…"; two had cut big hooks from before the whole-hook rule
  ("11,000 satellites, still…", "Credit stress looks…") that the read-time hook check still let through.
- Story hook line editorialised: SpaceX catch story said "...and the people who matter most are cheering" about
  Musk, Hegseth and Trump Jr. reacting. Not neutral; an expert reads it as taking sides.
- News feed: RKLB tagged "▲ story helps" with the reason "Rivals' reusable tech raises pressure to match cheaper launch
  costs", a reason that argues the other way.
- /live activity: "Learned 50 beliefs from the news · 10 rounds · 4m ago" next to "12 today" read as a contradiction;
  the 10 grouped rounds span 10 hours, the time shown is only the newest.

Changed:
- movers.py: `_sentences` cuts story happened / why / twist at the last whole sentence that fits (word clip with "…"
  only when no sentence fits), also applied on read to cached stories; `_hook` drops a hook ending in "…".
  STORY_PROMPT: hook_line stays neutral (report who reacted, never judge whose opinion matters); why in whole
  sentences. Feed PROMPT: a company's reason must agree with its up/down direction. Test in test_story_mode.
- BrainPage.jsx: grouped activity says the span, "· 10 rounds over 10h".

Checks: vite build passes, backend tests 160 passed.

## 2026-11-15 (mid-morning run, ~09:30 UTC = Sun 4:30 AM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No HQ messages from
Murad. Signed-in screens not re-walked (no signed-in code changed since the last walk).

Found:
- News feed (/trending, "Moving now") showed the wrong companies. kv_cache `movers:v1` built 09:19 UTC had `ai: false`
  with no error: Claude kept none of the 30 weekend headlines, so the feed fell back to raw headlines and the news
  source's own tags. "Dr. Martens plc Announces Ex-Dividend Date" -> "COMPANIES IT TOUCHES: DOCS" (DOCS here is
  Doximity, Dr. Martens' London ticker); "Potentially AI PLC Announces Beta Workspace" -> AGI (Alamos Gold). Each with a
  "See how to invest in this" button. The same fallback replaced Friday's curated hunches with exactly the noise the
  prompt drops (a dividend date, "RBC Maintains Buy Rating").
- /brain "A catch we found": "+0.5 pts (t 1.7) instead of +1.5 pts (t 4.5)" right under a headline of "+1.2 pts". Both
  are right (2,703 test calls vs 4,398 graded #1 picks), but read as a contradiction.

Changed:
- movers.py: a news-source tag (a company Claude didn't pick) stays only if the story names it: its ticker as a word,
  or the first real word of its listed name (`_names_company`, Alpaca asset name, already cached). When a rebuild has
  no Claude hunches and the stored feed does and is under 3 days old (`MP_MOVERS_KEEP_CURATED_SECONDS`), keep the
  curated feed (its "Updated" time stays honest, built_at unchanged) and mark `checked_at` so it isn't rebuilt every
  request. Test test_movers_fallback_drops_tags_for_a_different_company_and_keeps_the_curated_feed.
- BrainPage.jsx: "... instead of +1.5 pts (t 4.5) on those same calls with the peek".

Checks: vite build passes, backend tests 162 passed.

## 2026-11-15 (afternoon run, ~14:30 UTC = Sun 9:30 AM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No HQ messages from
Murad. News feed shows curated hunches again (the morning fix holds). Checked live Close Call SPY $750 Nov 20: YES $53 +
NO $46 = $99 of $100, breakevens $750.53/$750.54, consistent with 54.6% odds on a $750/$751 spread. Checked /brain
"Just graded" AVGO +14.9% in DB (ret 17.4% minus SPY 2.5%, matches). Read the new Close Call "Your answers" record code:
counting and clustered band add up.

Found:
- /brain "MuLine vs the classics" claimed "MuLine caught real turns sooner ... than ALMA" on 4.72 vs 4.89 days late,
  both with a 4-day median (trendlab in /v4/brain). A 0.2-day gap is not "sooner" to an expert's eye.
- Close Call reason: "SPY's MuLine trend is rising (for 1 trading days)."
- /brain luck check: "1 of 42 ways do."

Changed:
- BrainPage.jsx: MuLine verdict says the gaps in numbers; under half a day reads "about as fast as ALMA (4.7 vs 4.9
  days late on average, the same 4-day median), with 2.9 fewer false turns a year". Non-winning verdicts add "Still
  tuning". "1 of 42 ways does".
- yesno.py `_reasons`: "1 trading day" singular. Test test_yesno_reasons_say_one_trading_day_in_the_singular.

Checks: vite build passes, backend tests 164 passed.

## 2026-11-15 (late-morning run, ~15:30 UTC = Sun 10:30 AM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No HQ messages from
Murad. The Nvidia headline in the feed (Huang's ouster) is real news (WSJ/Fortune, Nov 11). New "in real time" tile
matches the DB.

Found:
- /brain "Just learned": "Nvidia's leadership shake-up will make its chip sales harder to predict" (direction volatile in
  DB, b-91be3cc7c96f42e2) showed "NVDA ▲ · SMH ▲ · AMD ▲". Those picks are volatile (a big move either way, graded on
  |move|), but anything not bearish was drawn as ▲, so it read as a bullish call on a story the feed tags "story hurts".
- /brain "Growing every day": "Beliefs learned 6,567 · +6,567 in 30 days" and "5,474 · +5,474 in 30 days". The DB starts
  Oct 28 (MIN(created_at)), so the 30-day gain is the whole total; reads like a padded stat.

Changed:
- BrainPage.jsx: volatile picks show ↕ plus "(↕ a big move either way)"; a growth line whose count started inside the
  window says "all since Oct 28" (beliefs) / the first real-time grade day, otherwise "+N in 30 days".

Checks: vite build passes, backend tests 165 passed.

## 2026-11-15 (evening run, ~18:30 UTC = Sun 1:30 PM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No HQ messages from
Murad. Signed-in screens locally (offline server, throwaway SQLite): "AI chip demand will keep rising for the next 6
months", $1,000, 6 months, Options, Biggest upside -> NVDA Bull Call Spread $185/$210 May 21 2027: $14.61 - $5.57 =
$904 debit, max gain $2,500 - $904 = $1,596, breakeven $194.04, +20% scenario +$1,596 = +177% of cost: all add up.
Paper traded it -> Portfolio shows Invested $904, cash $99,096. No overflow at 390px.

Found:
- Options card footnote: "Priced at the stock's past volatility (no live option quotes) (24%)." Two parentheses in a
  row, and the 24% has no unit (it is annualized volatility).
- Welcome "What's new" (Nov 15) misses Close Call's new "Your answers" record (6eb8c5b / 125d41c).

Changed (frontend only):
- StrategyCard.jsx: "Priced at the stock's past volatility (24% a year), since there were no live option quotes." (implied
  case: "the market's implied volatility (N% a year)").
- WhatsNew.jsx: "New: Close Call keeps your record: how often you picked the right side, next to what the market's odds
  expected".

Checks: vite build passes, backend tests 166 passed.

## 2026-11-15 (night run, ~21:30 UTC = Sun 4:30 PM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No HQ messages from
Murad. Checked tonight's brain upgrade (fcc9b08) and Builder spread line against /v4/brain and `baserate:v1`.

Found:
- Confidence badge contradicts its own test. `ranker:v2.confidence` (basis "app, no look-ahead") reads high +0.2 /
  mid +0.9 / low +0.5 pts (t_nw 0.3 / 1.0 / 1.0), yet each live #1 pick still got a green "High confidence" badge
  whose tooltip says the most confident picks beat the average idea by more than the least confident ones.
- /brain "When the AI is most sure" still said "This uses the #1's score as stored, which peeked at later results",
  which is no longer true since fcc9b08 switched it to the no-look-ahead score.
- /trending: "Centrica and Equinor Advance in Bidding Process for Uniper" listed "CNA ▲ story helps, stock +0.5% on
  Fri". CNA is Centrica's London ticker; in the US it is CNA Financial (an insurer), whose price move was shown.

Changed:
- research.confidence_backed(): the badge is shown on the #1 only while the top third beats the bottom third;
  engine still stores the label in features.rv2_conf for the live forward test. No ordering/gate change.
- BrainPage.jsx: says the thirds are scored without the peek; when not backed: "So far, more sure has not meant
  better: the most confident third did +0.2 pts, the least confident +0.5 pts, and none of these gaps is clear of
  luck. So the #1 pick shows no confidence badge until the test backs it up." The stale peek line only shows on the
  old basis.
- movers.py: a ticker that came from the article's tags must name the company in the story even when Claude picked
  it; prompt warns about foreign tags that are a different US company.
- Tests: test_confidence_badge_hidden_while_the_test_does_not_back_it,
  test_movers_drops_a_claude_pick_that_is_a_foreign_tag_for_a_different_us_company; updated
  test_ranker_confidence_thirds_and_live_label.

Checks: vite build passes, backend tests 172 passed.

## 2026-11-16 (early run, ~00:30 UTC = Sun 7:30 PM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No HQ messages from
Murad. /brain confidence card now reads high +2.2 / mid +1.6 / low +0.4 pts (ranker active, model's own out-of-sample
thirds in `ranker:v2.confidence`), so the badge is back by the same honest rule. Signed-in screens locally (offline
server, throwaway SQLite): "Restaurants will struggle as consumers cut back", $1,000, Options.
- Earn income -> CMG Bear Call Spread $40/$44: credit $2.34 - $1.16 = $118, max loss $282, 3 for $846, collect $354,
  breakeven $41.18, +42% of cost if flat (354/846): all add up.
- Biggest upside, 1 month -> CMG Long Put $39 at $2.01: breakeven $36.99, but "Max gain $3,661" and "Best case
  +$14,644" (4 contracts). Should be ($39 - $2.01) x 100 = $3,699 and $14,796.

Found: the card's max gain / max loss / breakevens came from frontend `payoff.summarize`, a 1,200-point grid starting
at 1% of the stock price (so a put's best case stopped at $0.38, short by 1% of the price x 100) and stepping over
strikes (a butterfly's peak read low). The backend fixed the same grid on 11-13 (`library.economics`); the card never
got it. An expert reading "$3,661" beside a "$36.99" breakeven sees the mismatch at once.

Changed: payoff.js reads the expiry payoff exactly at $0, every strike and a far point (it is straight between strikes),
for both `summarize` and `capitalPerUnit`. Test in payoff.test.mjs (long put $3,699, butterfly peak on the strike).
Re-walked: "Max gain $3,699", "Best case +$14,796".

Checks: npm test passes, vite build passes, backend tests 172 passed.

## 2026-11-16 (morning run, ~03:30 UTC = Sun 10:30 PM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No HQ messages from
Murad. Signed-in screens locally (offline server, throwaway SQLite): "Airlines will have a strong holiday travel
season", $1,000, 3 months, Shares. Close Call can't be walked offline (no option chains).

Found:
- /brain "It grades itself, honestly": every row read "Trained a new brain ... trained on 11,408, tested on 3,299",
  nine days running (/v4/brain versions since Nov 4; identical lift 0.0058 t 1.21 since Nov 9). No 90-day outcome has
  been graded since Nov 2 (outcomes, checkpoint_days=90), so these are the same brain re-fit on the same data, shown
  as a stream of new brains. An expert reads that as theatre.
- DAL share card: "Fits your $1,000: about 17.24 shares", then "You buy about $1,000 of DAL (17 shares)" and "17
  shares" under the amount (17 x $58 = $986, not $1,000).

Changed (frontend only):
- BrainPage.jsx: when the newest retrains used the same counts, a line says "The last 9 retrains used the same 11,408
  graded calls. This brain learns from 90-day results, and no new ones have come in (the first real-time calls reach
  90 days on Jan 27). So read these as the same brain re-checked, not new ones."; each such row reads "same data as
  the one before"; activity feed says "Retrained the brain" instead of "Trained a new brain".
- payoff.js `shareCount`: two decimals under 100 shares, no trailing zeros (17.24, 10); used by the sizing note and
  the plain-English line. Test in payoff.test.mjs.

Checks: npm test passes, vite build passes, backend tests 173 passed.

## 2026-11-16 (midday run, ~06:30 UTC = Mon 1:30 AM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No HQ messages from
Murad. Cross-checked live Close Call AAPL $360 Dec 18: YES $204 + NO $294 = $498 of a $500 payout, breakevens
$362.04 / $362.06, odds 50.2% (flat-vol 44.8%, matches N(d2)); the spread note explains the $360-$365 gap. Signed-in
screens locally (offline server, throwaway SQLite) at 390 and 375: NVDA Bull Call Spread $185/$210, 6 months: $14.57 -
$5.54 = $903, max gain $1,597, breakeven $194.03, delta +28 sh: all add up; paper trade lands in Portfolio at $903.

Found: "Protect what I own" (the chip says "Insurance for shares I have") -> NVDA Protective Put, $5,000:
- the card said "Doesn't fit $5,000 even at 1 contract" and "ties up about $18,710 ... No version of this idea fits
  that amount", because the price includes buying the 100 shares the user just told us they own. Nowhere did it say
  the insurance itself was $210. An expert reads that as the app not understanding its own strategy.
- legs read "$177.5 strike · $2.1" (money without cents).

Changed:
- payoff.js `plainEnglish`: Protective Put adds "Already own 100 NVDA shares? Then only the put is new money: about
  $210."; Collar adds the options-only net (paid, received, or about $0). Test in payoff.test.mjs.
- StrategyCard: for Protective Put / Collar over budget the badge reads "With the 100 shares included, 1 contract costs
  more than your $5,000"; leg prices show cents ($177.50, $2.10).
- strategy.fit_budget: for those two, the note says the price includes buying 100 shares and that an owner only adds
  the options (test_protect_goal_over_budget_says_the_price_includes_the_shares). No sizing change.

## 2026-11-16 (afternoon run, ~09:30 UTC = Mon 4:30 AM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call, /reel, /learning on the live site at
390x844: no page errors, no 4xx/5xx (except /v4/learning 403, the owner-only page, as designed), no horizontal overflow.
No HQ messages from Murad. Signed-in screens locally (offline dev server, throwaway SQLite) at 375: "Restaurants will
struggle as consumers cut back", Not sure / AI decides / Let the AI decide -> CMG Bear Put Spread $38/$32: $2.67 -
$0.61 = $206, max gain $394, breakeven $35.94: all add up; paper trade lands in Portfolio at $206.

Found:
- Baskets (Home -> Baskets, never walked before): when the basket builder fails for any reason, `/basket/generate_basket`
  returned a fixed VTI 60% / BND 40% (VTI labelled "stock") with "5-7% annually" and risk "moderate", whatever the goal,
  and never said it was a stand-in. Reproduced locally with "Something safe for a house down payment in 3 years": 60%
  stocks and a promised return. (Live currently builds a sensible SGOV/SHY/BND/VTIP mix, so this only shows on a failure.)
- /live and /brain tile "Brains trained 46" sits above the note that the last 9 retrains were the same brain re-checked.

Changed:
- basket_router: on failure, HTTP 500 "We couldn't build a basket for that goal just now. Nothing was made up: please
  try again in a minute." (shown in the page's error line). v4 basket.generate raises when no valid holding survives
  instead of the generic 60/40; the empty-goal stand-in now says "A plain 60/40 starter mix, not built for a goal."
  Test: test_basket_route_never_serves_a_canned_basket_when_the_builder_fails.
- BrainPage: "Training runs" (tile) and "46 training runs so far".

Not live yet: Render's build minutes ran out at 08:07 UTC (builder flagged it to Murad), so this push won't deploy until
builds resume. Checks: vite build passes, npm test passes, backend tests 177 passed.

## 2026-11-16 (midday run, ~12:30 UTC = Mon 7:30 AM ET)

Walked /welcome, /trending (incl. "Watch the story in 30 seconds" and "See the other side"), /live, /story, /account,
/brain, /journey, /close-call, /reel on the live site at 390x844: no page errors, no 4xx/5xx, no horizontal overflow.
No HQ messages from Murad. Live Baskets (dividend income; AI and chips) add up to 100% and carry no promised return.
Render builds still failing (out of build minutes), so 0dbdbfc / 4db4cda / ee64847 and this commit wait in line.

Signed-in screens locally (offline server, throwaway SQLite) at 375, first walk of a "big move either way" (volatile)
belief: Bold, $1,000, 3 months, Options, Limit my risk -> NVDA Long Strangle $197.50 call $5.05 + $172.50 put $3.41 =
$846, breakevens $164.04 / $205.96, +/-20% = +$1,604, chart top +$5,304 at $259: all add up; paper trade lands in
Portfolio at $846.

Found:
- The Breakeven tile on every two-breakeven card (strangle, straddle, condor, butterfly) read "$164.04..." at 375px:
  the upper breakeven was cut off, the one number that says how big the move must be.
- Choosing Shares on a volatile call gives a Sell / Avoid card that still said "Fits your $1,000 · 3 months" and "Why
  this strategy: Best fit for what you said matters most." (nothing is bought; the user never chose a goal).
- For Murad's build chat, not changed: a range-bound ("will trade sideways") belief can never get a range strategy.
  Pick directions are only bullish / bearish / volatile (interpreter schema and `_sanitize` turn neutral into bullish),
  so Iron Condor / Iron Butterfly are unreachable and a sideways call gets e.g. a Bull Call Spread whose "stays flat"
  row reads -100%. Live DB: 0 user beliefs are neutral so far (seeded ones are), so not urgent. Fixing it touches
  grading (no neutral rule), so it's an M for the build chat.

Changed (frontend only):
- StrategyCard `Stat`: an array value stacks one line per number; Breakeven passes both breakevens ($164.04 above
  $205.96), single values unchanged.
- StrategyCard: the budget line and the generic "what you said matters most" reason are hidden on Sell / Avoid cards.
- scripts/dev_offline_server.py: the fake interpreter also returns volatile ("big move", "either way") and neutral
  ("sideways", "range") beliefs, so those cards can be walked locally.

## 2026-11-16 (late run, ~15:30 UTC = Mon 10:30 AM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call, /reel on the live site at 390x844:
no page errors, no 4xx/5xx, no horizontal overflow. No HQ messages from Murad. Render builds still failing (out of
build minutes): every push since 0dbdbfc is queued, including this one.

Signed-in screens locally (offline server, throwaway SQLite) at 375, first walk of the "Earn income" goal: Careful,
$5,000, 6 months, Options, Earn income -> JETS Cash-Secured Put $21.50 for $0.74 x 2: collect $148, set aside
$4,152 (= $4,300 - $148), breakeven $20.76, -20% = -$312 (-8% of $4,152), delta +46 sh: all add up. Paper trade ->
Portfolio: Invested $4,152 + cash $95,848 = $100,000.

Found:
- "See the other side" / "I doubt it" (news feed and story viewer) built the user's belief by lower-casing the first
  letter of the hunch, whatever it was. From this week's real hunches that gives "I don't think aI firms will pay
  publishers...", "aI coding tools", "nvidia will face...", "europe's race...", "social Security overhaul...", and a
  hunch with "may" gives "I don't think bitcoin may slide...", which isn't English. An already negative hunch
  ("X won't ...") gave a double negative. The text becomes the user's belief in chat and My beliefs.
- The brain's own news opposites (/brain "Just learned") had the same "I don't think X may ..." wording
  (e.g. "I don't think Bitcoin's weekend selloff may signal a longer crypto downturn ahead").
- The passkey card said "Log in with Windows Hello or a passkey" on every device that isn't iPhone, Mac or Android
  (Linux, ChromeOS).

Changed:
- frontend lib/text.js `oppositeOf` / `lowerFirst` (mirrors seeder._lower_first: acronyms, names, possessives,
  two-word names and nationalities keep their capital; may / might / could -> will; a negative hunch becomes
  "I doubt that ..."). MoversFeed `doubtUrl` uses it. Test: src/lib/text.test.mjs (in npm test).
- seeder: `_opposite` writes may / might / could as "will" (lower-case only, so the month May stays); an opposite
  already learned in the old wording isn't learned again; the renamed opposite still pairs with its hunch for the
  same-side `avoid` check. Test: test_news_opposite_reads_as_english_and_still_pairs_with_its_hunch.
- auth.biometricName: "Windows Hello or a passkey" only on Windows, otherwise "a passkey".

For the Builder (not changed): the same-side guard only drops a stock bet the same way on both sides. "I don't think
Bitcoin's weekend selloff may signal a longer crypto downturn" was still learned bearish (QQQ down) because QQQ
wasn't one of the hunch's stocks. Of the last 60 hunch/opposite pairs, ~9 have the same overall direction on both
sides; some are real (winners vs losers, e.g. "tighter chip controls favor US rivals over Nvidia"), so a blanket
"same direction = skip" rule would be wrong.

Checks: vite build passes, npm test passes (payoff, figures, text), backend tests 180 passed.

## 2026-11-16 (evening run, ~18:30 UTC = Mon 1:30 PM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call, /reel on the live site at 390x844:
no page errors, no 4xx/5xx, no horizontal overflow. No HQ messages from Murad. Render builds still failing (out of build
minutes): every push since 0dbdbfc is queued, including this one.

Signed-in screens locally (offline server, throwaway SQLite) at 375, first walk of selling a share position and of the
Portfolio's options rows: NVDA shares $1,000 = 5.4054 sh @ $185, sold flat -> cash back to $100,000. NVDA Long Call
$180 @ $12.79 = $1,279, breakeven $192.79, flat -$779, +20% +$2,921, chart top +$6,621 at $259: all add up.

Found:
- Portfolio options rows never showed the strikes: "NVDA LONG STRANGLE · 5 contracts · expires Feb 19, 2027". Which
  strangle? A finance reader can't tell what the position is.
- Shares path (no goal question is asked) and "Any options strategy" cards said "Why this strategy: Best fit for what you
  said matters most." The user never said what matters most.
- After a shares paper trade the card said "Added $1,000 of NVDA to your practice portfolio" then "See it in My beliefs";
  the options trade (rightly) links to Portfolio.
- For later (not changed, M): a sold position disappears with no record; Portfolio then says "Nothing here yet" and the
  realized gain only shows inside Account value. A closed-trades list would need backend history.

Changed:
- PracticePage: each options row shows its legs ("Buy $197.50 call · Buy $172.50 put", stock legs "Own 100 shares").
- strategy.select: with no goal, shares say "You chose shares: the simplest way to own this idea, any amount, no end
  date."; options say "Fits your belief's direction and your risk level, with options as you asked." Goal text unchanged
  when a goal was given; stay-out cards keep the text the card already hides. Test
  test_strategy_reason_never_claims_a_goal_the_user_did_not_give.
- StrategyCard: shares paper-trade confirmation links to Portfolio.

Checks: vite build passes, npm test passes, backend tests 182 passed.

## 2026-11-16 (night run, ~21:30 UTC = Mon 4:30 PM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No HQ messages from
Murad. Render builds still failing (out of build minutes): every push since 0dbdbfc is queued, including this one.

Signed-in screens locally (offline server, throwaway SQLite) at 375, first walk of a bearish "Earn income" card:
"People are eating out less at restaurants this year", Bold, $5,000, 3 months, Options, Earn income -> CMG Bear Call
Spread, sell $40 call $1.92 / buy $43 call $1.04: credit $0.88 = $88, max loss $300 - $88 = $212 per contract, 23
contracts = collect $2,024, worst case $4,876, breakeven $40.88, +42% of cost: all add up. Paper trade -> Portfolio:
Invested $4,876 + cash $95,124 = $100,000, row shows "Sell $40 call · Buy $43 call".

Found (Brain page, the part a finance reader will study hardest), checked against live /v4/brain:
- The luck check said "today's #1 also mixes in the retrained model below". Since the brain upgrade (69ab3d0, queued)
  a model that passed alone picks the #1 alone (weight 1.0); the sentence would be wrong as soon as it deploys.
- "Counting overlap honestly" said the live #1 model scores t 3.0, "short of the bar" (3.25), with no mention that on
  the risk-matched measure the same counting gives t 4.25 (lift_adj_t_nw), which clears it. A reader sees a model
  "short of the bar" running the #1 and no reason why.
- "It grades itself, honestly" said "46 training runs · none of the latest 24 has earned a vote" right under a card
  saying the retrained #1 model is live. They're different models (nightly brain vs ranker v2), never said.

Changed:
- brain._skill: ranker carries `mix` (False = the model alone orders the #1). Test
  test_brain_scorecard_says_whether_the_ranker_is_mixed.
- BrainPage: luck check says "today's #1 now comes from the retrained model below" unless the ranker is a mix (or an
  older backend sends no `mix`); overlap paragraph adds "matched for each stock's risk, it scores t 4.3 counted that
  way, clearing it" (or "short of it"); the versions list says "These are the nightly brain's runs. The #1 pick model in
  the scorecard above is trained separately and has shaped the #1 since Nov 16."
- Not changed (research gate, not mine): the go-live gate uses plain t (MIN_T 1.5, MIN_T_ADJ 1.0), well under the luck
  bar the page shows (3.25). Today's live model clears both anyway; worth a sentence from the brain upgrade task if a
  future model goes live between the two.

Checks: vite build passes, npm test passes, backend tests 187 passed. Verified locally against live /v4/brain data.

## 2026-11-17 (early run, ~00:30 UTC = Mon 7:30 PM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /journey, /close-call on the live site at 390x844: no page
errors, no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No HQ messages from
Murad. Render builds still failing (out of build minutes): every push since 0dbdbfc is queued, including this one.

Signed-in screens locally (offline server, throwaway SQLite) at 375, first walk of the bearish Long Put, the bearish
shares "Stay out" card and the new Closed trades list: "Restaurants will struggle as people cut back on eating out",
$1,000, 3 months, Options, Biggest upside -> CMG Long Put $39 @ $2.91: 3 contracts $873, breakeven $36.09, max gain
$3,609/contract ($10,827 for 3), flat at $38 -$573, -20% +$1,707 (+196%), chart top +$3,987 at $22.80: all add up.
Paper trade -> Portfolio -> Close -> Closed trades: set aside $873, got back $873, +$0.

Found:
- Closed trades date was a day late for US evenings: practice options stored `datetime.now()` with no offset (the
  server's UTC clock), the phone read it as local time. A close at 7:30 PM ET Mon showed "CLOSED NOV 17".
- An options trade closed by hand on its expiration morning would be tagged "Expired" (date-only comparison).
- Bearish shares card said "Shares only make money when a price rises." Not true as stated (short selling); a finance
  reader would flag it.

Changed:
- practice_options: new times stored in UTC with offset; expiry settles at 4pm New York with offset; `closed()` reads
  older bare rows right (bare 16:00:00 = NY expiry settle, else UTC) and sends offsets; "expired" = settled at/after
  4pm NY on expiration day. Router `_closed_trades` sends every closed_at with an offset (old share sales too).
  Test test_closed_trade_times_carry_their_offset. Checked in a New York-timezone browser: "CLOSED NOV 16".
- StrategyCard: "Buying shares only makes money if the price rises. To bet on a fall, tap Options."

Checks: vite build passes, npm test passes, backend tests 189 passed.

## 2026-11-17 (morning run, ~03:30 UTC = Mon 10:30 PM ET)

Walked /welcome, /trending, /live, /story, /account, /brain, /close-call on the live site at 390x844: no page errors,
no 4xx/5xx, no horizontal overflow (only the sandbox-proxy-blocked third-party request). No HQ messages from Murad.
Render builds still failing (out of build minutes): every push since 0dbdbfc is queued, including this one.

Reviewed the new Portfolio "You vs the S&P 500" (ffbc03a) as a finance reader would.

Found:
- The S&P leg started at SPY's last close before the trade, even for a trade opened during market hours. A trade
  placed at 2pm was charged with the S&P's whole move since the previous close: open a $1,000 trade at 2pm on a day
  SPY is up 0.8% and the card instantly said "Same money in the S&P 500: +$8 · behind by $8" before the trade had a
  chance to move. The footnote ("a trade held a few hours inside one day compares against little or no move") was
  only true for closed trades.
- Queued share orders filled at the open were stamped `T09:30:00-04:00` (summer offset). In November that's 8:30 AM
  New York, an hour before the session the fill price came from.

Changed:
- benchmark: a moment inside regular hours (9:30-4pm NY on a trading day) uses SPY's 5-minute bar it falls in (its
  open, adjusted like the daily closes; one fetch per day, cached); outside hours, or if the bars can't be fetched,
  the last close before it, as before. `compare`/`attach` take an `at` price function (tests inject it). Max 12 days
  fetched per portfolio load. Footnote: "from its price when the trade opened to its price when it closed (or now).
  During market hours that's SPY's price within 5 minutes of the trade; while the market is closed, its last close."
- paper_trading queued fills: `market._session_open_dt(day)` (right offset in winter and summer).
- Test test_a_trade_opened_during_market_hours_starts_from_spy_at_that_moment_not_the_morning.

Checks: vite build passes, backend tests 193 passed.
