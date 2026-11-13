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

## 2026-11-06 — First risk-matched results; beat-rate check made risk-matched

**Results (2,703 unseen directional calls, betas on 100% of graded picks, volatile ideas excluded per e0f186d).**

| | beat S&P | beat risk-matched S&P | edge vs other ideas, risk-matched |
|---|---|---|---|
| old way | 52.3% | 52.9% | +0.31 pts (t 1.16) |
| gbm (raw labels) | 52.0% | 52.7% | +0.88 pts (t 2.68) |
| gbm (risk-adjusted labels) | 51.9% | 53.6% | +0.97 pts (t 3.03) |
| "pick the most volatile" | 51.9% | 52.7% | +0.49 pts (t 1.19) |

Part of the earlier edge was risk (the volatile rule loses most of its edge once risk-matched), but a learned edge
survives: the risk-adjusted gbm's risk-matched lift is t 3.0. The ranker had turned off only because the gate still
compared *raw* beat rates (51.9% vs 52.3%), which reward holding riskier stocks.

**Change (post-hoc, flagged as such).** With the risk check on, `_passes` compares beat rates on the risk-matched
basis, requires the risk-matched lift > 0 with t >= 1.0, keeps lift >= 0.005 and t >= 1.5, and allows the raw beat
rate to trail the old way by at most 1 point. This was decided after seeing the results, so watch it: if the
risk-adjusted gbm's lift_adj_t drops below ~2 over the next weeks of new graded calls, revisit.

**What counts as a win.** The risk-adjusted gbm stays active with lift_adj_t >= 2 as new calls are graded, and the
live record of its picks (not the backtest) beats a risk-matched S&P more often than the old way.

## 2026-11-06 (weekly) — Lineages compete on directional ideas only (the 'volatile' grading mix-up, part 2)

**Problem.** The 2026-11-05 fix took 'volatile' ideas out of ranker v2 but noted the lineages still saw them. They
still do, and it matters there: a volatile idea is graded on `|stock move| - |S&P move|`, so it "wins" most of the
time regardless of skill. Replaying each alive strategist's choices on production data (read-only SQL, 90-day
checkpoint; the replay reproduces the stored fitness exactly for 6 of 8 strategists):

- In the 300-belief scoring window, 30 beliefs (10%) had a volatile idea, averaging **+10.7%** vs **-0.9%** for the
  same beliefs' directional ideas.
- Follow-the-AI strategists chose the volatile idea in 25 of 300 beliefs (their Claude-score features are 0 on
  backfill, so they pick by tie order). Follow-the-AI Gen 5: fitness **2.41% → 1.68%** without volatile ideas.
  Momentum Gen 1: 2.17% → 1.89%. Trend-riders barely move (3–5 volatile choices; 2.64% → 2.61%).
