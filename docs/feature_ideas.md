# Feature ideas backlog

Proposals for Murad and the other Claude sessions: one well-sourced idea per entry for the app (users) or the brain
(ranking, grading, honesty). Written by the daily CTO scout routine; nothing here is built until someone picks it up.
Status: **proposed** → accepted / rejected / built (with the commit). Ideas that would loosen research gates, use
look-ahead, change real-money behaviour or claim more than the data shows are never proposed.

---

## 2026-11-11 — "How sure are you?": user-stated probability and a personal calibration score
- **Area:** app (learning loop), with a small brain benefit.
- **Status:** built 2026-11-14, commit 0801caf (Builder): one-tap 55/65/75/90% under the picks in chat and on
  My beliefs (settable until the day after the call, then locked), scored at the checkpoint matching the call's
  horizon; "How well-calibrated are you?" card on My beliefs (Brier, said-vs-right table, 10-call minimum, "leaning"
  until the gap is beyond 2 standard errors). Not built yet: brain's own label on the same scale, `user_prob` in
  pick features for research. 2026-11-15 (Builder): instead of the brain's High/Medium/Low (Claude's `conviction` is
  "medium" on ~97% of calls, so scoring it says nothing), the card compares the user with the outside view: Brier if
  they had said the base rate (baserate.py) on each call, paired 2-SE verdict, 10+ calls with a base rate.
- **Problem:** the only confidence the app records for a call is `beliefs.conviction`, which Claude infers from the
  wording, and it carries almost no information: since Oct 1, 33 of 34 real user calls and 5,801 of 6,039 seeded
  calls are "medium" (prod query, 2026-11-11). So the app grades *whether* a call beat the S&P 500 but never teaches
  the skill that matters most for practising calls: knowing how sure you should be. Overconfidence is the best-known
  investor error (Barber & Odean: overconfident investors trade more and earn less).
- **Evidence / sources:**
  - Mellers et al. (2014), "Psychological Strategies for Winning a Geopolitical Forecasting Tournament",
    Psychological Science 25(5): forecasters who gave probabilities and got scored feedback (Brier) improved, and a
    short probability-training module improved accuracy measurably:
    https://www.psychologicalscience.org/journals/psychological-science/0956797614524255/ ;
    open copy: https://escholarship.org/uc/item/4rg4n9vr
  - Barber & Odean (2001), "Boys Will Be Boys: Gender, Overconfidence, and Common Stock Investment", QJE 116(1)
    (overconfidence → excess trading → lower net returns).
  - Brier (1950) score: mean of (stated probability − outcome)², 0 = perfect, 0.25 = always saying 50%.
