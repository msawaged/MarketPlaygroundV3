# Brain upgrades log

One entry per weekly CTO upgrade. Each entry: the problem (with real numbers), what changed, the commit, and what
would count as a win. Ranking-feature ideas live in `docs/research_ideas.md` instead.

## 2026-11-03 — Network learns the within-belief label (ranking), not the belief-level noise

**Problem.** The neural network has never left shadow. Latest walk-forward (2026-11-02 23:11 UTC, 11,514 train /
3,299 test rows, 845 test beliefs, cutoff 2026-01-15): top-pick lift **-1.13% (t = -2.43)**, Spearman -0.034,
test MSE 0.0350 vs 0.0290 for just predicting the average (20% worse than a constant), blend gain vs Claude -0.24%.
Meanwhile ranker v2 (gradient-boosted trees on the same numeric features, trained on *within-belief* returns) is
active at +1.80% lift, t = 4.7, out of sample.

Diagnosis from the database (90-day checkpoint, stock picks with a sel_edge label):
- **35% of label variance is between beliefs** (total var 0.0264, within-belief 0.0171; 41% for beliefs benched
  against a fund). That part says whether a belief's stocks as a group beat their fund. It cannot help choose
  between ideas, and the only inputs that can fit it are belief text and theme hashes, so the network memorizes them.
- Memorized ticker history doesn't carry over: per ticker+direction, mean label before vs after the cutoff
  correlates at **0.02** (362 tickers).
- Ridge on the same inputs is also negative (lift -0.45%, Spearman -0.04), so it's the target, not the MLP shape.

**Change.** `nn.train()` now trains on each pick's label minus its belief's average (`nn.within_belief`), the same
target ranker v2 uses (`research.load()` → `rel`). Beliefs with only one graded idea are dropped from training
(nothing to compare). Evaluation is untouched: lift, t, Spearman, blend trials and every promotion gate
(`MIN_T`, `MIN_TEST_BELIEFS`, rho > 0.03, beats Claude) are still computed on the raw label, with the same
walk-forward split and 90-day embargo. Metrics record `label_mode`. `MP_NN_LABEL_MODE=raw` restores the old target.
No new memory: same matrices, slightly fewer rows.

**Checks.** Backend tests: 88 passed. Offline `ml_check` (full): same verdict as the old label (signal worlds
active at 800 beliefs: 1 of 2 both ways; no-signal worlds promoted: 0 of 6 both ways); peak training memory 278 MB.
The synthetic world mostly uses basket benchmarks, where the label is already near-demeaned, so it can't show the
effect; the real data (84% fund-benched rows) is where it should matter.

**Commit.** See `git log --grep "within-belief"` on v4-polish (this entry ships in the same commit).

**What counts as a win.** Over the next nightly retrains: test MSE no longer worse than baseline by ~20%,
Spearman ≥ 0, and top-pick lift turning positive (≥ 0 with t > 0). A real win is the first version promoted to
*active* through the unchanged gates. If lift stays ≤ -1% for a week, the next suspect is the 6k hashed
text/ticker inputs themselves (try numeric-only inputs, as ranker v2 does).

## 2026-11-04 — Network trains on the numbers only (drop hashed text/ticker inputs)

**Problem.** Last week's within-belief label helped but did not fix the network. First retrain on it
(2026-11-03 23:53 UTC, 11,408 train / 3,299 test, 845 test beliefs, cutoff 2026-01-15): top-pick lift **-0.70%
(t = -1.47)**, Spearman **-0.052** (now *rejected*, below the -0.05 shadow floor), test MSE 0.0317 vs 0.0287 for a
constant. Ridge on the same inputs: lift -0.31%, Spearman -0.045. Ranker v2 (trees on numbers only) is active at
+2.00% lift, t = 4.93.

Ablation on production data (all 16,402 graded 90-day picks with a sel_edge label, pulled read-only; same
walk-forward split, within-belief label, same 3-net ensemble, seeds 7/8/9):

| inputs | lift | t | Spearman | test MSE |
|---|---|---|---|---|
| numbers only (`MODEL_NUMERIC`) | +0.39% / +0.54% / +0.69% | 0.8 – 1.4 | +0.006 – +0.014 | 0.0289 |
| numbers + hashed ticker only | -0.69% / -0.77% / -0.85% | -1.5 – -1.9 | -0.062 – -0.064 | 0.0308 |
| production (numbers + ticker + themes + text) | -0.70% | -1.47 | -0.052 | 0.0317 |

The hashed ticker column alone accounts for the whole negative result: the network memorizes which tickers did well
before the cutoff and that reverses afterwards (last week: per-ticker mean label before vs after correlates at 0.02).
Belief text is constant inside a belief, so under the within-belief label it can only add noise.

**Change.** `nn.vectorize` now feeds only `MODEL_NUMERIC` by default (`MP_NN_INPUTS=numeric`; `all` restores the old
inputs). Each version records `inputs` in its metrics, and `nn.predict` scores a stored version with the inputs it was
trained on (versions saved before this field existed are treated as `all`), so the current shadow model keeps working
until a new version replaces it. Evaluation, the walk-forward split, the embargo and every promotion gate
(`MIN_T`, `MIN_TEST_BELIEFS`, rho > 0.03, beats Claude) are unchanged. Memory goes down (15 dense columns instead of
6,159 sparse ones). Not a user-facing change: the network still has blend weight 0 unless it passes the gates.

**Checks.** Backend tests: 96 passed (new: `test_network_uses_numeric_inputs_and_scores_old_versions_with_theirs`).