- Live records (calls created after birth, the champion gate's input): Follow-the-AI Gen 2 **2.63% → 1.22%**
  (366 of 3,618 choices were volatile ideas), Momentum Gen 1 2.10% → 1.44%. The app's own #1 on directional ideas
  scored 2.51%. Follow-the-AI Gen 2 is the strategist closest to earning a champion's 25% say in real rankings
  (page: live 2.44% vs app 2.40%), and on the honest basis it is far behind.

So evolution was partly selecting for "happens to pick the volatile idea", and the champion gate could have been
passed the same way.

**Change.** `lineages.directional()`; `_graded_beliefs()` drops non-directional ideas, so fitness, evolution, live
records and the app baseline all compare bullish/bearish ideas only. New `lineages.score_candidates()`: a champion
scores directional ideas among themselves and gives a volatile idea their average (never reorders it; None with
fewer than 2 directional ideas); `engine.process_belief` uses it. No gate changed (`LIVE_MIN`, `LIVE_MARGIN`,
beat ≥ app, `CHAMPION_WEIGHT`); ranker v2 and the network are untouched (the network's training rows have only 22
volatile ideas with a `sel_edge`, so it was not affected). No extra memory.

**Checks.** Backend tests: 106 passed (new: `test_lineages_leave_out_volatile_ideas`).

**Commit.** See `git log --grep "Lineages compete on directional"` on v4-polish (this entry ships in the same commit).

**What counts as a win.** After the next nightly evolve: Follow-the-AI fitness drops on the page and the Trend-rider
line leads; no champion appears on the old artifact. The real win is a strategist later earning champion through the
unchanged gate on directional ideas only. Known leftover (not fixed, separate issue): on backfill beliefs Claude's
score is hidden, so Follow-the-AI picks by database tie order; its record there is noise, not skill.

## 2026-11-08 — The neural network joins ranker v2's competition (same inputs, labels, walk-forward and gate)

**Problem.** The standalone network (`nn.py`) has never left shadow: retrains on identical data scored lift
+0.54% / +0.78% / +0.45% (t 1.13 / 1.62 / 0.94) on Nov 4–6, and the spread between those runs came from row order,
not data (`_training_rows` had no ORDER BY). It also sees only 15 raw numbers, while ranker v2's trees see ~40
direction-signed, within-belief z-scores and are active.

**Test (offline, production data, 23,279 graded 90-day picks, ranker v2's exact 5-fold walk-forward with the
90-day embargo).** A small MLP (one hidden layer of 32, alpha 1.0, 5 seeds averaged, inputs standardized) trained on
ranker v2's own inputs and label:

| candidate | lift / t / beat | risk-matched lift / t / beat |
|---|---|---|
| app (old #1) | +0.37% / 1.34 / 52.3% | +0.32% / 1.18 / 52.9% |
| gbm | +1.01% / 3.01 / 51.5% | +0.62% / 1.92 / 52.3% |
| gbm (risk-adjusted) | +0.94% / 2.81 / 51.7% | +0.99% / 3.10 / 53.6% |
| **neural net** | **+1.16% / 3.46** / 51.7% | +0.61% / 1.90 / 52.1% |
| neural net (risk-adjusted) | +0.48% / 1.47 / 51.4% | +0.67% / 2.13 / **53.7%** |

Robustness (same harness, not used to pick settings): other seeds 1.09% (t 3.2), alpha 0.1 1.36% (t 4.1), alpha 3
1.03% (t 3.0), two layers 0.76% (t 2.2). So with the right inputs and target the network is a real contender; the
old network's problem was its inputs and target, not the architecture.

**Change.**
- `research.MLPRanker` + `_fit_mlp`; `run()` adds "neural net (learned)" and "neural net (risk-adjusted)";
  `fit_production()` adds candidates `mlp` / `mlp_adj`. The best candidate that clears the **unchanged** gate
  (`_passes`, risk-matched edge when the risk check is on) goes live; a winning net is stored in the same kv slot as
  the trees and `score_candidates` uses it. On the offline data the trees (gbm_adj) still win on risk-matched edge,
  so nothing changes for users until the network earns it.
- `nn._training_rows` reads rows in a fixed order, so the same data trains the same network.
- Cost: run + refit 83 s, peak 256 MB in the offline harness (cron limit 512 Mi; the refit already runs in its own
  process).

**Checks.** Backend tests: 108 passed (new: `test_ranker_v2_neural_net_competes_on_the_same_walk_forward`).

**What counts as a win.** The Brain/ranker numbers list the neural-net candidates; a real win is a net candidate
becoming the live ranker through the same gate, or the old network's nightly scores no longer jumping on identical
data.

## 2026-11-08 — Time-shifted practice calls: more graded training data with no Claude spend

**Problem.** Data is the limit. Graded 90-day ideas barely grow (108,002 → 108,779 in a week); real users' calls
start grading in late January; more Claude backfill costs money. A learning curve on ranker v2's own walk-forward
(training on 25/50/75/100% of the available beliefs) put the live model type's risk-matched lift at +0.36% / +0.19% /
+0.62% / +0.99%: noisy, but rising with data.

**Change.** `backend/v4/augment.py`: each practice belief's basket of directional ideas is re-scored at its date
±91 days (`MP_AUG_SHIFTS`), with features from `market.features(ticker, shifted_date)` (prices up to that date only)
and the 90-day outcome after it, stored in `aug_ideas`. The hourly seeder job adds a batch (`MP_AUG_BATCH`, 120
baskets, 4-minute cap). Research:
- shifted calls are training data only: every test, fixed rule and baseline (including "app (current #1)") is on
  real calls, unchanged;
- a shifted call trains a fold only when its own date AND its source belief's date are before that fold's cutoff
  (90-day embargo; no test belief lends its basket);
- they enter as their own candidates, "gbm (+ shifted)" and "gbm (risk-adjusted, + shifted)", so the walk-forward
  decides; `fit_production` picks among all candidates through the unchanged gate; if a "+ shifted" one wins, the
  live model is fit on real + shifted.
- Memory: `research.load` now builds compact rows directly (no per-idea dict of Python floats) and model matrices
  are sliced from them (`_matrix`). With a simulated 45k shifted ideas the run + refit stayed ~320 MB; cap
  `MP_AUG_MAX` = 40,000 shifted ideas.

**Known limit.** Claude picked the basket with today's knowledge (the same hindsight the practice calls already
have); shifting dates adds no new outcome information, and tests stay on real calls only.

**Checks.** Backend tests: 111 passed (new: `test_time_shifted_practice_calls_are_training_only`,
`test_research_adds_shifted_candidates_without_touching_tests`).

**What counts as a win.** Once a few thousand baskets are shifted (~1–2 days of hourly batches), "+ shifted"
candidates beat their plain versions on the same test, and one becomes the live ranker through the gate.

## 2026-11-08 — Off-by-one: every "app #1" comparison was reading the #2 idea; confidence thirds

**Bug.** The engine stores `final_rank` from `enumerate()` (0 = the #1 idea people see; production: every belief has
a rank 0). Research's "app (current #1)" baseline, the lineages' app baseline and the Brain scorecard all used
`final_rank == 1`, i.e. the **#2** idea. On the walk-forward test (2,703 real practice beliefs):

| | lift / t / beat | risk-matched lift / t / beat |
|---|---|---|
| what the gate compared against (the #2 idea) | +0.37% / 1.34 / 52.3% | +0.32% / 1.18 / 52.9% |
| the real app #1 | **+1.49% / 4.54 / 53.4%** | **+1.24% / 3.87 / 54.2%** |
| best learned candidate (gbm risk-adjusted) | +0.93% / 2.80 / 51.7% | +0.99% / 3.10 / 53.6% |

Live forward test, 7 days (108 real-time calls): the real #1 is **+1.12% vs its own belief's other ideas (t 1.24)**;
the #2 was -0.33%. So "the #1 pick trails at 7 days" (logged earlier today) was the #2.

**Change.** `research.load`, `lineages._graded_beliefs`, `brain._skill` and `brain._forward` read rank 0. Gate code
unchanged; it now compares against the real #1, a higher bar. Expected effect at the next refit: ranker v2 and the
neural net **turn off** (no candidate beats the app's own #1 on its own) and the #1 goes back to the app's ordering.
Caveat: on practice calls Claude's ordering may carry hindsight (it knows how 2023–25 went), which makes this bar
conservative; the live forward test is where the ranker has to prove itself. Offline, blending a model into the
app's score at 25% (what production would do when a ranker is active) added only ~+0.2 pts risk-matched over the app
alone (gbm risk-adjusted @0.25: +1.43%, t 4.56 vs app +1.22%, t 3.85); not shipped as a gate change.

**Confidence thirds (new).** How far the #1 idea's score stands out from its belief's average sorts outcomes. On the
walk-forward test, by thirds of that spread: gbm risk-adjusted's most confident third beat a risk-matched S&P
**57.8%** of the time (least confident 49.2%); the neural net (risk-adjusted) **60.2%** (50.4%); the app's own score:
lift +2.46% in its top third vs +0.93% in its bottom. `research.run` stores `confidence` (cuts + thirds) per learned
candidate and for the app; `fit_production` keeps the cuts for whatever orders the live #1 (the active model, else
the app's score); the engine labels the live #1 `confidence: high/medium/low` and stores `rv2_conf` with the pick;
`/v4/brain` `forward.by_confidence` tracks the live result by label. Picks also keep `rv2` (ranker score) and research
rows carry the app's `final_score` (`app`) for later analysis.

**Checks.** Backend tests: 113 passed (new: `test_the_app_number_one_is_final_rank_zero`,
`test_ranker_confidence_thirds_and_live_label`; `test_brain_forward_test_counts_only_live_calls` now uses rank 0).

**What counts as a win.** Brain scorecard and forward test show the real #1; over the coming weeks the live
"high-confidence" #1 calls beat the S&P clearly more often than "low" ones (the 30- and 90-day columns).

## 2026-11-09 — Gate amendment (Murad's decision, option B): test each model the way it would go live

**Why.** Ranker v2 is never used on its own: when active, the engine mixes its score into the app's own score. The gate
compared the model *alone* with the app alone, i.e. something users never get. Murad chose (2026-11-09) to also test
each model as the mix that would go live, at 25%, with an extra real-time requirement.

**Change.**
- `research.mix_scores` reproduces the engine's mixing (model z-scored within the belief, clipped ±2, put on the app
  score's spread, weight `MIX_WEIGHT` = 0.25). `run()` adds "<model> + app (25%)" for every learned model, on the same
  walk-forward test, with confidence thirds.
- `fit_production` adds `<key>_mix` candidates. They must pass the **same, unchanged `_passes`** against the app's real
  #1 **and** `live_check`: on at least `LIVE_MIN_CALLS` = 300 calls made in real time (never practice; all after every
  training outcome) graded at `LIVE_DAYS` = 30 days, the mix's #1 must do at least as well as the app's #1 (average
  move vs the S&P). Models alone keep the old rule. A live mix runs at its tested weight (`ranker.weight`, engine reads
  it); confidence for a mix comes from the mixed score. The ranker record shows `live` (n so far, needed, mix vs app)
  for the strongest mix even while it can't go live.
- Why 30 days: the ranker learns 90-day outcomes, but real-time calls (first ones Oct 28) only reach 90 days in late
  January; 7 days is mostly noise. 30-day grades start ~Nov 27 and should pass 300 calls in early December.
  `MP_RANKER_LIVE_DAYS=90` makes it stricter (waits until ~February). **Murad confirmed 30 days (2026-11-09); keep it.**

**Today's numbers (offline replay, real app #1 as the bar).** App alone: risk-matched lift +1.24%, beat 54.2%.
Mixes: gbm risk-adjusted +1.43% / 53.5%, neural net risk-adjusted +1.38% / 53.7%, gbm +1.36% / 53.5%. A bigger edge
over the other ideas, but none beats the S&P as often as the app, so nothing switches on now.

**Checks.** Backend tests: 115 passed (new: `test_ranker_mix_is_tested_as_it_goes_live_and_needs_real_time_proof`,
`test_live_check_uses_real_time_calls_only`; `test_nightly_refit_loads_graded_calls_once_and_compactly` now ignores
the small live-only load).

## 2026-11-09 (weekly) — The app's #1 on practice calls had look-ahead; new "app, no look-ahead" baseline

**Problem (real numbers).** Every gate compares learned rankers with "app (current #1)", the stored `final_rank` 0
of each practice call. On the walk-forward test (2,703 practice beliefs, 90-day checkpoint) that bar is
**+1.49% lift, t 4.54, beat 53.4%**, and no learned model alone reaches it (best: gbm +1.32%, t 3.89). But practice
calls were scored long after their date (warm-up, Oct 30 – Nov 2), and the app's score is Claude's score plus a
track-record nudge (`learning.ticker_adjustment` from `ticker_stats`), which had **no date filter**: it counted
outcomes graded *after* the call's own date, including other practice calls in the same months. Decomposed on
production data (read-only SQL, same test beliefs):

| ordering of the #1 | lift / t / beat |
|---|---|
| stored app #1 (the gate's bar) | +1.49% / 4.52 / 53.3% |
| Claude's score alone (user's direction first) | +0.06% / 0.22 / 51.8% |
| Claude + nudge from outcomes graded **before** the call's date | **+0.53% / 1.71 / 52.2%** |