- **Build sketch (size M):**
  - Chat: after the belief is entered, an optional one-tap row "How sure are you it beats the S&P in N days?"
    with 55 / 65 / 75 / 90% (no free text, no default; skipping is fine).
  - `backend/v4/db.py`: migration `ALTER TABLE beliefs ADD COLUMN user_prob REAL` (keep the `ALTER TABLE t ADD COLUMN`
    shape the migration test expects). `router.py`: accept `user_prob` on the belief request (0.5-0.99, else null);
    `engine.py` stores it. Keep Claude's `conviction` untouched (it drives the strategy structure).
  - `grader.py` / a small `calibration.py`: for each graded user call with `user_prob`, outcome = 1 if the #1 pick
    beat the S&P (in the call's direction) at 90 days. Per user: Brier score, count, and a 4-bucket reliability table
    (said 55/65/75/90% → actually right X%), only shown with 10+ graded calls; below that, "N more graded calls
    until your calibration score".
  - `MyCallsPage.jsx`: a "How well-calibrated are you?" card (said vs actual per bucket, plain words: "When you said
    75%, you were right 58% of the time — a bit overconfident"). Same scoring for the brain's own High/Medium/Low
    label later, so users can compare themselves with the brain on equal terms.
  - Brain: store `user_prob` in the pick's `features` (`num`) so research can later test whether user certainty
    predicts anything — through the normal walk-forward gates only, never straight into rankings.
- **How we'd know it worked:** share of new user calls with a probability (target 40%+ after a month); the
  calibration card is opened; among users with 10+ graded calls, Brier score falls between their first and second
  10 calls (the Mellers effect). No change to ranking metrics expected or claimed.
- **Risks:** small samples look precise — hence the 10-call minimum and showing counts next to every percentage;
  the 90-day grading delay means the card stays empty for months for new users (show the countdown, and optionally
  a 30-day provisional read clearly labelled provisional); must never read as advice ("you should be 75% sure") —
  it only mirrors the user's own track record. No real-money or gate impact.

---

## 2026-11-12 — Luck bar for research: count every rule we test and show the multiple-testing threshold
- **Area:** brain (research honesty); a small app/brain-page benefit.
- **Status:** built 2026-11-12 (Murad: "build it"); see docs/brain_upgrades.md
- **Problem:** every `research:ranker` run scores 37 methods on the same 2,703 test beliefs (run 2026-11-12 10:03 UTC:
  37 entries in `results`), and the daily routine adds one more rule a day (9 so far). The idea log then reads each
  rule's t-stat against the usual 2.0 bar. With 37 tries, the biggest |t| from pure noise is expected to be around
  2.5-3, so "t 2.9" (frog in the pan, today) or "t 3.0" (intermediate momentum, today) can be luck; a Bonferroni 5%
  two-sided bar for 37 tests is |t| ≈ 3.20. Today 10 of 37 clear it: the app's #1 (4.54), the Amihud rule (3.98), plain
  gbm (3.68) and the seven "+ app (25%)" mixes; on the risk-matched t only the Amihud rule among fixed rules does. Nothing records how many rules were ever tried, including ones later dropped, so the
  number behind every claim on the brain page understates how much searching was done.
- **Evidence / sources:**
  - Harvey, Liu & Zhu (2016), "...and the Cross-Section of Expected Returns", Review of Financial Studies 29(1), 5-68:
    with hundreds of factors tried, a new factor needs t > ~3.0, not 2.0:
    https://ideas.repec.org/a/oup/rfinst/v29y2016i1p5-68..html ; NBER: https://nber.org/papers/w20592
  - Bailey & López de Prado (2014), "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting
    and Non-Normality", Journal of Portfolio Management: https://papers.ssrn.com/abstract=2460551 — the best of N
    backtests must be judged against the expected best of N noise strategies.
- **Build sketch (size S):**
  - `backend/v4/research.py` `run()`: after `results`, add `tests_run` (number of methods scored), `luck_bar`
    (Bonferroni two-sided 5% critical t for that count, via `statistics.NormalDist`), and per method `p` and
    `holm_ok` (Holm step-down at 5% on `lift_t`, and separately on `lift_adj_t`). Store a cumulative
    `research:tries` kv entry: the set of every method name ever scored (so dropped rules still count), and report
    its size as `tries_ever` and a second bar for that count. Pure reporting: `_passes`, `fit_production` and the
    ranker v2 gate stay exactly as they are (any tightening would be Murad's decision, written up in
    docs/brain_upgrades.md).
  - `docs/research_ideas.md`: each result line adds "clears the luck bar (|t| ≥ X for N tests): yes/no"; the daily
    routine reads it from the kv instead of eyeballing t ≥ 2.
  - `/v4/brain` (engine/router brain payload) and the brain page: one plain line under the ranker card, e.g.
    "We tested 37 ways to pick the #1; 10 cleared the bar for luck (t ≥ 3.2)." Numbers from the same kv, never typed.
  - Test: synthetic run with 37 pure-noise rules → Holm flags ≈ none; one planted rule at t 6 → flagged.
- **How we'd know it worked:** every research entry states whether it clears the bar; over the next month the count of
  "promising" rules quoted in docs falls to those that clear it, and their next-run results hold up more often than
  rules that didn't (track: share of rules with t ≥ 3.2 that keep t ≥ 2 on the next 30 days of new graded calls).
- **Risks:** Bonferroni/Holm assume roughly independent tests; ours are correlated (many momentum variants), so the
  bar is conservative — say so in the text and keep the raw t visible. A second, separate honesty gap worth its own
  entry later: 90-day outcomes of beliefs made on nearby dates overlap, so the plain t-stats are likely too large
  (date-clustered or Newey-West errors would fix it). Must not be read as loosening anything; it only adds a
  stricter lens.


---

## 2026-11-13 — Honest t-stats: count overlapping 90-day windows once (date-clustered / Newey-West errors)
- **Area:** brain (research honesty); feeds the luck bar and the brain page.
- **Status:** built 2026-11-14, commit "Honest t-stats: research reports..." (Builder): `research._se_overlap` (residuals summed per call date, date
  pairs weighted by window overlap 1 - gap/90 calendar days: Bartlett/Driscoll-Kraay style, nests date clustering);
  every result gets `lift_t_nw`, `lift_adj_t_nw`, `dates`, `n_eff`; `luck` adds `clear_nw` / `clear_adj_nw` /
  `app_clears_nw` and the app's t's; brain page luck card says it in plain words. Reporting only (gate untouched).
- **Problem:** every t-stat in `research:ranker` (`_metrics.tstat`) treats each test belief as an independent draw:
  se = std / sqrt(n) with n = 2,703. But those 2,703 beliefs sit on only 429 distinct dates (2024-12-03 to
  2026-07-24, prod query 2026-11-13), about 6 per date, and each is graded on a 90-day window, so calls made the same
  week share most of their market path. Beliefs on the same date are not independent (same market, often the same
  tickers: e.g. NVDA was an idea in 666 beliefs in 14 days, polish log 2026-11-12), and consecutive dates overlap by
  ~60 of 63 sessions. So the effective sample is far smaller than 2,703 and every t is too big, including the app's
  own 4.54, the Amihud rule's 4.04 and the luck bar's `clear` list. The luck bar (built 2026-11-12) fixed "how many
  tries"; this fixes "how many independent observations", the other half flagged in that entry and in
  docs/brain_upgrades.md ("overlapping 90-day windows likely also inflate the plain t-stats, not addressed").
- **Evidence / sources:**
  - Petersen (2009), "Estimating Standard Errors in Finance Panel Data Sets: Comparing Approaches", Review of
    Financial Studies 22(1), 435-480: with a time effect (observations on the same date correlated), OLS standard
    errors are biased down, often badly; clustering by time fixes it:
    https://econpapers.repec.org/RePEc:oup:rfinst:v:22:y:2009:i:1:p:435-480 ; author's page with code and test data:
    https://www.kellogg.northwestern.edu/faculty/petersen/htm/papers/standarderror.html
  - Newey & West (1987), Econometrica 55(3): autocorrelation-consistent standard errors, the standard fix for
    overlapping-horizon returns (lag = horizon - 1). Practitioner summary of why overlapping long-horizon tests
    overstate significance: https://quantpedia.com/problems-with-a-long-horizon-predictability/
- **Build sketch (size S):**
  - `backend/v4/research.py`: `_metrics` takes each pick's belief date (already in `b["date"]`; pass it through
    `_pick`/`_choose` as a 5th tuple element). Add `lift_t_nw` / `lift_adj_t_nw`: average the lift per date
    (one number per day), then a Newey-West t on that daily series with lag = 63 sessions (~the 90-day window),
    Bartlett weights; plain numpy, no new dependency. Also report `dates` (distinct test dates) and
    `n_eff` ≈ n · (se_plain / se_nw)². Keep the old `lift_t` / `lift_adj_t` exactly as they are.
  - `research.luck`: add `clear_nw` / `clear_adj_nw` (same Holm step-down, on the NW t's) next to the existing lists.
    Reporting only: `_passes`, `fit_production` and ranker v2's activation rules don't read any of it (tightening
    the gate with it would be Murad's separate, deliberate decision, written up in docs/brain_upgrades.md).
  - `/v4/brain` `skill.luck` + BrainPage scorecard line: "The 2,703 test calls were made on 429 days with overlapping
    90-day windows; counted honestly that's worth about N independent calls." Numbers from the kv, never typed.
  - `docs/research_ideas.md`: the daily routine quotes the NW t beside the plain t.
  - Test: synthetic run where every belief on a date shares one big random market shock → plain t large, NW t near
    noise level, and `n_eff` well below n; a planted real per-pick edge still shows up under NW.
- **How we'd know it worked:** every research run shows both t's and `n_eff`; rules whose NW t clears the bar keep
  their edge on the next 30-60 days of newly graded calls more often than rules that clear only on the plain t
  (track it in the log). The brain page and marketing "receipts" stop quoting t-stats that overstate certainty.
- **Risks:** NW with a 63-session lag on ~430 dates is itself noisy and can be unstable for short series — show it
  with the date count, and fall back to date-clustered (Petersen) errors if the two disagree wildly. It will make
  most current "wins" look weaker, likely including the app's #1; that's the point, but the campaign copy that
  quotes t's must be updated the same day. Must not be read as loosening anything; it only adds a stricter lens.

---

## 2026-11-14 — "I'm wrong if...": a one-line pre-mortem on each call, shown back at every checkpoint
- **Area:** app (learning loop); a small, later brain benefit.
- **Status:** built 2026-11-14, commit ccb4e74 (Builder): optional line + price line on one shown pick, set in chat
  under the picks or later on My beliefs; My beliefs shows it with "crossed on <date>" from daily closes after the
  call. "Did that happen?" built 2026-11-15 (Builder, commit "Did that happen?..."): yes / partly / not yet on the
  written line from a week after the call, changeable, cleared when the line changes, set beside how the call is doing.
  Not built yet: push alerts on a crossing, research use.
- **Problem:** the app records *what* a user believes but not *why* or *what would prove it wrong*. Since Oct 1 the 34
  real user calls (7 users) average 43 characters (prod query 2026-11-14, `beliefs.source = 'user'`), e.g. a ticker
  and a direction. When the call is graded at 7/30/90/180/365 days (`grader.CHECKPOINTS`), the user sees a number but
  has no record of their own reasoning to compare it with, so the lesson defaults to "I was right/lucky" or "the
  market was wrong": hindsight bias (people misremember what they expected once they know the outcome) and the
  disposition effect (holding losers, selling winners: Odean 1998) both feed on having no written exit condition.
  That's the core skill a practice app should teach, and nothing in the app, docs/feature_ideas.md or the polish /
  brain logs covers it (the 2026-11-11 calibration idea asks *how sure*, this asks *what would change your mind*).
- **Evidence / sources:**
  - Mitchell, Russo & Pennington (1989), "Back to the future: temporal perspective in the explanation of events",
    Journal of Behavioral Decision Making 2(1): imagining the outcome has already happened ("prospective hindsight")
    raised the ability to name correct reasons for it by about 30%. Summary with references:
    https://corporate.jasoncollins.blog/premortem
  - Klein (2007), "Performing a Project Premortem", Harvard Business Review: https://hbr.org/2007/09/performing-a-project-premortem
  - Veinott, Klein & Wiggins (2010), "Evaluating the effectiveness of the PreMortem technique on plan confidence",
    ISCRAM: the pre-mortem lowered overconfidence more than a pro/con review: https://researchr.org/publication/VeinottKW10
  - Odean (1998), "Are Investors Reluctant to Realize Their Losses?", Journal of Finance 53(5):
    https://econpapers.repec.org/RePEc:bla:jfinan:v:53:y:1998:i:5:p:1775-1798
- **Build sketch (size S-M):**
  - Chat, after the picks are shown: optional "I'm wrong if..." field (one line, 140 chars, skippable, no default),
    with 3 tap-to-fill starters that only use things the app can check later: "...it falls below $X", "...it trails
    the S&P by more than N% in 30 days", or free text. Plain-words hint: "Imagine it's 90 days from now and this
    call lost. Why?"
  - `backend/v4/db.py`: `ALTER TABLE beliefs ADD COLUMN wrong_if TEXT` and `wrong_if_px REAL` (optional price line;
    keep the `ALTER TABLE t ADD COLUMN` shape the migration test expects). `router.py` / `engine.py` accept and store
    them for user calls only (seeded calls never get one).
  - `grader.py`: at each checkpoint, if `wrong_if_px` is set, record whether the #1 pick's close crossed it (a
    yes/no from data we already fetch; no new feed). `MyCallsPage.jsx`: each graded call shows "You said you'd be
    wrong if: ..." next to the result, the tripwire status ("crossed on Nov 3" / "never crossed"), and one question:
    "Did that happen?" (yes / no / partly). An alert (existing push alerts, `AlertsCard`) when a price tripwire is
    crossed, worded as information, never "sell".
  - Later, research only: whether users who wrote a tripwire, or the tripwire crossing itself, says anything about
    the 90-day outcome goes through the normal walk-forward tests; it never feeds the ranking directly.
- **How we'd know it worked:** share of new user calls with a "wrong if" (target 30%+ after a month); share of graded
  calls where the user answers "Did that happen?"; among users with both, fewer repeat calls on the same ticker
  after a crossed tripwire without a new reason (a simple disposition-effect proxy), and better calibration on the
  2026-11-11 Brier card if that's built. No ranking metric change is expected or claimed.
- **Risks:** extra friction at call time (keep it optional, one line, after the picks); a price tripwire can read
  like a stop-loss instruction, so the copy must say it's the user's own test of their idea, not advice, and nothing
  trades; free text is user content (length-cap, store as text, render escaped, never send to Claude without the
  existing moderation path). No real-money, gate or look-ahead impact.

---

## 2026-11-14 (extra run) — Feature coverage in every research run: mark a result "provisional" until its data is filled in
- **Area:** brain (research honesty, data quality).
- **Status:** built 2026-11-14 late night, commit "Feature coverage..." (Builder): `research.coverage` / `provisional` / `rule_inputs`
  (a rule's inputs are traced from its own code), kv `research:ranker` keys `coverage`, `provisional`, `low_coverage`;
  brain page luck card "Still filling in". Not built: per-feature `remaining` from `research.enrich` (its batch query
  only sees a few hundred rows, so it can't give a true total; the run's coverage replaces it).
- **Problem:** when a new feature is added, older graded picks read it as 0 until `research.enrich` backfills them
  (`research.load` falls back to `NEUTRAL` or 0.0 for a key the pick never stored), so a rule scored on half-filled
  data is scored partly on placeholders. Today 5,279 graded picks still lack `seas` (prod query 2026-11-14), yet the
  06:47 UTC run reports the seasonality rule at t 2.73 with nothing in `research:ranker` saying the input is
  incomplete; `dbeta` (added today) starts at 0% filled. The only coverage number stored is `beta_coverage`. Every
  routine checks completeness with ad-hoc SQL over `picks.features` (a `LIKE` scan joined to `outcomes`), the kind
  of query that once caused an outage. The learned ridge / gbm / net also train on those placeholder zeros.
- **Evidence / sources:**
  - Breck, Polyzotis, Roy, Whang & Zinkevich (2019), "Data Validation for Machine Learning", MLSys: Google's TFX
    validates every training batch against an expected schema (presence, missing-value share, distribution drift)
    before a model sees it, because silent data gaps were a leading cause of bad models:
    https://research.google/pubs/data-validation-for-machine-learning/ ; summary:
    https://blog.acolyer.org/2019/06/05/data-validation-for-machine-learning/
  - Schelter et al. (2018), "Automating Large-Scale Data Quality Verification" (Amazon Deequ): completeness metrics
    as unit tests on data: https://cdn.amazon.science/9f/b6/15099d504c54bec20ec6a6c2eb3d/deequ-data-quality-validation-for-machine-learning-pipelines.pdf
- **Build sketch (size S):**
  - `backend/v4/research.py` `load()`: while building each candidate row (it already reads `num`), count per key in
    FEATS whether the pick stored it (and whether it's exactly 0.0). `run()` adds `coverage`: {feature: share of
    test-period candidates that stored it} plus `zero_share`, computed in the same pass (no extra query, a few
    hundred bytes in the kv). Each fixed rule gets the features it reads (a small dict next to `fixed`) and a
    `provisional: true` flag when any of them is under 99% covered.
  - `research.enrich` returns `remaining` per feature (already counts `missing`), stored in kv `research:enrich` by
    the hourly job, so routines read completeness from the kv instead of scanning `picks`.
  - `docs/research_ideas.md`: results quote coverage; the brain page lists provisional rules as "still filling in".
  - Reporting only: `_passes`, `fit_production`, `RISK_COVERAGE` and ranker v2's activation rules stay as they are.
    (Whether learned models should drop features under some coverage is a separate, deliberate decision for Murad,
    written up in docs/brain_upgrades.md.)
  - Test: synthetic data where half the picks lack a key → coverage 0.5, rule flagged provisional; full data → 1.0, not.
- **How we'd know it worked:** no idea-log result is recorded as final while its feature is under 99% covered; no
  routine needs the `LIKE` scan any more; a sudden drop in a feature's coverage or a jump in its zero share (e.g.
  a data-feed outage) shows up in the next run instead of quietly shifting results.
- **Risks:** tiny (reporting only); the "exactly 0" share is a heuristic, since some features can truly be 0; keep
  the payload small for the 512Mi jobs (counts only, no per-pick lists).

---

## 2026-11-14 (evening run) — "The outside view": show how often calls like this one have beaten the S&P before the user sets "How sure"
- **Area:** app (learning loop, honest expectations); no brain or ranking change.
- **Status:** built 2026-11-14, commit "The outside view: base rate..." (Builder): call-level (same `belief_right` the
  calibration card scores), direction x checkpoint, kv `baserate:v1`, cells under 100 calls hidden; theme cut not built.
- **Problem:** when a user makes a call, everything on screen is about *this* idea (Claude's picks, payoff chart,
  "How sure are you?", "I'm wrong if..."). Nothing tells them how often calls of the same kind have worked, which is
  the single most useful number for a beginner and the one people ignore by default (base-rate neglect). The app
  already knows it from its own grading: across 23,279 picks graded at 90 days (prod query 2026-11-14,
  `outcomes.checkpoint_days = 90` joined to `picks.direction`), bullish ideas beat the S&P only **46.8%** of the time
  (n 14,736, avg +0.58%), bearish ideas **59.0%** (n 7,923, avg +1.65%, a falling-market period), volatile 73.9%
  (n 620). Overall 7-365-day graded checks are right 51.7% of the time (`/v4/brain` counts: 58,966 of 113,960). A
  user tapping "90% sure" on a bullish 90-day call is betting against a ~47% base rate without knowing it; the new
  calibration card (built today) will tell them weeks later that they were overconfident, but never *what they
  should have started from*.
- **Evidence / sources:**
  - Kahneman & Lovallo (1993), "Timid Choices and Bold Forecasts: A Cognitive Perspective on Risk Taking",
    Management Science 39(1), 17-31: forecasts built from the case at hand ("inside view") are systematically
    overoptimistic; anchoring on the record of similar cases ("outside view") corrects it:
    https://econpapers.repec.org/RePEc:inm:ormnsc:v:39:y:1993:i:1:p:17-31 ; practitioner how-to (McKinsey, Lovallo &
    Sibony): https://www.mckinsey.com/business-functions/strategy-and-corporate-finance/our-insights/how-to-take-the-outside-view
  - Mellers et al. (2014), "Psychological Strategies for Winning a Geopolitical Forecasting Tournament", Psychological
    Science 25(5): a ~1-hour training whose core lesson was "start from base rates / reference classes" improved
    forecast accuracy (Brier) by about 10% over a year: https://escholarship.org/uc/item/4rg4n9vr
- **Build sketch (size S-M):**
  - `backend/v4/engine.py` (or a small `backend/v4/baserate.py`): `base_rate(direction, checkpoint)` = share of graded
    picks in that direction that beat the S&P at the call's checkpoint (`calibration.checkpoint_for(horizon_days)`),
    plus n and the date range, using the same `dir_excess > 0` definition the grader and calibration use. Computed by
    the existing hourly/grading job into one small kv row (`baserate:v1`, ~15 numbers: 3 directions x 5 checkpoints),
    never per request (a GROUP BY over `outcomes` is the kind of scan to keep off the request path). Optional second
    cut by the belief's top theme only when that cell has n ≥ 300; otherwise direction-only.
  - `router.py`: include `base_rate` {beat, n, since, checkpoint} with the picks response and in `my_beliefs` per call.
  - Frontend `chat/HowSure.jsx`: one plain line above the 55/65/75/90 buttons: "Calls like this (bullish, ~90 days)
    have beaten the S&P 47% of the time (14,736 graded, since <first date>)." With a `Term` for "base rate". On My
    beliefs, show it beside the user's own "sure" number and the result. No default selection, no nudge.
  - Copy rules: it's the app's own practice record, past not future; say when n is small; never "you should".
  - Test: synthetic graded picks → correct share per direction/checkpoint; cells under a minimum n return nothing.
- **How we'd know it worked:** among users who set "How sure", the average stated probability moves toward the base
  rate (less 90% on ~47% call types) and the Brier score on the calibration card improves versus users who made
  calls before the line shipped; share of 90% taps falls. No ranking metric is claimed.
- **Risks:** the base rate reflects one ~2-year market (bearish ideas did well because the period had drawdowns),
  so it must be labelled with its date range and can shift; it could discourage users ("why bother?"), so frame it
  as the bar to beat; mixing practice (seeded/shifted) calls and real user calls must be stated or split (use the
  same graded population the brain page already reports). No gate, look-ahead, real-money or research change.

## 2026-11-15 — "How wide it can go": show the spread of outcomes for calls like this, not just the hit rate

- **Status:** built 2026-11-15 night, commit "How wide it can go..." (Builder): call-level, not pick-level, so it is the
  same calls the base rate counts (each call's theme vs the S&P in the direction called; its sign is belief_right, 0
  mismatches on the live DB). Live 90-day bullish: worst 1 in 10 -12 pts, middle -2, best 1 in 10 +12. My beliefs
  marker built 2026-11-16, commit "My beliefs: where your graded call landed..." (Builder): each call's newest graded
  check (`engine._graded_checks`, same number as `baserate._spreads`) marked "You" on the spread bar for that check.
- **Area:** app (learning / honest framing); reuses the brain's own graded record. Extends "The outside view"
  (2026-11-14 evening, built in `backend/v4/baserate.py`).
- **Problem:** the outside-view line tells a user how *often* calls like theirs beat the S&P, but not how *far* they
  land either way, and the spread is the bigger lesson. Live DB (2026-11-15, all picks graded at 90 days, excess return
  vs the S&P in the call's direction): bullish ideas n 14,736, average **+0.6 pts** but median **-1.0 pts**, 1 in 10
  finished **18.6+ pts behind** the S&P and 1 in 10 **20.3+ pts ahead**; bearish n 7,923, median +3.0, 10th/90th
  percentile **-18.2 / +21.6 pts**; volatile n 620, -4.2 / +36.6. A beginner who sees "beats the S&P 47% of the time"
  reads a near coin-flip with small stakes; the real picture is a coin-flip whose sides are about ±20 points. Nothing
  on the call screen says that (the options card shows a worst case in dollars for options only).
- **Evidence / sources:**
  - Goldstein, Johnson & Sharpe (2008), "Choosing Outcomes versus Choosing Products: Consumer-Focused Retirement
    Investment Advice", Journal of Consumer Research 35(3), 440-456 (the "distribution builder"): people make better,
    more consistent risk choices when shown the range of outcomes rather than summary numbers:
    https://econpapers.repec.org/RePEc:oup:jconrs:v:35:y:2008:i:3:p:440-456 (paper:
    https://web.stanford.edu/~wfsharpe/retecon/GJSJCR08.pdf)
  - Kaufmann, Weber & Haisley (2013), "The Role of Experience Sampling and Graphical Displays on One's Investment Risk
    Appetite", Management Science 59(2), 323-340: showing the distribution of outcomes (and letting people sample from
    it) improved their understanding of risk and expected returns versus text-only descriptions:
    https://econpapers.repec.org/RePEc:inm:ormnsc:v:59:y:2013:i:2:p:323-340
- **Build sketch (size S):**
  - `backend/v4/baserate.py`: in `compute()`, add one more aggregate per direction x checkpoint: 10th, 50th and 90th
    percentile of `outcomes.dir_excess` (`percentile_cont` in Postgres; sort-and-pick fallback in SQLite for tests),
    stored in the same `baserate:v1` cells as `p10` / `p50` / `p90`. Same `MIN_N` rule (no cell under 100), same daily
    refresh, never on a request. One query over ~60k outcome rows, fine for the 512Mi job.
  - `router.py`: nothing new; `base_rate` already travels with the picks response, the new keys ride along.
  - Frontend `chat/HowSure.jsx`: under the existing outside-view line, one plain line plus a tiny bar: "Most land
    between 19 pts behind and 20 pts ahead of the S&P after ~90 days; the middle call finished 1 pt behind." `Term`
    for "percentile" avoided: say "1 in 10 did worse than..., 1 in 10 better than...". On My beliefs, once graded, mark
    where the user's own result fell on that bar.
  - Copy rules: the app's own practice record, past not future, with its date range; never "expected" or "will".
  - Test: synthetic graded outcomes -> correct p10/p50/p90 per cell; cells under MIN_N carry no spread.
- **How we'd know it worked:** fewer 90% taps on "How sure" and better Brier scores on the calibration card for users
  who saw the spread (compare calls made before and after it ships); fewer calls closed or abandoned in the first
  checkpoint after a large early drawdown, if that is tracked. No ranking metric is claimed.
- **Risks:** one ~2-year market (bearish ideas did well in a falling stretch), so the date range must be shown and the
  numbers will shift; percentiles of single picks overstate the spread a diversified user would face, so say "a single
  idea"; practice and live calls are mixed, as on the brain page, and should be labelled the same way. Information
  only: no gate, look-ahead, ranking, research or real-money change.

## 2026-11-16 — Ticker identity check: make sure the ticker still is the company the idea names

- **Status:** built 2026-11-16 night, commit "Ticker identity check..." (Builder), first part only: new ideas whose
  ticker isn't the company Claude named are dropped (`names.same_company`, checked on 1,439 live pairs: drops PARA,
  PMI/Philip Morris, BYD/Boyd Gaming, CAL, CATL, INTM, NOVZ and ~20 more misreads, keeps renames and initials);
  backfill calls skip tickers whose price on the call date is 200x off today's; `features.claude_name` stored; seeder
  counts `name_mismatch`. Enforced, not log-only, because the 1,439-pair check showed no false drops. Not done (Murad's
  call / brain upgrade): the audit of old picks and leaving flagged rows out of research.
