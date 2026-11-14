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
