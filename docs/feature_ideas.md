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
  pick features for research.
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
  call. Not built yet: the "Did that happen?" answer, push alerts on a crossing, research use.
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
- **Status:** proposed
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