- **Area:** brain (data quality / honest grading); small app effect (a wrong company is never shown).
- **Problem:** a ticker is not a company. Tickers get reused after mergers and delistings, and the app trusts the
  ticker alone. Live DB, 2026-11-16: **PARA** has 30 picks, every one stored with the name **"Parabolic
  Technologies, Inc. Class A Common Stock"**, not Paramount (Paramount merged with Skydance and left PARA in August
  2025). 25 of them are `seed_backfill` practice calls dated Dec 2023 to Jul 2026 that were meant as Paramount media
  calls; their entry prices run from **$215,128.56** (Dec 2023) down to $22.50, i.e. the new issuer's
  reverse-split-adjusted history pasted over Paramount's dates. 16 of the 90-day grades are -60% to -86% (a bearish
  "media is in trouble" call scores a ~70-point win that never happened), 4 of the 30 were the #1 pick, and the newest
  `seed_news` / `seed_live` picks (Nov 2026) are a $0.08-$3 penny stock. These rows feed research, ranker v2's
  training, the base rate / spread on the call screen and the brain page. Nothing in `engine.process_belief` compares
  the company Claude meant with the company Alpaca returns: `market.asset_info` only checks "active and tradable".
  (Other big price ranges in the picks table, e.g. SEZL, BYND, ASTS, look like real moves; PARA is the one clear
  identity break found with one small query, but nobody checks, so there may be others.)
