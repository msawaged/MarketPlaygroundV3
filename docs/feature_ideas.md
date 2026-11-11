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