So about two-thirds of the bar (~0.96 pts) is look-ahead. The #1 differs between the stored and point-in-time
orderings in 34% of test beliefs. Live users were never affected (in real time the track record only holds the
past), and the learned models never saw this score as an input (Claude's score/rank are zeroed on practice calls).
The effect: the gate has been comparing honest models with a contaminated bar, and the "+ app (25%)" mixes are
tested with the contaminated score mixed in (their offline numbers are inflated the same way; the real-time
`live_check` is unaffected).

**Change (measurement only; no gate changed).** `research.load` rebuilds, for each practice idea, the app's score
as of the call's own date (`_pit_index`, `_pit_score`: Claude's score + `learning.ticker_adjustment` from outcomes
graded strictly before the call's date, user's direction first; real-time calls keep their stored #1).
Approximation: the rebuilt nudge counts the ticker's outcomes under any theme and ignores votes. `research.run`
reports it as the baseline **"app, no look-ahead"**; `fit_production` stores it as `old_pit` and `/v4/brain`
`skill.ranker.old_pit` shows it. `_passes`, `MIN_LIFT`, `MIN_T`, `MIN_T_ADJ`, the mix live check, the embargo and the
bar the gate uses (`old`, the stored #1) are all unchanged, so nothing changes for users. Memory: one extra float
per idea plus a per-ticker index of ~23k outcomes (a few MB), built and freed inside `load`.

**Decision for Murad (not taken by the routine).** Under a look-ahead-free bar, gbm alone (+1.32%, t 3.89) would
likely clear the lift part of the gate against +0.53%, and the 25% mixes should be tested with the point-in-time app
score. Switching the gate's bar from `old` to `old_pit` would let a model reach users sooner, so it counts as
changing a safety gate and is left for you. Until then, the conservative bar stays, and mixes still need the
real-time live check (300 calls at 30 days, ~early December).

**Checks.** Backend tests: 117 passed (new: `test_app_baseline_without_look_ahead_uses_only_earlier_track_records`).

**What counts as a win.** After tonight's refit, `research:ranker` shows "app, no look-ahead" near +0.5% lift
(t ≈ 1.7) next to the stored app's +1.5%, which confirms the bar is inflated on the live job's own data. The real
win: a ranker going live through a look-ahead-free comparison, then its real-time #1 beating the app's #1 in the
live check.

## 2026-11-09 (night check) — First nightly run with mixes, shifted data and the rank-0 fix

**Run.** v4-grade-and-train 22:47 UTC finished successfully (refit 22:59, no OOM; 6,451 shifted ideas in memory).
Old network retrain: shadow, lift +0.58% (t 1.21).

**Ranker v2 (walk-forward, 2,703 real practice calls; risk-matched lift / beat a risk-matched S&P):**

| | lift | beat |
|---|---|---|
| app #1 as stored (the gate's bar; has look-ahead, see d856c72) | +1.24% | 54.3% |
| app #1 point-in-time (no look-ahead, research routine) | +0.50% | 53.0% |
| gbm / gbm risk-adj / net risk-adj, alone | +0.94% / +0.93% / +1.00% | 52.8% / 53.7% / 53.9% |
| **gbm risk-adj + shifted, 25% mix** | **+1.55%** | **54.5%** (passes `_passes`) |
| gbm risk-adj 25% mix / gbm 25% mix | +1.65% / +1.58% | 54.0% / 53.6% |

- A 25% mix (gbm risk-adjusted trained with the shifted data) now clears the unchanged gate against the stored #1.
  It is **not live**: `live_check` has 0 of the 300 real-time calls it needs at 30 days (first ones ~Nov 27).
- Shifted data on its own does not help yet (gbm risk-adj +0.70% with it vs +0.93% without); in the mix it nudges the
  beat rate up. No net "+ shifted" candidate added: no evidence yet that shifted data helps.
- Against the honest (point-in-time) app, every learned model roughly doubles the edge (+0.9–1.0% vs +0.5%).

**Proposal for Murad (not changed: a gate decision).** Judge models against the point-in-time app #1 instead of the
stored #1 that carries look-ahead. That would let a model *alone* switch on today (e.g. net risk-adjusted: +1.00% vs
+0.50%, beat 53.9% vs 53.0%). My recommendation: leave it; the 25% mix plus the real-time check already gives an
honest path and switches on in early December if the live calls agree.

**Live forward test.** 7 days, 108 real-time calls: #1 +1.12% vs its belief's other ideas (t 1.24). Confidence
labels started Nov 8; first graded ones arrive ~Nov 15.

## 2026-11-11 (weekly) — Tests choose the #1 the way the engine shows it: within the belief's own direction

**Problem (real numbers).** The engine always puts ideas in the belief's own direction first (`engine._leads`: on a
bullish belief, a short on a competitor can only follow the longs), so a ranker can only reorder *within* that group.
Ranker v2's walk-forward, its fixed rules, the 25% mixes and `live_check` instead took the argmax over *all*
directional ideas. That matters on production data (read-only SQL, 90-day checkpoint, practice calls):
**1,704 of 4,391 graded beliefs (39%) mix both directions**, and in the 714 mixed bullish beliefs the opposite-
direction (short) ideas averaged **+2.85% vs the S&P (beat 59.4%) against −0.60% (44.4%) for the longs**; in
the 990 mixed bearish ones, same-direction ideas led (+1.71% vs +0.64%). Every learned model has `same_dir` and
`bearish` as inputs, so it can learn "pick the short in a bullish belief" and collect lift for a #1 users could never
be shown. The app's stored #1 (the gate's bar) always obeys the rule, so the comparison was uneven. Tonight's
numbers before this change: gbm +1.20% (t 3.47), neural net +1.34% (t 3.82), gbm risk-adj + app 25% +1.89%
(t 5.74), vs the app's stored #1 +1.49% (t 4.52) and app without look-ahead +0.53% (t 1.71).