- **Evidence / sources:**
  - CRSP, the standard U.S. research database, keys every security by a permanent number (PERMNO) precisely because
    tickers change and are reassigned; studies built on tickers silently splice different firms:
    https://www.crsp.org/wp-content/uploads/guides/CRSP_US_Stock_&_Indexes_Database_Knowledge_Base.pdf ; practitioner
    note on why quant data uses permanent IDs, not tickers: https://quantit.gitbook.io/finter/research-guide/data-science-for-finance/data-characteristics-and-methodologies/id-structures-quant-finance
  - Paramount-Skydance merger completed Aug 7, 2025 (Paramount Global's PARA stopped trading):
    https://www.advanced-television.com/2025/08/08/skydance-media-paramount-global-complete-merger/
- **Build sketch (size S-M):**
  - `backend/v4/engine.py` (candidate loop, where `asset_info` is called): compare Claude's `c["name"]` with
    `info["name"]` using a plain normalised-word overlap (drop "Inc", "Corp", "Class A", "Common Stock", "ETF" etc.);
    no overlap → skip the candidate and log `name_mismatch` (same path as an untradable ticker). Keep Claude's name in
    the pick record next to Alpaca's (e.g. `features.meta.claude_name`) so later checks can see both.
  - Backfill / shifted calls: also skip when the stock's bars are implausible for the dates used, e.g. any adjusted
    close above $20,000 or a 5-year max/min close ratio above 1,000 (`market.daily_closes` already has the series).
  - One-off audit job (read-only report first): list tickers whose stored pick names differ from today's
    `asset_info` name or whose history fails the plausibility check; write the list to `kv_cache` `audit:tickers`
    and show the count on /v4/brain. Then, as a separate deliberate step (Murad's call), mark those picks
    `data_flag` and leave them out of research, ranker v2 training and the base rate. No grade is rewritten in place.
  - Tests: synthetic candidate "Paramount Global" vs asset name "Parabolic Technologies" is dropped; "Apple Inc." vs
    "Apple Inc. Common Stock" kept; an ETF whose Alpaca name is the fund's long name kept (word overlap on the issuer
    or index name, so check a few real ETF names before shipping).
- **How we'd know it worked:** `name_mismatch` count in the seeder's log is small but non-zero; the audit lists PARA
  (and any others); after the flagged picks are excluded, research's raw lift and t for each rule move by less than a
  few hundredths on well-covered rules (if they move a lot, the bad rows were driving them, which is worth knowing).
- **Risks:** name matching can drop real tickers with very different legal names (e.g. "Alphabet" vs "Google",
  share-class names, ADRs), so start in log-only mode for a week and read the drops before enforcing. Excluding
  flagged rows changes the research sample, so it is written up in docs/brain_upgrades.md, and gates are untouched.
  No look-ahead: the name check uses what Alpaca says at pick time for live calls; for old backfill calls it only
  removes rows, never adds information.

## 2026-11-17 — Outlier check on every research result: does the lift survive without its few biggest calls?
- **Area:** brain (research honesty). Reporting only.
- **Status:** built 2026-11-17, commit e16f928 (Builder): `research.winsor_cuts` + `_metrics` lift_w /
  lift_w_t / lift_w_t_nw / lift_med / top10_share, `luck.clear_w` / app_lift_w / app_top10_share / winsor; Brain page
  "Without the extremes" line in the luck check. Gate unchanged. Numbers appear after the next research run.
- **Problem:** a research lift is a plain mean of 90-day excess returns, and those returns have fat tails. Live
  numbers (all graded 90-day outcomes, 2026-11-17): n = 23,279, mean directional excess +1.33% but median +0.53%,
  standard deviation 20.6%, 1st / 99th percentile -45% / +58%, **81 outcomes beyond ±100%** (max +500%, min -351%;
  e.g. ONDS +508%, SEZL +360%, plus the 30 mis-graded PARA rows). One +500% #1 pick moves the lift of a 2,703-call test
  by 0.18 points, about a seventh of the illiquidity rule's +1.21% (the only fixed rule that clears the plain luck
  bar). Today nothing tells us whether a rule's lift is broad (many calls a bit better) or comes from a handful of
  lottery tickets, or from bad data rows. The t-stat doesn't fully protect against this: a few huge values inflate the
  mean and the spread together, and a rule that happens to own two of them can look like skill. The research log keeps
  saying "a small number of bad rows in every result" without being able to say how much they matter.