**Commit.** See `git log --grep "numeric inputs"` on v4-polish (this entry ships in the same commit).

**What counts as a win.** Next nightly retrains: status back to *shadow* (Spearman > -0.05), Spearman ≥ 0, top-pick
lift > 0, and test MSE within ~1% of the constant baseline. The offline ablation says that much is likely; it does
*not* say the network will clear the active gate (t ≈ 1, rho ≈ 0.01 < 0.03). If it plateaus there, the next suspect is
that the network sees fewer numbers than ranker v2 (no 12-1/residual momentum, volume profile, MuLine or regime
features, and no direction-signing of momentum) — but adding those is a feature change, so check with the idea scout's
work first.

## 2026-11-05 — Score the #1 pick against a risk-matched S&P, not just the S&P

**Problem (real numbers, research:ranker, 2,707 unseen calls).** Ranker v2 (gbm) beat the S&P 53.5% with +2.16 pts
lift (t 5.39). But the plain rule "pick the most volatile candidate" scored 53.6% (+1.55 pts, t 3.52) and "pick the
calmest" lost (-1.02 pts, t -4.63). In a rising 2024-26 market, riskier stocks outrun the S&P by construction, so a
large part of the edge may be beta, not skill. A finance reviewer would call that out immediately.

**What changed.**
- `market.beta_value`: each pick's 252-day beta vs SPY, as of the pick's own date (point-in-time). Stored on new picks
  (`nn.make_features` num) and backfilled on graded picks by `research.enrich`.
- `research.load`: risk-matched outcome `exa = dir * (ret - beta * spy_ret)` next to the plain one.
- `research._metrics`: every idea now reports `beat_adj`, `lift_adj`, `lift_adj_t` too. New learner in the race:
  `gbm (risk-adjusted)`, trained on risk-matched outcomes. Output adds `beta_coverage`.
- Gate (stricter only): once >=80% of graded picks carry a beta, the production ranker must also show
  `lift_adj > 0` and `lift_adj_t >= 1.0`. Among passing candidates (ridge, gbm, gbm risk-adjusted), the one with the
  biggest risk-matched edge goes live. If none passes, the ranking falls back to the old way and the page says so.
- Brain page shows the risk-adjusted result once the check is on.

**What counts as a win.** After the backfill (~a day), a candidate with `lift_adj_t >= 1.0`. If the gbm's edge
collapses on a risk-matched basis, that's an honest finding: the next upgrade should hunt for edge beyond beta
(the risk-adjusted learner is that hunt), not more volatility exposure.

## 2026-11-05 — Ranker v2 stops counting 'volatile' ideas as skill (it turns off until it earns it back)

**Problem.** A 'volatile' idea is graded on `|stock move| - |S&P move|` (grader.py), which a single stock beats about
75% of the time no matter what (90-day beat rate 73.9% vs 46.8% bullish / 59.0% bearish, avg +15.0% vs +0.6% / +1.7%).
`research.load()` put these 620 graded ideas (2.7%) in the same within-belief comparison as directional ideas, in
576 of 4,398 beliefs. Choosing the volatile idea there looked like a big win, and high-volatility features point to it.

Replaying `research.run()` + `fit_production()` on production data (all 23,279 graded 90-day picks, read-only):

| ranker | with volatile ideas: lift / t / beat | directional only: lift / t / beat |
|---|---|---|
| app (old #1) | +0.02% / 0.08 / 52.3% | +0.37% / 1.34 / 52.3% |
| high vol | +1.55% / 3.52 / 53.6% | +0.87% / 2.04 / 51.9% |
| gbm (live ranker) | +1.83% / 4.55 / 52.9% | +1.01% / 3.01 / 51.5% |
| gbm (risk-adjusted) | +0.66% / 1.95 / 52.2% | +0.94% / 2.81 / 51.7% (risk-matched lift +0.99%, t 3.10) |

About 45% of the live ranker's raw lift, and its whole beat-rate edge over the app, came from this mix.

**Change.** `research.directional()`; `load()` drops non-directional ideas from ranker v2's training and evaluation;
`score_candidates()` scores directional ideas among themselves and gives a volatile idea their average, so the ranker
never moves it (and returns None with fewer than 2 directional ideas). No gate changed (`MIN_LIFT`, `MIN_T`,
`MIN_T_ADJ`, `_passes`, beat ≥ app, 90-day embargo).

**Effect, on purpose.** On the clean data no candidate clears `beat ≥ app` (best: gbm risk-adjusted 51.7% vs 52.3%),
so the next nightly refit will switch ranker v2 **off** and users' #1 pick goes back to the old ranking. Its lift is
real and survives risk matching (+0.9%, t ≈ 3), but it picks the S&P-beating idea slightly less often than the app,
and the gate says that isn't enough. It was only "on" because of the grading mix-up.

**Checks.** Backend tests: 99 passed (new: `test_ranker_v2_leaves_out_volatile_ideas`).

**Commit.** See `git log --grep "volatile ideas"` on v4-polish (this entry ships in the same commit).

**What counts as a win.** The Brain page's ranker numbers drop to the honest level (lift ≈ +1%, beat ≈ 51.5%) and
`active` goes false. The real win is ranker v2 turning back on through the unchanged gate on directional ideas only.
The obvious next lever is the beat rate, not the lift: the risk-adjusted gbm is 0.6 points short. Not yet fixed: the
network and lineages still see volatile ideas in their labels (much smaller share, and the network is at weight 0).
