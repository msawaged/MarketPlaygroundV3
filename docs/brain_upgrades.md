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