- **Source:** Adams, Hayunga, Mansi, Reeb & Verardi (2019), "Identifying and treating outliers in finance", Financial
  Management 48(2): https://researchportal.unamur.be/en/publications/identifying-and-treating-outliers-in-finance
  (outliers routinely flip finance results; report results with and without them, winsorizing at 1%/99% is the
  common check). Bessembinder (2018), "Do stocks outperform Treasury bills?", JFE 129(3):
  https://econpapers.repec.org/RePEc:eee:jfinec:v:129:y:2018:i:3:p:440-457 (single-stock returns are extremely
  right-skewed: a few stocks account for most of the market's gains, so means over stock picks are fragile).
- **Build sketch (S):** in `research._metrics`, beside the existing numbers, add (reporting only):
  `lift_w` / `lift_w_t` = the same lift with each call's chosen and belief-mean excess winsorized at the 1st / 99th
  percentile of all test-period candidates (cut points fixed per run from the pooled outcomes, so every rule uses the
  same ones); `lift_med` = median per-call lift; `top10_share` = share of the total lift contributed by the rule's 10
  best calls. Brain page / research log quote `lift_w` beside `lift`; a new `luck.clear_w` list for rules whose
  winsorized t clears the bar. Files: backend/v4/research.py (+ a test in tests/test_v4.py), docs/research_ideas.md
  header (one line explaining the columns), optionally BrainPage.jsx (one "without the 1% extremes" number). Data
  needed: none new. Memory: one extra array per rule, negligible.
- **How we'd know it worked:** each run stores the new numbers; we can then say, for example, whether the illiquidity
  rule and the app's #1 keep most of their lift winsorized (broad edge) or lose it (a few big winners). A planted test
  where one rule owns two +500% calls and nothing else should show a large `lift`, a near-zero `lift_w` and
  `top10_share` near 1.
