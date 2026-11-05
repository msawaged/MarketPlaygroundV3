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
