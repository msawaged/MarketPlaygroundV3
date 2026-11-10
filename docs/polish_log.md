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

Checks: vite build passes, payoff/figures tests pass, backend tests 124 passed. Verified at 390px with a mocked
price_check (live NVDA data) on a local Bear Put Spread card.