- **Risks:** must stay reporting only: `_passes` / `fit_production` keep reading the plain t (changing the gate is
  Murad's decision and goes in docs/brain_upgrades.md). Winsorizing hides real big winners, which a long-only user did
  earn, so it is shown as a check beside the real number, never instead of it. Cut points from pooled test outcomes
  are fine (no look-ahead into any rule's choice, they only rescale outcomes already graded), but must be computed
  per run, not hard-coded.

## 2026-11-18 — "Is it new?": how often each research rule picks the same #1 as the app, and its lift where they differ
- **Area:** brain (research honesty). Reporting only.
- **Status:** built 2026-11-21, bfbcdaa.
- **Problem:** the research log judges each of 46 fixed rules against zero and the luck bar, never against what the
  app already does. Today's run (2026-11-18 17:19 UTC, n = 2,703) shows why that matters: the strongest fixed rule
  yet, "avoid right-skewed stocks (-z_rskew)", has lift +1.45% / beat 53.4% / lift_w +1.26%, almost exactly the app's
  own #1 (+1.49% / 53.4% / lift_w +1.24%). If the two mostly choose the same stock, the rule is a re-description of
  the current ranking, not a new edge, and its clearing the risk-matched overlap-honest bar says little about whether
  ranker v2 should ever lean on it. The same question hangs over the illiquidity rule (+1.21%) and over "high vol" in
  `clear_w`. Nothing stored today can answer it: results hold each rule's own averages only.
- **Source:** Feng, Giglio & Xiu (2020), "Taming the Factor Zoo: A Test of New Factors", Journal of Finance 75(3),
  1327-1370: https://econpapers.repec.org/RePEc:bla:jfinan:v:75:y:2020:i:3:p:1327-1370 (working paper:
  https://www.nber.org/papers/w25481): a new factor should be judged by what it adds *given* the factors already in
  hand, and most of the hundreds proposed add nothing. Harvey & Siddique (2000) (idea 17's source) is itself an example:
  coskewness partly explains momentum rather than standing beside it.
- **Build sketch (S):** in `research.run`, for every rule record per test call whether its chosen #1 is the same pick
  as the app's #1 (both chosen within the belief's lead direction, as now). In `_metrics` (or a small helper beside
  it) add, reporting only: `same_as_app` = share of calls where the two #1s agree; `n_diff` = calls where they
  differ; `lift_diff` / `lift_diff_t` (and `_t_nw` via the existing `_se_overlap`) = the rule's #1 excess minus the
  app's #1 excess on those calls only, the direct head-to-head where it matters. Files: backend/v4/research.py, one
  planted test in backend/v4/tests/test_v4.py (a rule that copies the app should show `same_as_app` = 1 and no
  `n_diff`; a rule planted to beat the app on disagreements should show `lift_diff_t` > 3), one header line in
  docs/research_ideas.md; optionally one "agrees with the app N% of the time" note per row on the Brain page. Data
  needed: none new (the app's #1 per test call is already computed for the "app (current #1)" row). Memory: one
  boolean and one float per rule per call, negligible on the 512Mi job.
- **How we'd know it worked:** the next run says, for example, "rskew agrees with the app on X% of calls; where they
  differ it is +Y% (t_nw Z)". A high agreement with lift_diff near zero means the rule is the app restated; a
  meaningful lift_diff on disagreements is the first evidence a rule adds something the ranking doesn't have, which is
  what ranker v2's learned models would need to exploit. Research log entries quote it beside lift.
- **Risks:** must stay reporting only: `_passes` / `fit_production` and the luck bar are untouched (changing the gate
  is Murad's decision, written up in docs/brain_upgrades.md). `lift_diff` on few disagreements is noisy, so report
  `n_diff` with it and don't quote it under ~100 calls. The app's #1 baseline must be the same no-look-ahead version
  the "app (current #1)" row uses, or the comparison inherits its leak.

## 2026-11-21 — "Does it hold every year?": each research result split into time blocks, with a sign-consistency count
- **Area:** brain (research honesty). Reporting only.
- **Status:** built 2026-11-21, 4190d8e (Builder): `research._time_blocks` + `_metrics` blocks / pos_blocks /
  n_blocks / last_block_lift / block_spread, `luck.steady` / `steady_nw` / app_blocks / app_pit_blocks; Brain page
  "Through time." line in the luck check. Gate unchanged. Numbers appear after the next research run.
- **Problem:** every research number is one average over the whole test period (2024-12-03 on, 429 call dates,
  n = 2,703). An edge that lived in one stretch (one rally, one sell-off, one hot theme) and vanished since looks the
  same as one that held throughout, and the outlier check (lift_w, top-10 share) can't tell them apart because it
  clips single calls, not whole months. Today's numbers make it matter: the strongest fixed rule, "avoid right-skewed
  stocks (-z_rskew)", has lift +1.45% with n_eff only 922 of 2,703 calls (its calls cluster in time), and beats the
  app's #1 by +1.23% where they differ (t_nw 2.44); the learned neural net leads `is_new` (+1.23%, t_nw 2.83). Before
  anyone leans on either, the obvious question is "was it good in each part of the period, or in one?", and nothing
  stored answers it. A side observation for whoever builds this: the coskew row reports n_eff = n (2,703) with t_nw
  above t, unusual for overlapping 90-day windows, worth a glance at `_se_overlap` while in there.
- **Source:** McLean & Pontiff (2016), "Does Academic Research Destroy Stock Return Predictability?", Journal of
  Finance 71(1), 5-32 (CFA Institute digest: https://rpc.cfainstitute.org/research/cfa-digest/2016/06/does-academic-research-destroy-stock-return-predictability-digest-summary;
  author copy: https://ivey.uwo.ca/media/3775549/pontiff.pdf): across 97 published predictors, returns were about 26%
  lower out of sample and 58% lower after publication, so an average over a long window overstates what is left now.
  Bailey, Borwein, López de Prado & Zhu (2017), "The Probability of Backtest Overfitting" (J. Computational Finance)
  makes the same point with combinatorially split periods: a strategy chosen on the whole sample should keep its rank
  across sub-periods.
- **Build sketch (S):** in `research.run` / `_metrics`, split each method's test calls into K = 4 chronological blocks
  of equal call count by belief `as_of_date` (calls on one date stay in one block). Per block store `lift`, `n`,
  `beat`; per method add `blocks` (the list), `pos_blocks` (how many blocks have lift > 0), `last_block_lift`, and
  `block_spread` (max minus min block lift). `luck.steady` = methods that clear the luck bar *and* have lift > 0 in
  at least 3 of 4 blocks. Files: backend/v4/research.py, one planted test in backend/v4/tests/test_v4.py (a rule that
  only works in the first quarter of dates shows `pos_blocks` 1 and stays out of `luck.steady`; an even rule shows 4),
  one header line in docs/research_ideas.md; optionally a "held in 4 of 4 periods" note per row on the Brain page.
  Data: none new (dates are already loaded). Memory: four small sums per method, negligible on the 512Mi job.
- **How we'd know it worked:** the next run says, for example, "rskew positive in 4 of 4 blocks, latest block +X%", and
  research log entries quote pos_blocks / last_block_lift beside lift. A rule positive in only one block is read as an
  episode, not an edge, however high its t.
- **Risks:** must stay reporting only: `_passes` / `fit_production` and the luck bar's threshold are untouched
  (changing the gate is Murad's decision, written up in docs/brain_upgrades.md). Each block holds ~675 calls but only
  ~100 dates, so a block's lift is noisy: report block n and don't treat one negative block as a failure; the point is
  spotting rules carried by a single stretch. Blocks must be cut on dates, never on outcomes.

## 2026-11-21 (late) — "Would we have picked the winner?": probability of backtest overfitting across all research rules
- **Area:** brain (research honesty). Reporting only.
- **Status:** built 2026-11-22, commit "Research: would we have picked the winner? (probability of backtest overfitting)" (Builder). Built as sketched: `research.pbo` in `luck.pbo` / `luck.pbo_learned`, ranked on plain lift (not lift_adj); Brain page luck card line "Would we have picked the winner?".
- **Problem:** the research run now tries 47 ways to choose the #1 (48 after idea 19), and the honest question about the
  *process*, not any single rule, is: when we pick the best-looking way on one stretch of history, does it stay good on
  the rest? The luck bar (3.27 for 47 tries) and "Does it hold every year?" judge rules one at a time; neither measures
  how often the act of picking the winner fools us. Today's run shows why it matters: the no-look-ahead app #1 was
  ahead in its first three stretches (+1.54%, +1.20%, +1.01%) and then -1.65% in the latest (2026-02-27 to 2026-07-24,
  beat 43.5%); the stored app #1 and rskew, both near the top on the whole period (t 4.54 and 4.96), are also negative
  in the latest stretch (-0.74%, -0.39%), while the neural net, ridge, gbm and Amihud stayed positive (+0.6% to +1.7%).
  A rule chosen on the early data would not always have been the one that held up. Ranker v2 is live as the mlp
  alone, chosen exactly this way, so a single number for "how likely is the chosen one to be below median out of
  sample" is the most direct honesty check we don't have.
- **Source:** Bailey, Borwein, López de Prado & Zhu (2017), "The Probability of Backtest Overfitting", Journal of
  Computational Finance 20(4): https://papers.ssrn.com/abstract=2326253 (author copy:
  https://escholarship.org/content/qt4w1110bb/qt4w1110bb.pdf). Combinatorially symmetric cross-validation (CSCV): split
  the history into S equal blocks, and for every way of choosing S/2 blocks as "in-sample", pick the best strategy
  there and see where it ranks on the other half. PBO = share of splits where the in-sample winner ranks below the
  out-of-sample median. Also reports the slope of out-of-sample vs in-sample performance (performance degradation)
  and the chance the winner loses money out of sample.
- **Build sketch (S/M):** in `research.run`, after results are filled: cut the test-period call dates into S = 8
  chronological blocks of about equal call count (same date-cut rule as `_time_blocks`, a date never splits). For each
  method with n > 0, keep 8 (sum lift, count) pairs from the per-call lifts `_metrics` already sees (47 x 8 numbers,
  negligible on 512Mi). For each of the C(8,4) = 70 splits: IS score = pooled mean lift over its 4 blocks per method,
  winner = argmax, OOS = pooled mean over the other 4; record the winner's OOS rank fraction (logit as in the paper),
  its OOS lift, and the IS/OOS pair. Store `pbo` = {`pbo`, `n_splits`, `n_methods`, `oos_lift_med` (winner's median OOS
  lift), `p_loss` (share of splits with winner OOS lift < 0), `slope` (OOS on IS lift across splits), `winners`
  (method -> how many of the 70 splits it won)} in the research kv, and the same restricted to the learned candidates
  that `fit_production` chooses among (`pbo_learned`). Exclude the look-ahead "app (current #1)" row from the pool (use
  the no-look-ahead app row as a member). One Brain page line in the luck check: "If we had picked the best way on half
  the history, it ranked in the bottom half on the other half X% of the time." Files: backend/v4/research.py, one
  planted test in backend/v4/tests/test_v4.py (40 pure-noise rules give PBO near 0.5; one rule with a real planted edge
  plus noise rules gives PBO near 0 and wins most splits), a header line in docs/research_ideas.md,
  frontend/src/components/BrainPage.jsx. Data: none new.
- **How we'd know it worked:** the kv carries `pbo` after the next run, and the research log quotes it each day. A
  PBO well under 0.5 (the paper treats about 0.1 or less as reassuring) with the learned models winning most splits
  says our selection is picking real signal; a PBO near 0.5 says the leaderboard is mostly reshuffling noise and the
  log should say so plainly.
- **Risks:** must stay reporting only: `_passes`, `fit_production`, the luck bar and MIN_LIFT/MIN_T are untouched (any
  gate use is Murad's decision, written up in docs/brain_upgrades.md). Many rules are near-copies (momentum variants,
  gbm vs gbm-shifted), which makes PBO look better than it is; report `n_methods` and the winners table so this is
  visible. Each block holds only ~50 dates, so per-block lifts are noisy and PBO itself has sampling error; say so
  next to the number. Blocks must be cut on dates, never on outcomes, and only test-period calls (after the 90-day
  embargo) may enter.

## 2026-11-21 (night, extra run) — "I called it" cards: a share link with its own preview for every graded call, wins and misses alike
- **Area:** app (growth). Scouted on the HQ chair's sprint call (growth and launch readiness until 02:00 UTC).
- **Status:** built 2026-11-21, commit "Share: every call gets its own link with a preview card" (Builder). Built as sketched, with these differences: the link lives on the backend (`/c/<id>` on marketplayground-backend-18mm.onrender.com, since the static site can't serve per-call tags); only users' own calls (`source = 'user'`) get a card, seeded ones 404; the PNG is cached in memory (64 entries), not kv_cache; card views are counted in the backend log (`[share] card view`), not a table.
- **Problem:** the app has almost no one using it yet, and nothing inside it lets a user bring anyone else. Since Oct 1:
  34 calls from real users (`beliefs.source = 'user'`), from 7 distinct users, the last one on 2026-11-10; everything
  else (7,413) comes from our own seeders. There is no share button anywhere: the one site-wide preview
  (`frontend/index.html`, og.png "invest in what you believe") is the same for every link, so a user who wants to show
  a friend a good call has to screenshot it. Graded calls are exactly the thing worth showing: a dated, checkable
  prediction with a result against the S&P 500.
- **Evidence it works for similar products:** Wordle grew from about 90 players in November 2021 to about 2 million by
  January 2022 once the share button posted a spoiler-free grid of coloured squares; 1.2 million tweets carrying the
  grid went out on Jan 1-13, 2022 alone (BuzzFeed News: https://www.buzzfeednews.com/article/stefficao/how-wordle-went-viral-strategy;
  Smithsonian: https://www.smithsonianmag.com/smart-news/heres-why-the-word-game-wordle-went-viral-180979439/), and the
  New York Times said it brought "tens of millions" of new users after the purchase (TechCrunch:
  https://techcrunch.com/2022/05/04/wordle-new-york-times-user-growth). What carried it: one result per day, compact,
  same format for everyone, and the link leads straight into playing. Research on sharing points the same way: Berger
  & Milkman (2012), "What Makes Online Content Viral?", Journal of Marketing Research
  (https://faculty.wharton.upenn.edu/wp-content/uploads/2011/11/Virality.pdf), found useful and emotionally arousing
  content (surprise, excitement, even anxiety) is shared more; a call that beat or missed the market is both.
- **Build sketch (M):**
  - Backend (backend/v4/router.py, new backend/v4/share.py): `GET /c/{belief_id}` returns a tiny HTML page with
    per-call `og:title` / `og:description` / `og:image` / `twitter:card` tags and an instant redirect to
    `https://marketplayground-web.onrender.com/welcome?ref=card&c={belief_id}` (crawlers read the tags, people land in
    the app). `GET /c/{belief_id}.png` renders a 1200x630 card with Pillow (already in requirements.txt): the belief
    in quotes, the date it was made, the #1 pick and direction, the latest graded checkpoint ("90 days: +6.1% vs the
    S&P 500" or "Missed: -3.2% vs the S&P 500"), the user's stated "How sure" if set, and the footer "Practice call,
    graded against the S&P 500 at 30/60/90 days. MarketPlayground". Cache the PNG in kv_cache by belief id +
    checkpoint so it renders once. Data: what `engine.get_belief` already returns, nothing new.
  - Wordle-style copy text for chats where previews don't show: e.g. "My call: 'AI chips keep running' NVDA long,
    Nov 2 / 30d 🟩 60d 🟩 90d 🟥 vs S&P / marketplayground-web.onrender.com/c/<id>" (green = ahead of the S&P at that
    checkpoint, red = behind, grey = not graded yet).
  - Frontend: a "Share" button on each graded call in MyCallsPage.jsx and on the graded result view, using
    `navigator.share` on phones with a copy-link fallback; WelcomePage.jsx shows "<the shared call> — make your own
    call" above sign-up when `c` is present, and keeps `ref=card` with the sign-up so it can be counted.
  - Test (backend/v4/tests/test_v4.py): the share page carries the call's own og tags and the redirect; an ungraded
    call shows "not graded yet", never a result; a belief id that doesn't exist is a 404; the copy text marks each
    checkpoint from the stored grades only.
- **How we'd know it worked:** count shares (button taps), card visits (`/c/` hits), and sign-ups carrying `ref=card`
  per week. Worth keeping if real users' weekly calls rise above the current ~0 and at least some sign-ups come from
  cards within a month; the growth report already watches `ref` visits (docs/growth_plan.md).
- **Risks and guardrails:** honest by construction. Only graded checkpoints are shown, misses look the same as wins
  (no cherry-picked "I called it" for losing calls, no ungraded call shown as a win), returns always against the
  S&P 500 and always labelled practice, and no claim beyond the call itself (no "the AI beats the market"). Privacy:
  no user name or email on the card or page, just the call; sharing is opt-in per call and the link reveals only that
  belief, which `/v4/belief/{id}` already serves publicly. The PNG renderer must cap text length and handle any
  ticker or quote safely (escape in the HTML, wrap in the image). No posting on anyone's behalf: the user shares it
  themselves. Nothing touches real-money behaviour or research gates.

## 2026-11-22 — "Many weak signals, one vote": an equal-weight composite of the research rules, chosen inside each fold
- **Area:** brain (accuracy and honesty of research). Reporting only: a new research row, never the live ranking.
- **Status:** built 2026-11-22, commit "Research: many weak signals, one vote (equal-weight composite chosen in-fold)" (Builder). Built as sketched: `research.composite_members` / `composite_scores` / `composite_summary`, method "equal-weight composite (chosen in-fold)", `out["composite"]`, `luck.composite`, Brain page luck card line "Many weak signals, one vote.". Differences: each kept rule's scores are z-scored within the belief before averaging (several rules aren't single z's, e.g. the VP and MuLine blends); provisional rules (input still filling in) can't join.
- **Problem:** research now tests 49 single rules (50 with today's idea 21), and the leaderboard of which one is "best"
  reshuffles. Run 2026-11-22 17:21 UTC (n=2,703 test calls, test from 2024-12-03): PBO 0.343 over 48 methods, and the
  in-sample winner of the 70 splits was spread over 12 different rules (rskew 21, neural net 16, amihud 7, frog-in-the-
  pan 7, ldvol 6, high vol 6, ...), with a median out-of-sample lift of only +0.63%. Several rules each carry a little
  real, partly different information (rskew raw +lift, t above the 3.28 bar; amihud +1.21%, t 4.04, 4 of 4 stretches;
  coskew in `clear_adj_nw`; ldvol +0.81%, t 2.90), but every rule is judged alone, so nothing tests whether averaging
  them is steadier than betting on whichever is ahead. Meanwhile the app's own #1 was behind our other ideas in its
  latest stretch (Feb-Jul 2026 lift -0.74%, -1.65% without the peek), so a sturdier baseline matters.
- **Evidence:** in portfolio choice, the naive 1/N mix beat 14 optimized models out of sample on most datasets
  because estimated weights are too noisy (DeMiguel, Garlappi & Uppal 2009, "Optimal versus naive diversification: how
  inefficient is the 1/N portfolio strategy?", Review of Financial Studies 22(5), 1915-1953:
  https://ideas.repec.org/a/oup/rfinst/v22y2009i5p1915-1953.html). In forecasting the same "forecast combination
  puzzle" holds: a simple average of forecasts usually beats estimated "optimal" weights, and Claeskens, Magnus,
  Vasnev & Wang (2016), International Journal of Forecasting 32(3), 754-762
  (https://econpapers.repec.org/RePEc:eee:intfor:v:32:y:2016:i:3:p:754-762) explain why: estimating weights adds
  variance that eats the gain. Review: Wang, Hyndman, Li & Kang (2022), "Forecast combinations: an over 50-year
  review" (https://arxiv.org/pdf/2205.04216).
- **Build sketch (S-M):**
  - backend/v4/research.py, in run(): for each walk-forward fold, using only that fold's *training* calls (same
    embargo), score every fixed rule (not the learned ones, not "app (current #1)", which has look-ahead) and keep the
    ones with training lift > 0 and plain t >= 2 (a fixed, pre-stated cutoff; at most, say, 8, ranked by training t,
    and dropping a rule whose training-period #1 matches an already-kept rule's more than 70% of the time so near
    copies don't double-vote). On the fold's test calls the composite score is the plain average of the kept rules'
    scores (each already a z-score within the belief, so they're on the same scale); no fitted weights. If no rule
    qualifies, fall back to the app's no-look-ahead order. Report it as a new method "equal-weight composite (chosen
    in-fold)" with all the usual metrics (lift, t, t_nw, lift_w, blocks, same_as_app / lift_diff) plus
    `composite_members` = how often each rule was kept across folds.
  - It counts as one more try for the luck bar and joins the PBO pool like any rule.
  - Test (backend/v4/tests/test_v4.py): plant two weak independent signals each under t 3 alone; the composite should
    beat both; a rule that only works in the test period must never be selected (selection sees training calls only);
    with no qualifying rule it equals the app's no-look-ahead row.
  - Memory: reuses the per-rule scores already computed per fold; no new features, no new data. Fine on 512Mi.
- **How we'd know it worked:** on the same run, the composite has a higher lift_t_nw than the median single rule and
  at least the best single rule's pos_blocks (3+ of 4), and it is not just the app restated (lift_diff > 0 on a few
  hundred differing calls). If it beats every single rule out of sample it is evidence the brain should combine
  rather than pick one; if it doesn't, that's informative too (the rules share one source of edge).
- **Risks and guardrails:** the selection step is where cheating would hide, so it must use training calls only and
  the cutoff (t >= 2, max 8) is fixed in code before the run, never tuned on test results. Reporting only: it doesn't
  touch `_passes`, `fit_production` or ranker v2's activation rules; whether a composite could ever compete for the
  live #1 is a separate, deliberate decision for Murad written up in docs/brain_upgrades.md. Near-copy rules
  (rskew/max5, amihud/ldvol) are why the overlap filter is there.

## 2026-11-23 — "Put it on your home screen": a real install button, asked at the right moment, and counted
- **Area:** app (getting the phone app into people's hands; answers Murad's HQ message #1, "mobile app vs online app").
- **Status:** built 2026-11-24, commit "Home screen: offer the installable app after a first call, and count it" (Builder). Built as sketched, with these differences: offered on Home only once this device has made a call (recent beliefs), one ask at a time (Face ID, then this, then alerts); on iPhone the steps also mention Safari 26's ••• menu and other iPhone browsers get "open in Safari" as a fallback, not as the only path; counts live in a small `install_counts` table (day, kind, n), each device once per kind per day, capped per day, shown on Agent HQ as the last 7 days.
- **Problem:** the site is already an installable phone app (frontend/public/manifest.webmanifest, sw.js, icons, push
  alerts in AlertsCard), and the chair's HQ reply recommends staying on that path ("home-screen app") while
  invite-only, then an app-store wrapper later. But nothing ever *offers* the install: there is no install button
  anywhere, the only mention is an iPhone hint inside AlertsCard (Account page and the tool picker), and we can't tell
  how many people installed. Evidence from the database today: `push_subs` has **0** rows, and since Oct 1 there were
  only 7 real users making 34 calls. On iPhone, alerts only work after Add to Home Screen, so 0 alert subscribers is
  partly an install problem. Before paying for app-store accounts and a wrapper (path 2), we should know whether
  people install at all when asked well.
- **Evidence:** Google's PWA guidance (web.dev, "Patterns for promoting PWA installation",
  https://web.dev/articles/promote-install; "Installation prompt", https://web.dev/learn/pwa/installation-prompt;
  "How to define your install strategy", https://web.dev/articles/define-install-strategy): wait for the
  `beforeinstallprompt` event, call `preventDefault()`, keep it and show your own button; offer it after the user has
  shown interest or right after a "conversion" moment (sign-up, a completed action), never on first load and never
  inside a task; always dismissible, remembered, and re-offered only after the relationship changes; iPhone/iPad
  never fire the event (Chrome and Edge on iOS can't install either), so show Safari's Share -> Add to Home Screen
  steps only when `display-mode` is `browser`; measure with the `userChoice` outcome and the `appinstalled` event.
  Those pages are 2019-2022 and give no hard numbers of their own, so we should measure our own rate rather than
  borrow case-study figures.
- **Build sketch (S):**
  - New `frontend/src/lib/install.js`: listen for `beforeinstallprompt` once at startup (main.jsx), store the event;
    `canInstall()`, `isInstalled()` (`matchMedia('(display-mode: standalone)')` or `navigator.standalone`),
    `isIOS()`, `promptInstall()` (calls `prompt()` once, returns 'accepted'/'dismissed'); `appinstalled` listener.
  - New `frontend/src/components/InstallCard.jsx`: one card, two versions. Android/desktop: "Add MarketPlayground to
    your home screen: it opens full screen and can tell you when the market opens" + one button. iPhone in Safari:
    the same line with the two-step Share -> Add to Home Screen picture; iPhone in another browser: "open this page in
    Safari to add it". Hidden when already installed. "Not now" remembers for 30 days (localStorage, in try/catch).
  - Where: right after a user saves their first call (the conversion moment) and once in the Account page menu; not
    on the Welcome page, not over chat. AlertsCard reuses the iPhone steps from InstallCard instead of its own text.
  - Counting (tiny, no personal data): `POST /v4/install/event` with {kind: shown | accepted | dismissed |
    installed | opened_standalone}, stored as a daily count per kind in kv_cache (or a small table); the Brain or HQ
    page shows "installs this week". `opened_standalone` is sent once per day per device from main.jsx so we see
    actual home-screen use, not just installs. Test: the endpoint only accepts the five kinds and rate-limits.
  - No app-store work, no new accounts, no money; push and grading untouched.
- **How we'd know it worked:** after 2-4 weeks, of users who saw the card, what share accepted (Android) or later
  opened standalone (iPhone); `push_subs` above 0; and whether standalone users come back more often than browser
  users over the following weeks (compare return visits, with the caveat that keen users are the ones who install, so
  this is not proof the install causes it). If almost nobody installs even when asked at the right moment, that is
  a reason to rethink an app-store wrapper too, since a store listing mainly removes the "how do I install" step.
- **Risks:** nagging (one card, dismissible, remembered, never on first visit); Safari changes its Add to Home Screen
  flow from time to time, so the iPhone picture needs a check per iOS release; counts are rough (private mode and
  cleared storage double-count `opened_standalone`). No claims about results in the card copy.
