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