**Change (measurement only; the gate is untouched).** `research.load` marks each idea `lead` (belief direction not
bullish/bearish, or the idea's direction equals it). `_lead` / `_top` pick a belief's #1 as the engine would (best
score within the lead group); used by every learned candidate and mix in `run`, the fixed rules (`_choose`), the
"app, no look-ahead" baseline and `live_check`. Training is unchanged (all ideas, within-belief label). `run` now
stores `lead_only: true`, `mixed_direction` (share of test beliefs with both directions) and `off_lead` per learned
model (how often its unconstrained favourite was in the other direction: the size of the old mismatch). `_passes`,
`MIN_LIFT`, `MIN_T`, `MIN_T_ADJ`, the 90-day embargo, the mix live check and the bar (`old`) are unchanged.
Memory: one bool per idea. Not changed: `lineages` still scores strategists over all directional ideas (same issue;
needs the belief's direction in `_graded_beliefs`) — next candidate for a follow-up.

**Checks.** Backend tests: 126 passed (new: `test_research_picks_the_number_one_within_the_beliefs_own_direction`).

**What counts as a win.** After tonight's refit, `research:ranker` shows `off_lead` per model; if it is well above
zero, the learned models' lift drops by roughly that mismatch and the numbers are now what users would get. A real
win is a candidate that still clears the unchanged gate under this rule, and whose live #1 then holds up in the
real-time check. If learned models fall clearly below the app no-look-ahead baseline, that is the honest answer too.

## 2026-11-12 — The luck bar: every research run is judged against how many ways we tried (reporting only)
- **Why:** each `research:ranker` run scores 37 methods on the same test calls, and the daily routine adds one more a
  day. With that many tries, a t near 3 can be chance (Harvey, Liu & Zhu 2016; Bailey & López de Prado 2014). Murad
  asked for it to be built (proposal in docs/feature_ideas.md, 2026-11-12), also as a "receipts" point for the
  "Prove them wrong" campaign.
- **What:** `research.luck(results, tries_ever)` adds a `luck` block to `research:ranker`: `tests` (methods scored this
  run), `tries_ever` (size of the running set of every method name ever scored, kv `research:tries`, so dropped rules
  still count), `bar` / `bar_ever` (Bonferroni two-sided 5% critical t), `clear` / `clear_adj` (Holm step-down at 5%
  over `tries_ever` tests on `lift_t` / `lift_adj_t`; positive t only), `app_clears` / `app_clears_adj`.
  `/v4/brain` `skill.luck` carries it (plus `n`, `at`); the brain page scorecard shows a "luck check" line.
- **Not changed:** `_passes`, `fit_production` and ranker v2's activation rules don't read it. Tightening the gate with
  it would be a separate, deliberate decision.
- **Caveat:** Bonferroni/Holm assume roughly independent tests; many of ours are correlated momentum variants, so the
  bar errs strict. Overlapping 90-day windows likely also inflate the plain t-stats (not addressed here).
- Files: backend/v4/research.py, backend/v4/brain.py, backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx.

## 2026-11-13 (weekly) — Lineages choose their #1 within the belief's own direction (follow-up to 2026-11-11)

**Problem (real numbers).** The 2026-11-11 fix made ranker v2 pick a belief's #1 the way the engine shows it (ideas in
the belief's own direction first, `engine._leads`), but `lineages.score` still took each strategist's favourite over
*all* directional ideas. On the lineages' own window (300 most recent graded beliefs, 90-day checkpoint, read-only
SQL today): in bullish beliefs the **shorts averaged +4.11% vs the S&P (beat 58.9%, 56 ideas)** against **−1.21%
(44.4%, 728 ideas)** for the longs that weren't the app's #1. A strategist that liked those shorts scored fitness for a
#1 users can never be shown, so evolution (10 generations, all 8 alive are now Trend-riders, fitness +2.4–3.0%) was
partly selecting for "pick the other direction", and the champion gate (`pick_champion`: live record vs the app's
#1, which always obeys the rule) would compare unevenly once live 90-day calls arrive (~late January).

**Change.** `_graded_beliefs` reads the belief's direction and marks each idea `lead` (belief not bullish/bearish, or
idea direction equals it). `score` picks the strategist's #1 within the lead group (`_lead`, falls back to all ideas),
so fitness, evolution and the live record all measure what users would get. `_baseline` (app's #1), `LIVE_MIN`,
`LIVE_MARGIN`, `CHAMPION_WEIGHT`, the 90-day checkpoint and the engine path are unchanged: this only removes credit
the old scoring gave; it can't make a champion easier to earn. Memory: one bool per idea in a 300-belief window.

**Checks.** Backend tests: 137 passed (new: `test_lineages_pick_the_number_one_within_the_beliefs_own_direction`).
Commit: see git log ("Lineages: choose each strategist's #1 within the belief's own direction").

**What counts as a win.** After the next nightly evolve, alive fitness should drop by roughly the old off-direction
credit (expect a few tenths of a point) and the ranking of strategists may reshuffle. Over the following generations,
the best strategist's fitness on the window should move toward or above the app's #1 on the same calls (~+3.1% on
today's window) without the leak; in late January, a champion is only crowned on a fair live comparison.
