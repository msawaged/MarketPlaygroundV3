# Feature ideas backlog

Proposals for Murad and the other Claude sessions: one well-sourced idea per entry for the app (users) or the brain
(ranking, grading, honesty). Written by the daily CTO scout routine; nothing here is built until someone picks it up.
Status: **proposed** → accepted / rejected / built (with the commit). Ideas that would loosen research gates, use
look-ahead, change real-money behaviour or claim more than the data shows are never proposed.

---

## 2026-11-11 — "How sure are you?": user-stated probability and a personal calibration score
- **Area:** app (learning loop), with a small brain benefit.
- **Status:** proposed
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
- **Status:** proposed
- **Problem:** every `research:ranker` run scores 37 methods on the same 2,703 test beliefs (run 2026-11-12 10:03 UTC:
  37 entries in `results`), and the daily routine adds one more rule a day (9 so far). The idea log then reads each
  rule's t-stat against the usual 2.0 bar. With 37 tries, the biggest |t| from pure noise is expected to be around
  2.5-3, so "t 2.9" (frog in the pan, today) or "t 3.0" (intermediate momentum, today) can be luck; a Bonferroni 5%
  two-sided bar for 37 tests is |t| ≈ 3.21. Today 10 of 37 clear it: the app's #1 (4.54), the Amihud rule (3.98), plain
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

