# Ranker research ideas log

Each idea is added as a fixed scoring rule in `backend/v4/research.run()` and tested walk-forward (90-day embargo,
calls never seen) against the current #1 pick. Nothing here goes into the live ranking directly; ranker v2
(`research.fit_production`) keeps its own out-of-sample gate.

Metrics: **lift** = #1 pick's 90-day excess return minus the belief's average idea; **beat** = share of #1 picks that
beat the S&P 500 in the belief's direction; **t** = t-stat of lift.
Since 2026-11-14 each result also has **t_nw** (`lift_t_nw`): the same lift's t with overlap-honest errors (calls on
the same or nearby dates share most of their 90-day market path; see `research._se_overlap`), plus `dates` and `n_eff`
(about how many independent calls the n is worth), and `luck.clear_nw`. Quote t_nw beside t in new results. Reporting
only: `_passes` / `fit_production` still read the plain t (changing that is Murad's call, see docs/brain_upgrades.md).
Since 2026-11-14 (late) each run also stores **coverage** (`coverage.share` / `zero_share` per feature on the test-period calls),
`provisional` ({rule: {feature: share}} for each fixed rule reading a feature under 99% filled) and `low_coverage`.
Read completeness from the kv instead of a `LIKE` scan over `picks`, quote coverage with each result, and don't record
a result as final while its rule is in `provisional`. Reporting only: gates unchanged.
Since 2026-11-17 (late) each result also has an **outlier check** (`research.winsor_cuts`): `lift_w` / `lift_w_t`
(/ `lift_w_t_nw`) = the same lift with every outcome clipped at the run's pooled test-period 1st / 99th percentile
(`winsor` {lo, hi} in the kv), `lift_med` (median per-call lift) and `top10_share` (share of the summed lift from the
10 best calls), plus `luck.clear_w`. Quote lift_w beside lift: a rule whose lift_w collapses is a few lottery tickets,
not a broad edge. Reporting only: gates unchanged.
Since 2026-11-21 each result (except the app's no-look-ahead row) also has **"is it new?"** (`research._vs_app`,
Feng, Giglio & Xiu 2020): `same_as_app` = share of test calls where the rule's #1 is the app's no-look-ahead #1;
`n_diff` = calls where they differ; `lift_diff` / `lift_diff_t` / `lift_diff_t_nw` = the rule's #1 excess minus the
app's #1 excess on those calls only. `luck.is_new` lists the 3 strongest methods with these. Quote same_as_app and
lift_diff (with n_diff; not under ~100) beside lift: high agreement with lift_diff near zero is the app restated.
Reporting only: gates unchanged.

Since 2026-11-21 (evening) each result with call dates also has **"does it hold every year?"** (`research._time_blocks`,
McLean & Pontiff 2016): the test calls split into 4 chronological stretches of about equal call count, cut on call dates
(one date never splits). `blocks` = per-stretch from/to/n/lift/beat, `pos_blocks` (of `n_blocks`) = stretches with
lift > 0, `last_block_lift`, `block_spread` = best minus worst stretch; `luck.steady` (/ `steady_nw`) = methods that
clear the bar and are ahead in 3+ of 4; `luck.app_blocks` / `app_pit_blocks` for the app as stored / without the peek.
Quote pos_blocks and last_block_lift beside lift: a rule ahead in one stretch is an episode, not an edge. Each stretch
has only ~100 dates, so one negative stretch alone is not a failure. Reporting only: gates unchanged. (On the coskew
row's n_eff = n with t_nw > t: `_se_overlap` can come out below the plain se when residuals on nearby dates lean
opposite ways; n_eff is capped at n, so that reads as n_eff = n. Not a bug.)

Since 2026-11-22 each run also stores **"would we have picked the winner?"** (`research.pbo`, probability of backtest
overfitting by CSCV, Bailey, Borwein, Lopez de Prado & Zhu 2017) in `luck.pbo`: the test calls cut on dates into 8
chronological blocks; for each of the 70 ways to call 4 blocks in-sample, the method with the best pooled lift there is
the winner and is ranked on the other 4. `pbo` = share of splits where it ranks at or below the median out of sample,
`oos_lift_med`, `p_loss` (winner's out-of-sample lift < 0), `slope` (out-of-sample on in-sample lift), `winners`,
`n_methods` (methods with calls in all 8 blocks; the look-ahead "app (current #1)" row is left out).
`luck.pbo_learned` = the same among the ranker v2 candidates and their mixes. Quote pbo with n_methods: about 0.1 or
less is reassuring, near 0.5 means the leaderboard is reshuffling noise; near-copy rules flatter it and each block is
small, so it is a rough guide. Reporting only: gates unchanged.

## Baseline (kv_cache `research:ranker`, run 2026-11-02 08:13 UTC, 3,676 beliefs, test from 2024-12-03, n=2,256)

| Method | Lift | Beat | t |
|---|---|---|---|
| app (current #1) | -0.01% | 52.2% | -0.03 |
| 1y trend (z_mom250) | +0.63% | 50.8% | 1.59 |
| high vol (z_vol60) | +1.55% | 53.7% | 3.18 |
| low vol (-z_vol60) | -1.01% | 49.0% | -4.23 |
| near highs (z_dist_high) | -1.06% | 51.1% | -2.62 |
| ridge (learned) | +1.23% | 53.1% | 2.91 |
| gbm (learned) | +1.49% | 52.9% | 3.48 |

Random pick beat rate: 51.8%. Momentum (60d), relative strength, mom+rs blend, volume-profile rules, rvol and
regime-aware styles were all within ±0.5% lift (|t| < 1.3).

## Ideas

### 1. 12-1 month momentum (Jegadeesh & Titman)
- **Added:** 2026-11-02
- **Source:** Jegadeesh & Titman (1993), "Returns to Buying Winners and Selling Losers"; practitioner summary:
  https://alphaarchitect.com/how-to-measure-momentum/ ; momentum vs short-term reversal:
  https://www.quantpedia.com/an-important-analysis-of-stock-momentum-and-reversal-factors/
- **Why:** the standard academic momentum signal ranks on the past 12 months but skips the latest month, because
  1-month returns tend to reverse. Our "1y trend" (mom250) includes that month.
- **Computed as:** `mom_12_1 = close[t-20] / close[t-250] - 1` (= (1+mom250)/(1+mom20) - 1). Stored for new picks
  via `market.features`; derived for older picks from their own stored mom250/mom20 (as of each pick's date, no
  look-ahead). Directional (flipped for bearish beliefs). Research rule: `12-1 momentum (z_mom_12_1)`; also
  available to the learned ridge/gbm.
- **Result (run 2026-11-03 10:58 UTC, 4,396 beliefs, test from 2024-12-03, n=2,707):** lift **+0.79%**, beat
  **50.1%**, t **2.21**. Better than plain 1y trend (+0.59%, t 1.67), so skipping the latest month helps the lift, but
  its beat rate is below the app's 52.3% and below random (51.6%), so on its own it would not pass the ranker v2 gate.
  Same run: app +0.02% / 52.3% / t 0.08; high vol +1.55% / 53.6% / t 3.52; ridge +1.01% / 52.4% / t 2.74;
  gbm +1.99% / 53.6% / t 5.41.

### 2. Frog in the pan: smooth 12-1 momentum (Da, Gurun & Warachka)
- **Added:** 2026-11-03
- **Source:** Da, Gurun & Warachka (2014), "Frog in the Pan: Continuous Information and Momentum", Review of
  Financial Studies 27(11); practitioner summary:
  https://alphaarchitect.com/frog-in-the-pan-identifying-the-highest-quality-momentum-stocks/
- **Why:** investors under-react to news that arrives in many small steps, so momentum built from steady small gains
  keeps going for months, while momentum built from a few big jumps tends to fade. Fits the ~90-day hold. Builds on
  idea 1, which had positive lift but a weak beat rate.
- **Computed as:** information discreteness over the same 12-1 window (closes t-250 to t-20):
  `fip_id = sign(12-1 return) * (% down days - % up days)`, from -1 (steady, continuous) to +1 (a few jumps).
  `market.fip_id` / `market.fip_features`; stored for new picks via `market.features` and `nn.make_features`;
  backfilled for older picks by `research.enrich` using closes up to each pick's own date only (the other enrich
  features are not recomputed). Not directional (low = steady in whichever direction the stock moved). Research
  rule: `smooth 12-1 momentum (frog in the pan)` = `z_mom_12_1 - z_fip_id`; `z_fip_id` is also available to the
  learned ridge/gbm.
- **Note:** until the hourly enrich finishes backfilling older picks, those picks read `fip_id = 0`, so the first
  run or two after deploy will understate the rule; trust the result once enrich reports nothing remaining.
- **Result (run 2026-11-04 18:15 UTC, 4,396 beliefs, test from 2024-12-03, n=2,707; enrich backfill complete, all
  23,279 graded picks carry fip_id):** lift **+0.62%**, beat **50.3%**, t **1.88**. Slightly worse than plain 12-1
  momentum in the same run (+0.79% / 50.1% / t 2.21), so tilting toward smooth momentum does not add anything here;
  the learned ridge gives z_fip_id a small negative weight (-0.004, i.e. it mildly prefers smooth). Not a candidate
  for the ranker v2 gate (beat below the app's 52.3% and random 51.6%). Same run: app +0.02% / 52.3% / t 0.08;
  high vol +1.55% / 53.6% / t 3.52; ridge +0.92% / 52.1% / t 2.46; gbm +2.00% / 53.3% / t 4.93.

### 3. Residual momentum (Blitz, Huij & Martens)
- **Added:** 2026-11-04
- **Source:** Blitz, Huij & Martens (2011), "Residual Momentum", Journal of Empirical Finance 18(3), 506-521:
  https://econpapers.repec.org/RePEc:eee:empfin:v:18:y:2011:i:3:p:506-521 ; working paper: https://repub.eur.nl/pub/22252
- **Why:** plain momentum partly just rides market exposure: in a rising market the high-beta stocks top the 12-1
  ranking, and they crash when the market turns. Ranking on the part of the return the market does not explain,
  scaled by its own volatility, earned about twice the risk-adjusted return of total-return momentum in the paper,
  with much smaller drawdowns. Builds on idea 1 (positive lift, weak beat rate), and is a direct test of whether our
  "high vol" winner is really just beta.
- **Computed as:** market-model version over the 12-1 window (daily returns from t-250 to t-20): fit the stock's SPY
  beta on that window, residuals `e = r - beta * r_SPY` (alpha kept in), `resid_mom = sum(e) / (std(e) * sqrt(n))`,
  clipped to ±10; 0 with under 150 matched days. (The paper uses a 3-factor model on 36 months of monthly returns;
  we only have SPY and ~a few years of daily bars, so this is the closest faithful version.) `market.resid_mom` /
  `market.resid_features`; stored for new picks via `market.features` and `nn.make_features`; backfilled for older
  picks by `research.enrich` using stock and SPY closes up to each pick's own date only. Directional. Research rule:
  `residual 12-1 momentum (z_resid_mom)`; `z_resid_mom` is also available to the learned ridge/gbm.
- **Note:** until the hourly enrich finishes backfilling (~23k picks), older picks read `resid_mom = 0`, so the first
  runs after deploy understate the rule; trust the result once every graded pick has `resid_mom`.
- **Result (preliminary, run 2026-11-05 02:34 UTC, 4,396 beliefs, test from 2024-12-03, n=2,707):** lift **+0.69%**,
  beat **52.4%**, t **2.17**. The first momentum variant whose beat rate matches the app's (52.3%) and beats random
  (51.6%), with lift close to plain 12-1 (+0.79% / 50.1% / t 2.21). Caveat: this run came ~8 hours after deploy, so
  only part of the ~23k older picks had `resid_mom` yet (the rest read 0); by 2026-11-05 all 23,279 graded picks
  carry it (and `beta`), and the research rerun triggered by the idea-4 deploy is the first fully backfilled one,
  including the new risk-matched (beta-adjusted) lift/beat. Same run: app +0.02% / 52.3% / t 0.08; high vol
  +1.55% / 53.6% / t 3.52; ridge +0.95% / 52.1% / t 2.56; gbm +1.84% / 53.1% / t 4.62. Risk-matched columns were
  not meaningful yet (beta_coverage 0.0).
- **Result (fully backfilled, run 2026-11-05 18:48 UTC, 4,396 beliefs, test from 2024-12-03, n=2,707, beta_coverage
  1.0):** lift **+0.39%**, beat **51.4%**, t **1.16**; risk-matched lift **+0.50%**, beat_adj **52.8%**, t **1.59**.
  With real values for every pick the raw edge shrinks (the preliminary number was flattered by zeros), but it is
  one of the few rules whose edge holds up once risk is matched (12-1 momentum: +0.39% adj, t 1.15; high vol: +0.15%
  adj, t 0.35). Not significant on its own; worth keeping as a learner input.

### 4. Betting against beta (Frazzini & Pedersen)
- **Added:** 2026-11-05
- **Source:** Frazzini & Pedersen (2014), "Betting Against Beta", Journal of Financial Economics 111(1), 1-25:
  https://econpapers.repec.org/RePEc:eee:jfinec:v:111:y:2014:i:1:p:1-25 ; publisher's version:
  https://research-api.cbs.dk/ws/portalfiles/portal/60082899/lasse_heje_pedersen_et_al_betting_against_beta_publishersversion.pdf ;
  critique (BAB partly overlaps low volatility and depends on how beta is built): Novy-Marx & Velikov,
  https://mysimon.rochester.edu/novy-marx/research/BABAB.pdf
- **Why:** many investors can't or won't use leverage, so they reach for high-beta stocks to get more return; that
  bids high-beta stocks up and leaves them with lower risk-adjusted returns (a flatter security market line than
  CAPM predicts). Low-beta longs and high-beta shorts earn positive alpha across US and international stocks. This
  differs from the "low vol" rule already tried (total volatility, which lost) because beta is only the market part of
  risk. With the new risk-matched scoring (`beat_adj` / `lift_adj`, vs an S&P scaled to each stock's beta) we can
  finally test the claim the way the paper states it: does the low-beta side win once risk is matched?
- **Computed as:** the pick's stored `beta` (`market.beta_value`: OLS beta of daily returns vs SPY over the last 252
  sessions up to the pick's own date, clipped to [-1, 4], 1.0 with under 120 matched days), already stored for new
  picks and backfilled for all 23,279 graded picks by `research.enrich`. The paper uses a shrunk beta
  (0.6 * time-series beta + 0.4); shrinking toward 1 is linear, so the within-belief z-score and the ranking are the
  same. Added to `research.FEATS` and `DIRECTIONAL` (bearish calls flip it, so the rule picks the high-beta stock to
  short); a pick without a stored beta reads 1.0 (market-like). Research rule: `betting against beta (-z_beta)`;
  `z_beta` is also available to the learned ridge/gbm.
- **What to look at:** raw lift will likely be negative (high vol, and probably high beta, wins raw lift in this
  sample's rising market). The test is `lift_adj` / `beat_adj` and whether "high vol"'s edge survives risk matching.
- **Result (run 2026-11-05 18:48 UTC, 4,396 beliefs, test from 2024-12-03, n=2,707, beta_coverage 1.0):** raw lift
  **-1.61%**, beat **50.5%**, t **-4.66**; risk-matched lift **+0.02%**, beat_adj **54.0%**, t **0.06**. As expected,
  it loses badly on raw returns in this rising-market sample. Against a beta-matched S&P its #1 picks beat the
  benchmark most often of any rule (54.0% vs app 52.7%), but its lift over the belief's average idea is zero, so
  there's no alpha from choosing low beta within a belief: no BAB edge here. The bigger finding is the mirror image:
  "high vol"'s +1.55% raw lift (t 3.52) falls to +0.15% (t 0.35) once risk is matched, so most of that winner was
  market beta, not skill. The learned ridge gives z_beta a small positive weight (+0.005, mildly prefers higher beta
  in the call's direction). Not a ranker v2 candidate. Same run: app +0.02% / 52.3% / t 0.08 (adj +0.35% / 52.7% /
  t 1.28); ridge +1.32% / 52.4% / t 3.31 (adj -0.10%, t -0.26); gbm +2.01% / 53.3% / t 4.91 (adj +0.47%, t 1.19);
  gbm (risk-adjusted) +0.33% / 52.1% / t 0.96 (adj +0.36% / 53.1% / t 1.13); random beat 51.6%.

### Re-run after "volatile ideas left out" (run 2026-11-06 16:15 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703)
Since commit e0f186d, 'volatile' calls (graded on |move|) are excluded from research and ranker v2, so every number
moved a little. Raw lift / beat / t, then risk-matched lift / beat_adj / t:

| Method | Lift | Beat | t | Lift adj | Beat adj | t adj |
|---|---|---|---|---|---|---|
| app (current #1) | +0.39% | 52.3% | 1.41 | +0.33% | 52.9% | 1.24 |
| 12-1 momentum (idea 1) | +0.69% | 49.5% | 1.97 | +0.43% | 51.3% | 1.29 |
| frog in the pan (idea 2) | +0.81% | 49.7% | 2.49 | +0.69% | 52.1% | 2.24 |
| residual momentum (idea 3) | +0.49% | 50.9% | 1.49 | +0.57% | 53.2% | 1.81 |
| betting against beta (idea 4) | -1.27% | 50.4% | -3.75 | +0.04% | 54.0% | 0.12 |
| high vol (z_vol60) | +0.87% | 51.9% | 2.04 | +0.49% | 52.7% | 1.19 |
| ridge (learned) | +0.81% | 51.1% | 2.37 | +0.27% | 51.9% | 0.82 |
| gbm (learned) | +1.41% | 51.9% | 4.16 | +0.96% | 52.8% | 2.94 |
| gbm (risk-adjusted) | +0.72% | 51.4% | 2.17 | +0.76% | 53.5% | 2.39 |

Random beat 51.0%. Frog in the pan now has the best risk-matched lift of the fixed rules (t 2.24), a change from its
earlier middling result; its raw beat rate is still below the app's. Residual momentum's beat_adj (53.2%) is above
the app's (52.9%).

### 5. MAX effect: avoid lottery stocks (Bali, Cakici & Whitelaw)
- **Added:** 2026-11-06
- **Source:** Bali, Cakici & Whitelaw (2011), "Maxing Out: Stocks as Lotteries and the Cross-Section of Expected
  Returns", Journal of Financial Economics 99(2), 427-446:
  https://econpapers.repec.org/RePEc:eee:jfinec:v:99:y:2011:i:2:p:427-446 ; NBER working paper:
  https://econpapers.repec.org/RePEc:nbr:nberwo:14804 ; practitioner summary:
  https://alphaarchitect.com/hot-off-the-jfe-press-maxing-out-your-returns/
- **Why:** investors overpay for stocks with lottery-like payoffs (a few huge up-days recently), so those stocks earn
  lower returns afterwards; in the paper, the high-MAX decile lagged the low-MAX decile by over 1% a month, and MAX
  also explains the "idiosyncratic volatility puzzle". It's a sharper question than "high vol vs low vol" (already
  tried, high vol won raw but mostly on beta): is it the *upside spikes* that hurt? Caveat: the paper's holding period
  is one month; our test is 90 days, so the effect may be diluted.
- **Computed as:** `max5` = average of the 5 largest daily returns over the last 21 sessions up to the pick's own
  date (the MAX5 variant from Bali, Brown, Murray & Tang 2017, more robust than the single biggest day), clipped to
  [-0.5, 1]; 0 with under a month of history. `market.max5` / `market.max_features`; stored for new picks via
  `market.features` and `nn.make_features` (not MODEL_NUMERIC); backfilled for older picks by `research.enrich`
  using closes up to each pick's own date only (other features untouched). Directional (bearish calls flip it, so
  the rule shorts the lottery stock). Research rule: `avoid lottery stocks (-z_max5)`; `z_max5` is also available to
  the learned ridge/gbm.
- **Note:** until enrich finishes backfilling older picks they read `max5 = 0` (looks like "no lottery"), so the first
  runs after deploy understate or distort the rule; trust the result once every graded pick has `max5`.
- **Result (run 2026-11-09 17:05 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; all 23,279 graded picks carry
  max5):** raw lift **-0.87%**, beat **49.4%**, t **-2.40**; risk-matched lift **-0.32%**, beat_adj **50.8%**,
  t **-0.95**. No MAX effect at our 90-day horizon: avoiding lottery stocks hurts raw returns and is flat once risk is
  matched, and the learned ridge gives z_max5 a small positive weight (+0.004, mildly prefers the spiky stock in the
  call's direction). Consistent with high vol winning raw. Not a ranker v2 candidate.
  Same run (first one scoring the real 0-based app #1, see handoff 2026-11-08): app **+1.49% / 53.4% / t 4.54**
  (adj +1.24% / 54.3% / t 3.89), now ahead of every fixed rule; frog in the pan +0.80% / 49.7% / t 2.47 (adj +0.69%,
  t 2.22); residual momentum +0.49% / 50.9% / t 1.49 (adj +0.57% / 53.2% / t 1.81); BAB -1.28% / 50.4% (adj +0.03% /
  54.0%); high vol +0.87% / 51.9% / t 2.04 (adj +0.49%, t 1.19); gbm +1.32% / 51.8% / t 3.89; gbm + app (25%)
  +1.87% / 53.2% / t 5.75 (adj +1.47%, t 4.67); random beat 51.0%.

### 6. Intermediate-horizon momentum, the "echo" (Novy-Marx)
- **Added:** 2026-11-09
- **Source:** Novy-Marx (2012), "Is Momentum Really Momentum?", Journal of Financial Economics 103(3), 429-453:
  https://econpapers.repec.org/RePEc:eee:jfinec:v:103:y:2012:i:3:p:429-453 ; practitioner debate:
  https://alphaarchitect.com/when-academics-disagree-on-momentum-investing/ ; critique (the echo is weaker outside
  the US and partly a 12-month seasonality): Goyal & Wahal (2015), "Is Momentum an Echo?", JFQA 50(6):
  https://econpapers.repec.org/RePEc:cup:jfinqa:v:50:y:2015:i:06:p:1237-1267_00
- **Why:** Novy-Marx found that momentum's profits come mainly from returns 12 to 7 months back, not from the most
  recent six months, so "stocks that went up a while ago" beat "stocks that went up recently". Our 12-1 rule mixes
  both legs; this isolates the older one. Slow signal, suits the ~90-day hold.
- **Computed as:** `mom_12_7 = close[t-125] / close[t-250] - 1` (trading days; 0 without a year of history).
  `market.mom_12_7` / `market.echo_features`; stored for new picks via `market.features` and `nn.make_features`
  (not MODEL_NUMERIC); backfilled for older picks by `research.enrich` using closes up to each pick's own date only
  (other features untouched). Directional. Research rule: `intermediate momentum (z_mom_12_7)`; `z_mom_12_7` is also
  available to the learned ridge/gbm/net.
- **Note:** until enrich finishes backfilling older picks they read `mom_12_7 = 0`; trust the result once every
  graded pick has `mom_12_7`.
- **Result (run 2026-11-10 14:45 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; all 23,279 graded picks carry
  mom_12_7):** lift **+0.77%**, beat **50.0%**, t **2.20**; risk-matched lift **+0.38%**, beat_adj **51.9%**,
  t **1.12**. About the same as plain 12-1 momentum in the same run (+0.69% / 49.5% / t 1.97; adj +0.43%, t 1.29), so
  the older 12-7 leg alone is not better than the full 12-1 window here: no echo effect beyond ordinary momentum.
  Beat rate is below random (51.0%) and well below the app's; the learned ridge gives z_mom_12_7 almost no weight
  (+0.0007). Not a ranker v2 candidate. Same run: app +1.49% / 53.4% / t 4.54 (adj +1.24% / 54.2% / t 3.87);
  app, no look-ahead +0.53% / 52.2% / t 1.71; frog in the pan +0.78% / 49.6% / t 2.38 (adj +0.66%, t 2.13);
  gbm +1.16% / 52.1% / t 3.38; gbm (+ shifted) + app (25%) +1.87% / 53.0% / t 5.82 (adj +1.47%, t 4.74);
  random beat 51.0%.

### 7. Moving average distance (Avramov, Kaplanski & Subrahmanyam)
- **Added:** 2026-11-10
- **Source:** Avramov, Kaplanski & Subrahmanyam (2021), "Moving Average Distance as a Predictor of Equity Returns",
  Review of Financial Economics 39(2), 127-145: https://ideas.repec.org/a/wly/revfec/v39y2021i2p127-145.html ;
  working paper: https://anderson-review.ucla.edu/wp-content/uploads/2021/03/Avramov-Kaplanski-Subra_2018_SSRN-id3111334.pdf ;
  practitioner summaries: https://alphaarchitect.com/moving-average-distance/ ,
  https://www.cxoadvisory.com/technical-trading/distance-between-fast-and-slow-price-smas-and-stock-returns
- **Why:** investors anchor on a stock's long-run average price and under-react when the recent price drifts far
  from it, so stocks whose 21-day average is well above their 200-day average keep outperforming for months, and
  those far below keep lagging. The paper reports the MAD long-short spread survives controls for 12-1 momentum and
  the 52-week high (both tried here), and is stronger in hard-to-value stocks. It is a trend-strength signal rather
  than a point-to-point return, which is a different shape from ideas 1-3 and 6; monthly rebalancing in the paper
  fits our ~90-day hold better than daily technical rules.
- **Computed as:** `mad = mean(close[t-20..t]) / mean(close[t-199..t]) - 1`, clipped to [-0.9, 3]; 0 with under 200
  days of history. (The paper uses the ratio MA21/MA200; subtracting 1 doesn't change the within-belief z-score.)
  `market.mad` / `market.mad_features`; stored for new picks via `market.features` and `nn.make_features` (not
  MODEL_NUMERIC); backfilled for older picks by `research.enrich` using closes up to each pick's own date only
  (other features untouched). Directional (bearish calls flip it, so the rule shorts the stock furthest below its
  200-day average). Research rule: `moving average distance (z_mad)`; `z_mad` is also available to the learned
  ridge/gbm/net.
- **Note:** until enrich finishes backfilling older picks (~23k, 300 per hourly run, so about 3-4 days) they read
  `mad = 0`; trust the result once every graded pick has `mad`.
- **Result (run 2026-11-10 22:56 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; checked 2026-11-11: no graded
  pick is missing `mad`):** lift **-0.73%**, beat **51.1%**, t **-2.41**; risk-matched lift **-0.67%**, beat_adj
  **50.9%**, t **-2.33**. The opposite of the paper: within a belief, picking the stock furthest above its 200-day
  average (furthest below, for shorts) did *worse* than the belief's average idea, raw and risk-matched. Close to
  "near highs (z_dist_high)" in the same run (-0.61%, t -1.67), so on our 90-day horizon stretched trends tended to
  give some back rather than keep going. The learned ridge gives z_mad a small negative weight (-0.0023), consistent.
  Not a ranker v2 candidate (and the reverse, -z_mad, is not tested out of sample; noted only). If backfill finished
  only shortly before that run, the post-deploy re-run of 2026-11-11 is the clean read. Same run: app +1.49% / 53.4% /
  t 4.54 (adj +1.24%, t 3.87); app, no look-ahead +0.53% / 52.2% / t 1.71; 12-1 momentum +0.69% / 49.5% / t 1.97;
  frog in the pan +0.81% / 49.7% / t 2.50 (adj +0.69%, t 2.24); gbm +1.19% / 52.4% / t 3.51;
  gbm (risk-adjusted) + app (25%) +1.89% / 52.9% / t 5.75 (adj +1.65%, t 5.20); random beat 51.0%.

### 8. Illiquidity premium (Amihud)
- **Added:** 2026-11-11
- **Source:** Amihud (2002), "Illiquidity and Stock Returns: Cross-Section and Time-Series Effects", Journal of
  Financial Markets 5(1), 31-56: https://www.cis.upenn.edu/~mkearns/finread/amihud.pdf ; follow-up with newer data:
  Amihud & Noh (2021), "Illiquidity and Stock Returns II: Cross-section and Time-series Effects", Review of Financial
  Studies 34(4), 2101-2123: https://econpapers.repec.org/RePEc:oup:rfinst:v:34:y:2021:i:4:p:2101-2123.
- **Why:** investors want to be paid for holding stocks that are costly to trade, so stocks whose price moves a lot
  per dollar traded (illiquid) have earned higher later returns. A slow, annual signal that fits the ~90-day hold,
  and a different family from the momentum/trend ideas 1-3, 6 and 7 and the risk ideas 4-5. Our candidates are
  mostly liquid large caps, so the spread within a belief is smaller than in the paper's full cross-section; this
  tests whether it still helps choose among them.
- **Computed as:** `amihud = log(1 + 1e8 * mean(|r_d| / (close_d * volume_d)))` over the last 252 sessions up to the
  pick's date (needs 120+ days with volume, else 0), clipped to [0, 15]. Uses our feed's volume (IEX by default, a
  slice of total volume; fine for ranking stocks against each other, not an absolute dollar figure).
  `market.amihud` / `market.amihud_features`; stored for new picks via `market.features` and `nn.make_features` (not
  MODEL_NUMERIC); backfilled for older picks by `research.enrich` using closes and volumes up to each pick's own date
  only (other features untouched). Directional (bearish calls flip it, so the rule shorts the most liquid stock,
  the side the premium says should lag). Research rule: `illiquidity premium (z_amihud)`; `z_amihud` is also
  available to the learned ridge/gbm/net.
- **Note:** until enrich finishes backfilling older picks they read `amihud = 0` (same as "most liquid"); trust the
  result once every graded pick has `amihud`.
- **Result (run 2026-11-12 10:03 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; checked 2026-11-12: no graded
  pick is missing `amihud`; first run with the "#1 within the belief's own direction" rule, `lead_only`, so every
  fixed rule moved vs earlier runs):** lift **+1.20%**, beat **52.7%**, t **3.98**; risk-matched lift **+1.00%**,
  beat_adj **54.2%**, t **3.44**. The strongest fixed rule logged so far and the first whose risk-matched edge holds
  up at t > 3: close to the app's own #1 in the same run (+1.49% / 53.4% / t 4.54; adj +1.24% / 54.2% / t 3.87) and
  ahead of ridge (+0.96% / 51.7% / t 2.94; adj +0.63%, t 1.97). Raw beat rate is still below the app's, so on its own
  it would not pass the ranker v2 gate; the learned ridge gives z_amihud almost no weight (+0.0001), so the learners
  are not yet using it. Caveat: 37 methods are scored each run, so a t near 3 is the bar for "not luck" (Bonferroni
  5% two-sided ≈ 3.20); this one clears it, raw and risk-matched. Same run: 12-1 momentum +0.66% / 50.5% / t 1.94; frog in the pan +0.91% /
  50.9% / t 2.89 (adj +0.78%, t 2.58); intermediate momentum +1.03% / 51.7% / t 3.02 (adj +0.65%, t 1.97); MAD
  +0.12% / 49.5% / t 0.36; gbm +1.20% / 52.1% / t 3.68; gbm (risk-adjusted) + app (25%) +1.92% / 53.5% / t 5.98
  (adj +1.74% / 54.8% / t 5.59); random beat 51.0%.

### 9. Continuing overreaction: volume-confirmed trend (Byun, Lim & Yun)
- **Added:** 2026-11-12
- **Source:** Byun, Lim & Yun (2016), "Continuing Overreaction and Stock Return Predictability", Journal of Financial
  and Quantitative Analysis 51(6), 2015-2046: https://ideas.repec.org/a/cup/jfinqa/v51y2016i06p2015-2046_00.html ;
  publisher: https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/continuing-overreaction-and-stock-return-predictability/A97DDAC507CBDBAEBD4CCB50A84D3577
- **Why:** overconfident investors with biased self-attribution keep overreacting in the same direction, and trading
  volume shows how strongly. The paper's CO measure (a weighted average of *signed volume*) buys stocks with upward
  continuing overreaction and sells downward, and predicts returns better than past returns alone; the effect is
  stronger where such investors hold the stock. A volume-price confirmation signal over a 12-month window, monthly
  rebalanced, which fits our ~90-day hold, and a different shape from the return-only momentum ideas 1-3 and 6 (here
  a quiet up month counts for little, a heavy-volume up month for a lot).
- **Computed as:** split the last 252 sessions (up to the pick's own date) into 12 blocks of 21 sessions; block j
  (1 = latest) contributes `w_j * sign(block return) * block volume` with `w_j = 13 - j`;
  `co = sum / (mean block volume * sum of weights)`, from -1 (heavy volume on down months) to +1 (on up months);
  0 without a year of priced volume. (The paper uses monthly turnover; dividing by the stock's own mean volume plays
  the same role, and the extra constant doesn't change the within-belief z-score.) Volume is our feed's (IEX by
  default), fine for comparing a stock's months with each other. `market.co` / `market.co_features`; stored for new
  picks via `market.features` and `nn.make_features` (not MODEL_NUMERIC); backfilled for older picks by
  `research.enrich` using closes and volumes up to each pick's own date only (other features untouched). Directional
  (bearish calls flip it, so the rule shorts the stock with heavy-volume down months). Research rule:
  `continuing overreaction (z_co)`; `z_co` is also available to the learned ridge/gbm/net.
- **Note:** until enrich finishes backfilling older picks they read `co = 0`; trust the result once every graded pick
  has `co`.
- **Result (run 2026-11-13 18:02 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; checked 2026-11-13: no graded
  pick is missing `co`):** lift **+0.09%**, beat **50.6%**, t **0.32**; risk-matched lift **+0.29%**, beat_adj
  **52.7%**, t **1.05**. No edge: weighting past moves by their volume adds nothing over plain 12-1 momentum in the
  same run (+0.66% / 50.5% / t 1.94; adj +0.45%, t 1.37), and the learned ridge gives z_co a small negative weight
  (-0.0027). Does not clear the luck bar (|t| ≥ 3.21 for 38 tries; `luck.clear` lists only the app's #1, the Amihud
  rule, the plain neural net and the "+ app (25%)" mixes). Not a ranker v2 candidate. Same run: app +1.49% / 53.4% /
  t 4.54 (adj +1.24% / 54.2% / t 3.87); illiquidity premium +1.21% / 53.1% / t 4.04 (adj +1.00% / 54.5% / t 3.44,
  clears the bar both ways); neural net (learned) +1.25% / 52.1% / t 3.82; MAD now +0.12% / 49.5% / t 0.36 (was
  -0.73%, t -2.41 before the `lead_only` change); gbm (risk-adjusted, + shifted) + app (25%) +1.70% / 53.4% / t 5.40
  (adj +1.53% / 54.9% / t 5.00); random beat 51.0%.

### 10. Return seasonality: the same season in past years (Heston & Sadka)
- **Added:** 2026-11-13
- **Source:** Heston & Sadka (2008), "Seasonality in the Cross-Section of Stock Returns", Journal of Financial
  Economics 87(2), 418-445: https://econpapers.repec.org/RePEc:eee:jfinec:v:87:y:2008:i:2:p:418-445 ; follow-up
  across asset classes and factors: Keloharju, Linnainmaa & Nyberg (2016), "Return Seasonalities", Journal of
  Finance 71(4), 1557-1590: https://econpapers.repec.org/RePEc:bla:jfinan:v:71:y:2016:i:4:p:1557-1590 ; practitioner
  summary: https://hedgefundalpha.com/strategies/return-seasonalities-a-stock-selection-strategy/
- **Why:** a stock's return in a given calendar month predicts its return in the same month of later years (the
  effect shows up at annual lags for up to ~20 years and is not explained by size, industry, earnings timing or
  dividends); Keloharju et al. find the same pattern in industries, countries and factors and argue it comes from
  seasonal swings in risk premia. A new family for the log: not momentum (ideas 1-3, 6, 7, 9), risk (4, 5) or
  liquidity (8), and it uses only the calendar, which nothing in FEATS captures.
- **Computed as:** for each of up to 4 past years y, the stock's return over the 63 sessions (~3 months, our hold)
  starting on the last session on or before (pick date - 365*y days); `seas` = the average of those returns,
  clipped to [-0.9, 3]; a year is skipped if the data has a >7-day gap at its start or doesn't reach that far; 0
  without any past-year window. Every window ends at least ~9 months before the pick's date, so no look-ahead. The
  papers use the same single calendar month over many years of monthly data; with 5 years of daily bars and a
  90-day hold, the same ~3-month season over up to 4 years is the closest faithful version (older picks from
  2023-24 have only 1-2 past years, so the signal is noisier for them). `market.seas` / `market.seas_features`;
  stored for new picks via `market.features` and `nn.make_features` (not MODEL_NUMERIC); backfilled for older picks
  by `research.enrich` using closes up to each pick's own date only (other features untouched). Directional (bearish
  calls flip it, so the rule shorts the stock with the worst past seasons). Research rule:
  `same season, past years (z_seas)`; `z_seas` is also available to the learned ridge/gbm/net.
- **What to look at:** raw and risk-matched lift, and whether it clears the luck bar (`luck.clear` / `clear_adj`,
  now 39 tries). Expect a weak effect: the papers' edge is monthly and small, and ours is averaged over 3 months.
- **Note:** until enrich finishes backfilling older picks they read `seas = 0`; trust the result once every graded
  pick has `seas`.
- **Result (preliminary, run 2026-11-14 06:47 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; checked 2026-11-14:
  5,279 graded picks still missing `seas`, so not final):** lift **+0.89%**, beat **52.7%**, t **2.73**; risk-matched
  lift **+0.54%**, beat_adj **53.9%**, t **1.73**. Promising raw, weaker risk-matched; does not clear the luck bar
  (|t| ≥ 3.22 for 39 tries; `luck.clear` lists only the app's #1, the Amihud rule, the plain neural net and the
  "+ app (25%)" mixes). Learned ridge weight on z_seas +0.0035. Re-check once enrich reports nothing remaining.
  Update (run 2026-11-14 17:19 UTC, 3,779 graded picks still missing `seas`): lift +0.62% / beat 52.2% / t 1.86
  (t_nw 0.94); risk-matched +0.26% / 53.5% / t 0.81 (t_nw 0.44). Fading as the backfill fills in. Same
  run: app +1.49% / 53.4% / t 4.54 (adj +1.24% / t 3.89); illiquidity premium +1.21% / 53.1% / t 4.04 (adj +1.00% /
  t 3.44); random beat 51.0%.
- **Result (final, run 2026-11-15 17:16 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; coverage `seas` 100%, not in
  `provisional`):** lift **+0.79%**, beat **52.3%**, t **2.29** (t_nw **1.32**); risk-matched lift **+0.45%**, beat_adj
  **53.8%**, t **1.36** (t_nw **0.81**). n_eff 902. Mildly positive raw, mostly gone risk-matched and on honest errors;
  under the luck bar (3.24 for 42 tries). Not a usable rule here. Ridge weight on z_seas +0.0028.

### 11. Downside risk premium: relative downside beta (Ang, Chen & Xing)
- **Added:** 2026-11-14
- **Source:** Ang, Chen & Xing (2006), "Downside Risk", Review of Financial Studies 19(4), 1191-1239:
  https://econpapers.repec.org/RePEc:oup:rfinst:v:19:y:2006:i:4:p:1191-1239 ; working paper (NBER w11824):
  https://econpapers.repec.org/RePEc:nbr:nberwo:11824
- **Why:** investors care more about losses than gains, so a stock that falls hardest exactly when the market falls
  is worth less to them and must offer a higher return. The paper finds stocks with high downside beta (beta
  measured only on days the market is below its average) earned about 6% a year more, and that *relative* downside
  beta (downside beta minus plain beta) carries the premium on its own, so it isn't just the beta trade (idea 4,
  which lost raw and was flat risk-matched). A new family for the log: asymmetric risk, from daily returns over a
  12-month window, which suits our ~90-day hold.
- **Computed as:** daily returns of the stock and SPY over the last 252 sessions up to the pick's own date; beta on
  all days, and beta on the days SPY's return was below its window average; `dbeta` = downside beta minus beta,
  clipped to [-3, 3]; 0 without 120 matched days including 50 below-average market days. `market.dbeta` /
  `market.dbeta_features`; stored for new picks via `market.features` and `nn.make_features` (not MODEL_NUMERIC);
  backfilled for older picks by `research.enrich` using closes up to each pick's own date only (other features
  untouched). Directional (bearish calls flip it, so the rule shorts the stock least exposed to market drops, the
  weak side of the premium, as with the Amihud rule). Research rule: `downside beta premium (z_dbeta)`; `z_dbeta` is
  also available to the learned ridge/gbm/net.
- **What to look at:** raw and risk-matched lift (the risk-matched benchmark uses plain beta, so `dbeta` is
  deliberately the part plain beta misses), and whether it clears the luck bar (now 40 tries). Later work finds the
  premium weaker in recent decades, so expect a small effect.
- **Note:** until enrich finishes backfilling older picks they read `dbeta = 0`; trust the result once every graded
  pick has `dbeta`.
- **Result (preliminary, run 2026-11-14 17:19 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; checked 2026-11-14
  evening: 6,779 of 23,279 graded picks still missing `dbeta`, so not final):** lift **+0.71%**, beat **52.9%**, t
  **2.18** (t_nw **2.05**); risk-matched lift **+0.76%**, beat_adj **54.0%**, t **2.44** (t_nw **2.21**). Positive and
  steadier than most (n_eff 2,371 of 2,703: little overlap), but under the luck bar (3.23 for 41 tries). Learned ridge
  weight on z_dbeta +0.0020. Re-check once filled.
- **Result (final, run 2026-11-15 17:16 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; coverage `dbeta` 100%, not in
  `provisional`):** lift **+0.57%**, beat **52.4%**, t **1.74** (t_nw **2.09**); risk-matched lift **+0.70%**, beat_adj
  **53.2%**, t **2.22** (t_nw **2.38**). n_eff 2,703 (picks barely overlap, so t_nw is not below t). One of the steadier
  small positives in the log, and stronger risk-matched than raw, as the paper would predict (plain beta is already
  in the benchmark); still under the luck bar (3.24 for 42 tries), so not a rule on its own. Ridge weight on z_dbeta
  +0.0040.

### 12. Short-term reversal: last month's losers (Jegadeesh 1990; Lehmann 1990)
- **Added:** 2026-11-14 (extra run)
- **Source:** Jegadeesh (1990), "Evidence of Predictable Behavior of Security Returns", Journal of Finance 45(3),
  881-898: https://econpapers.repec.org/RePEc:bla:jfinan:v:45:y:1990:i:3:p:881-98 ; practitioner summary:
  https://alphaarchitect.com/quantitative-momentum-research-short-term-return-reversal/
- **Why:** a stock's return over the past month tends to reverse the next month (liquidity provision and
  overreaction to short-term news), the reason the 12-1 momentum rules (ideas 1-3) skip the latest month. We have
  never tested it on its own: `mom20` is stored for every pick but only appears with a *positive* sign in the
  "mom+rs blend". A cheap, clean check of whether the latest month should count against an idea.
- **Computed as:** the stored 20-session return `mom20` (as of the pick's date, already on every graded pick, so no
  backfill and no new feature). Directional (bearish calls flip it, so the rule shorts last month's biggest
  winner). Research rule: `short-term reversal (-z_mom20)`.
- **What to look at:** raw and risk-matched lift and the luck bar (now 41 tries). The effect is about one month and
  our hold is ~90 days, so expect it to be weak; a negative result would say the latest month should not be held
  against an idea in our setting.
- **Result (final, run 2026-11-14 17:19 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; `mom20` on every graded
  pick):** lift **+0.60%**, beat **51.0%**, t **1.96** (t_nw **1.32**); risk-matched lift **+0.66%**, beat_adj
  **52.8%**, t **2.27** (t_nw **1.99**). Mildly positive: last month's loser was a slightly better #1 than its
  belief's average idea, so the latest month shouldn't count *for* an idea, but it doesn't clear the luck bar (3.23
  for 41 tries) and isn't a usable rule on its own. Ridge weight on z_mom20 +0.0001 (≈ none). Same run: app +1.49% /
  t 4.52 (t_nw 1.91); illiquidity premium +1.21% / t 4.04 (t_nw 2.63); `luck.clear` = app + illiquidity,
  `clear_nw` = none; random beat 51.0%.

### 13. Idiosyncratic volatility puzzle: the calmest stock beyond the market (Ang, Hodrick, Xing & Zhang)
- **Added:** 2026-11-14 (evening run)
- **Source:** Ang, Hodrick, Xing & Zhang (2006), "The Cross-Section of Volatility and Expected Returns", Journal of
  Finance 61(1), 259-299: https://business.columbia.edu/faculty/research/cross-section-volatility-and-expected-returns
  (working paper: https://users.nber.org/~confer/2003/apf03/ang.pdf); international and further U.S. evidence, same
  authors (2009), Journal of Financial Economics 91(1), 1-23:
  https://econpapers.repec.org/RePEc:eee:jfinec:v:91:y:2009:i:1:p:1-23
- **Why:** stocks whose daily returns swung the most over the past month *beyond what the market explains* went on
  to earn strikingly low returns (about 1% a month less for the top fifth in the paper), the "IVOL puzzle"; it holds
  across 23 developed markets. Different from what we've tried: the vol rules (high/low vol) use total volatility,
  beta (idea 4) and downside beta (11) use the market part, and MAX (5) uses the 5 biggest days. IVOL is the
  stock-specific part. Our own "high vol" rule was positive, so this is a real test of which side wins here.
- **Computed as:** daily returns of the stock and SPY over the last 21 sessions (~1 month, as in the paper) up to
  the pick's own date; market model fitted on that window; `ivol` = std of residuals x sqrt(252), clipped to [0, 3];
  0.30 (neutral, also `research.NEUTRAL`) without 15 matched days. The paper uses Fama-French 3-factor residuals; we
  only have SPY, so this is the market-model (CAPM) version (a common simplification; IVOL against different factor
  models is highly correlated, but this is a choice, not the paper's exact measure).
  `market.ivol` / `market.ivol_features`; stored for new picks via `market.features` and `nn.make_features` (not
  MODEL_NUMERIC); backfilled for older picks by `research.enrich` using closes up to each pick's own date only (other
  features untouched). Directional (bearish calls flip it, so the rule shorts the wildest stock). Research rule:
  `low idiosyncratic vol (-z_ivol)`; `z_ivol` is also available to the learned ridge/gbm/net.
- **What to look at:** raw and risk-matched lift, t and t_nw, and the luck bar (now 42 tries). Later work (Bali &
  Cakici 2008; Fu 2009) finds the effect sensitive to weighting and breakpoints and partly tied to last month's
  reversal (idea 12), and it is strongest among small, hard-to-short stocks, so expect it to be small on our mostly
  large-cap ideas. Overlap with high/low vol is large, so compare it against those rows, not just against zero.
- **Note:** until enrich finishes backfilling older picks they read the neutral 0.30; trust the result once every
  graded pick has `ivol` (`p.features LIKE '%"ivol"%'`).
- **Result (final, run 2026-11-15 17:16 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; coverage `ivol` 100%, zero share 0.2%,
  not in `provisional`):** lift **-1.28%**, beat **46.2%**, t **-4.00** (t_nw **-1.58**); risk-matched lift **-0.64%**,
  beat_adj **49.0%**, t **-2.09** (t_nw **-0.98**). n_eff 421. The puzzle runs the *other* way here: picking the calmest
  stock was clearly worse than the belief's average idea (raw t past the luck bar, but on overlap-honest errors it is
  -1.58), the same side as our "high vol" / "low vol" rows. About half the gap goes away risk-matched, so much of it is
  that wild stocks rose more in this market, not stock-specific skill. Read as: don't hold idiosyncratic volatility
  against an idea in our setting; it is not a reason to prefer wild stocks either. Ridge weight on z_ivol -0.0017.
  Same run: app +1.49% / 53.4% / t 4.52 (t_nw 1.91); illiquidity premium +1.21% / t 4.04 (t_nw 2.63); `luck.clear` =
  app, neural net, gbm, illiquidity, ridge, gbm (+ shifted); `clear_nw` = gbm (+ shifted) only; random beat 51.0%.

### 14. Long-term reversal: losers of the past three years, skipping the latest (De Bondt & Thaler)
- **Added:** 2026-11-15
- **Source:** De Bondt & Thaler (1985), "Does the Stock Market Overreact?", Journal of Finance 40(3), 793-805:
  https://econpapers.repec.org/RePEc:bla:jfinan:v:40:y:1985:i:3:p:793-805 ; practitioner summary:
  https://alphaarchitect.com/quantitative-momentum-research-long-term-return-reversal/ ; Fama & French (1996) show the
  long-term reversal (months -60 to -13) is one of the anomalies their 3-factor model captures through value, so it
  is a well-known, durable pattern, not a fresh claim.
- **Why:** portfolios of the biggest losers over the past three to five years beat the biggest winners over the
  next three to five years (about 25% cumulative in the paper over 36 months), read as investors overreacting to
  long runs of bad or good news. It is the long-horizon opposite of momentum: our momentum rules (1-3, 6, 7, 9) all
  look at the last year or less, and the short-term reversal (12) at the last month. Nothing in FEATS sees prices
  more than a year back except seasonality (10), which looks at the same season, not the whole run. Also a rough,
  price-only stand-in for "value" (long-term losers tend to be cheap), which we cannot test directly without
  fundamentals.
- **Computed as:** `ltr` = close one year (252 sessions) before the pick's date over the close up to three years (756
  sessions) before it, minus 1, clipped to [-0.95, 10]. The latest year is skipped, as in Fama-French's -60 to -13
  version, so 12-month momentum is not mixed in. We hold 5 years of daily bars, so picks from late 2024 have only about
  three years of history: when fewer than three years are available the formation period starts at the first close,
  as long as it covers at least one year (0 otherwise). Shorter than the paper's 3-5 years: a choice forced by the
  data. `market.ltr` / `market.ltr_features`; stored for new picks via `market.features` and `nn.make_features` (not
  MODEL_NUMERIC); backfilled for older picks by `research.enrich` using closes up to each pick's own date only (other
  features untouched). Directional (bearish calls flip it, so the rule shorts the biggest long-term winner). Research
  rule: `long-term reversal (-z_ltr)`; `z_ltr` is also available to the learned ridge/gbm/net.
- **What to look at:** raw and risk-matched lift, t and t_nw, and the luck bar (now 43 tries). The effect is slow
  (years) and our hold is ~90 days, the paper's losers were mostly small stocks and the edge concentrated in
  Januaries, so expect a weak result; compare against 1y trend (z_mom250) since a long-term loser is often also a
  recent loser.
- **Note:** until enrich finishes backfilling older picks they read `ltr = 0`; trust the result once `ltr` is out of
  `provisional` in the research kv (coverage share ≥ 99%). Picks with under two years of data will stay at 0 by
  design, so check `coverage.zero_share.ltr` too.
- **Result (preliminary, run 2026-11-16 06:59 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; coverage `ltr` 77.0%,
  still in `provisional`, so not final):** lift **+0.32%**, beat **51.0%**, t **1.08** (t_nw **0.65**); risk-matched
  lift **+0.39%**, beat_adj **52.0%**, t **1.38** (t_nw **0.85**). n_eff 997. Weak, as expected; well under the luck bar
  (3.25 for 43 tries). Ridge weight on z_ltr +0.0013. Re-check once `ltr` leaves `provisional`.
- **Result (final, run 2026-11-17 17:40 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; coverage `ltr` 100%, zero
  share 0.5%, not in `provisional`):** lift **+0.53%**, beat **50.3%**, t **1.78** (t_nw **1.32**); risk-matched lift
  **+0.72%**, beat_adj **51.7%**, t **2.52** (t_nw **1.76**). n_eff 1,480. Small and positive, a bit stronger once
  risk-matched (long-term losers here were not just high-beta names), but under the luck bar (3.25 for 44 tries) on
  every t and not in `luck.clear`. Read as: a faint long-horizon reversal, not a reason to change the ranking. Ridge
  weight on z_ltr +0.0008. Same run: app +1.49% / 53.4% / t 4.54 (t_nw 1.91); illiquidity premium +1.21% / t 4.04
  (t_nw 2.63; risk-matched t_nw 2.42); `clear_nw` empty; random beat 51.0%. Idea 15 (`delay`) coverage 0% at this run
  (enrich had not started on it yet).

### 15. Price delay premium: stocks that take in market news late (Hou & Moskowitz)
- **Added:** 2026-11-16
- **Source:** Hou & Moskowitz (2005), "Market Frictions, Price Delay, and the Cross-Section of Expected Returns",
  Review of Financial Studies 18(3), 981-1020: https://econpapers.repec.org/RePEc:oup:rfinst:v:18:y:2005:i:3:p:981-1020
  (also https://ideas.repec.org/a/oup/rfinst/v18y2005i3p981-1020.html)
- **Why:** some stocks respond to market-wide news days or weeks late (few analysts, few institutions, little
  attention). The paper's delay measure, from regressions of weekly returns on the market's current and lagged weekly
  returns, finds the most delayed stocks earned a large premium that size, liquidity and value don't explain, read as a
  neglect / friction premium. A new family for the log: it is about *how* a price follows the market, not its level
  (beta, idea 4; downside beta, 11), its own noise (IVOL, 13) or its liquidity (Amihud, 8). Built from a year of weekly
  returns, which suits our ~90-day hold.
- **Computed as:** non-overlapping 5-session returns of the stock and SPY over the last 52 weeks up to the pick's own
  date; regress the stock's weekly return on SPY's same-week return (R2 same) and on SPY's same-week plus previous 4
  weeks' returns (R2 full); `delay` = 1 - R2 same / R2 full (the paper's D1), clipped to [0, 1]; 0.20 (neutral, also
  `research.NEUTRAL`) without 40 usable weeks or a degenerate fit. `market.delay` / `market.delay_features`; stored for
  new picks via `market.features` and `nn.make_features` (not MODEL_NUMERIC); backfilled for older picks by
  `research.enrich` using closes up to each pick's own date only (other features untouched). Directional (bearish
  calls flip it, so the rule shorts the stock that reacts at once, the weak side of the premium, as with Amihud).
  Research rule: `price delay premium (z_delay)`; `z_delay` is also available to the learned ridge/gbm/net.
- **What to look at:** raw and risk-matched lift, t and t_nw, and the luck bar (now 44 tries). Compare against the
  illiquidity rule (z_amihud), the one fixed rule that has cleared the plain luck bar: delay and illiquidity are
  correlated, so a delay result that only repeats Amihud's adds little. The paper's premium sits mostly in small,
  neglected stocks and our ideas are mostly large caps, so expect a small effect. Caveat: our bars come from Alpaca's
  IEX feed, whose closes can be stale for thinly traded names, which itself looks like delay; one more reason to read
  it next to Amihud.
- **Note:** until enrich finishes backfilling older picks they read the neutral 0.20; trust the result once `delay` is
  out of `provisional` in the research kv (coverage share ≥ 99%). Data caveat for every rule: PARA picks are a
  reused ticker (Parabolic Technologies, not Paramount; see docs/feature_ideas.md 2026-11-16), a small number of bad
  rows in every result until they are flagged.
- **Result (final, run 2026-11-18 17:19 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; coverage `delay` 100%, zero
  share 0.2%, not in `provisional`):** lift **-0.20%**, beat **50.1%**, t **-0.67** (t_nw **-0.59**); risk-matched lift
  **+0.21%**, beat_adj **52.5%**, t **0.72** (t_nw **0.59**). Outlier check: lift_w -0.44% (t -1.82), median per-call
  lift -0.48%. n_eff 2,062. Nothing: the slow-reacting stock was no better a #1 than its belief's average idea, and
  it adds nothing beside the illiquidity rule (same run +1.21% / t 4.04 / t_nw 2.63 / lift_w +0.73%). Read as: price
  delay is not a usable signal on our mostly large-cap ideas. Ridge weight on z_delay +0.0013.

### 16. Realized skewness: avoid lottery-shaped return distributions (Amaya, Christoffersen, Jacobs & Vasquez)
- **Added:** 2026-11-17
- **Source:** Amaya, Christoffersen, Jacobs & Vasquez (2015), "Does realized skewness predict the cross-section of
  equity returns?", Journal of Financial Economics 118(1), 135-167:
  https://econpapers.repec.org/RePEc:eee:jfinec:v:118:y:2015:i:1:p:135-167 (working paper:
  https://ideas.repec.org/p/aah/create/2013-41.html)
- **Why:** stocks whose recent returns were strongly right-skewed (long quiet stretches with rare big up days) went on
  to earn clearly less than left-skewed ones; the paper finds a long-short weekly spread of about 19 basis points,
  read as investors overpaying for lottery-like payoffs (in line with skewness-preference theory, e.g. Barberis &
  Huang 2008). Not the same as the MAX effect (idea 5), which looks at the *size* of the biggest days, or volatility
  (ideas 13, high/low vol): skewness is the *shape*, how lopsided the up and down days are, scaled by volatility.
- **Computed as:** `rskew` = sample skewness of daily log returns over the last 63 sessions (~3 months) up to the
  pick's own date, clipped to [-5, 5]; 0 without 40 returns or with no variation. The paper uses 5-minute intraday
  returns over a week; we only have daily closes, so this is the daily-return version (a common simplification), over
  a longer window so it isn't three or four days' noise and to suit our ~90-day hold: a choice, not the paper's
  exact measure. `market.rskew` / `market.rskew_features`; stored for new picks via `market.features` and
  `nn.make_features` (not MODEL_NUMERIC); backfilled for older picks by `research.enrich` using closes up to each
  pick's own date only (other features untouched). Directional (bearish calls flip it, so the rule shorts the most
  right-skewed stock). Research rule: `avoid right-skewed stocks (-z_rskew)`; `z_rskew` is also available to the
  learned ridge/gbm/net.
- **What to look at:** raw and risk-matched lift, t and t_nw, and the luck bar (now 45 tries). Compare against
  "avoid lottery stocks (-z_max5)" and the vol rows: in this sample wild stocks have done better (ideas 5 and 13 ran
  the "wrong" way), so a skewness rule that only repeats them adds little. The paper's effect is short-horizon
  (weekly rebalancing) and decays over a month, so on a 90-day hold expect it to be weak.
- **Note:** until enrich finishes backfilling older picks they read `rskew = 0`; trust the result once `rskew` is out
  of `provisional` in the research kv (coverage share >= 99%). Idea 15 (`delay`) is backfilled first in the same loop
  order, so `rskew` fills in alongside or just after it.
- **Result (final, run 2026-11-18 17:19 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; coverage `rskew` 100%, zero
  share 0%, not in `provisional`):** lift **+1.45%**, beat **53.4%**, t **4.96** (t_nw **2.90**); risk-matched lift
  **+1.51%**, beat_adj **55.0%**, t **5.43** (t_nw **3.38**). Outlier check: lift_w **+1.26%** (t 5.01, t_nw 2.57),
  median per-call lift +1.13%, top-10 share 24%. n_eff 922. The strongest fixed rule in the log so far: it is in
  `luck.clear`, `clear_adj`, `clear_w` and, alone among fixed rules, `clear_adj_nw` (risk-matched t_nw 3.38 over the
  3.26 bar for 45 tries); not a few lottery tickets (lift_w barely moves, median well above zero). The paper's side
  wins here, unlike MAX (5) and IVOL (13), which ran the other way: the shape of the returns, not their size, is what
  helped. Caveats before reading it as an edge: (a) its raw numbers sit almost on top of the app's own #1 (app +1.49% /
  53.4% / t 4.54 / t_nw 1.91 / lift_w +1.24%), so part of it may be the same picks; there is no agreement measure yet
  (proposed in docs/feature_ideas.md 2026-11-18); (b) 45 rules tried, so one clearing the bar by a small margin is
  still possible luck; (c) fixed rules do not go live; only ranker v2's learned models can use z_rskew, and only through
  `fit_production`'s gate (ridge weight on z_rskew -0.0037, mid-sized: z_max5 +0.0059, z_beta +0.0041).
  Same run: `clear_nw` = gbm, gbm (+ shifted); `clear_adj_nw` = gbm (risk-adjusted), this rule, neural net
  (risk-adjusted); random beat 51.0%. Idea 17 (coskewness) tests whether the market-linked part of skewness carries it.

### 17. Coskewness: stocks that fall hardest when the market swings (Harvey & Siddique)
- **Added:** 2026-11-18
- **Source:** Harvey & Siddique (2000), "Conditional Skewness in Asset Pricing Tests", Journal of Finance 55(3),
  1263-1295: https://econpapers.repec.org/RePEc:bla:jfinan:v:55:y:2000:i:3:p:1263-1295 (author copy:
  https://people.duke.edu/~charvey/Research/Published_Papers/P56_Conditional_skewness_in.pdf)
- **Why:** investors dislike stocks that add left tail to a portfolio, ones that do worst exactly when the market makes
  its biggest moves; the paper finds those negatively coskewed stocks earn a premium (about 3.6% a year in its
  momentum and size portfolios) and that systematic skewness explains part of the momentum effect. The natural
  follow-up to idea 16: realized skewness (`rskew`) is the stock's *own* lopsidedness and was the strongest fixed rule
  yet; coskewness is the *market-linked* part. If coskewness carries the effect, rskew is a priced risk; if it doesn't,
  rskew is more likely the lottery-preference story (or overlap with the app's own #1).
- **Computed as:** daily simple returns of the stock and SPY over the last 252 sessions (~1 year) up to the pick's own
  date; residuals e from a market-model fit on that window, m = SPY's demeaned return; `coskew` = mean(e * m^2) /
  (sqrt(mean(e^2)) * mean(m^2)) (the paper's standardized coskewness, beta_SKD), clipped to [-3, 3]; 0 without 150
  matched days or with no variation. The paper uses 60 monthly returns; we use a year of daily returns (data and
  hold-length choice, not the paper's exact measure). `market.coskew` / `market.coskew_features`; stored for new picks
  via `market.features` and `nn.make_features` (not MODEL_NUMERIC); backfilled for older picks by `research.enrich`
  using closes up to each pick's own date only (other features untouched). Directional (bearish calls flip it, so the
  rule shorts the most positively coskewed stock). Research rule: `negative coskewness premium (-z_coskew)`;
  `z_coskew` is also available to the learned ridge/gbm/net once its coverage passes (learn_keys).
- **What to look at:** raw and risk-matched lift, t, t_nw, lift_w and the luck bar (now 46 tries); compare against
  idea 16 (rskew) and betting against beta (4) / downside beta (11), which also read how a stock moves with SPY. Daily
  coskewness is noisy and the paper's premium is modest, so expect it to be weak; a weak result plus a strong rskew
  points toward the lottery reading of idea 16.
- **Note:** until enrich finishes backfilling older picks they read `coskew = 0`; trust the result once `coskew` is out
  of `provisional` in the research kv (coverage share >= 99%).
- **Result (final, run 2026-11-21 17:36 UTC, 4,391 beliefs, test from 2024-12-03, n=2,703; coverage `coskew` 100%, zero
  share 0.2%, not in `provisional`):** lift **+0.83%**, beat **52.2%**, t **3.00** (t_nw **3.12**); risk-matched lift
  **+0.87%**, beat_adj **53.6%**, t **3.26** (t_nw **3.95**). Outlier check: lift_w **+0.70%** (t 2.86, t_nw 2.62),
  median per-call lift +0.90%, top-10 share 35%. Is it new: same_as_app **24.5%**, n_diff 2,040, lift_diff **+0.40%**
  (t 0.76, t_nw 0.58). Luck bar 3.27 for 46 tries: in `clear_adj` and top of `clear_adj_nw` (risk-matched t_nw 3.95),
  not in `clear` / `clear_nw` / `clear_w` (raw t 3.00 and 3.12 under the bar). Reading: the paper's side wins, about
  half the size of idea 16 (rskew +1.45%), and where it disagrees with the app's #1 it adds nothing measurable
  (lift_diff t 0.58), so it looks like a weaker restatement of what the app already finds rather than a new edge.
  Coskewness does not carry rskew's effect: rskew's own is-it-new numbers (same run: same_as_app 25.2%, n_diff 2,023,
  lift_diff **+1.23%**, t 2.24, t_nw 2.44) are much stronger, which leans toward the stock's own lopsidedness (lottery
  preference), not market-linked tail risk. Caveats: the kv reports n_eff = n (2,703) for this rule and its t_nw sits
  above the plain t, unusual for 90-day overlapping windows (rskew's n_eff is 922), so treat t_nw here with care;
  46 rules tried. Ridge weight on z_coskew -0.0017 (small). Fixed rules do not go live.
- **Also answers idea 16's caveat (a):** rskew picks the same #1 as the app on only 25% of calls and beats the app's #1
  by +1.23% where they differ (t_nw 2.44, under the 3.27 luck bar), so it is mostly *not* the app's picks restated;
  promising but not yet clear of luck on the head-to-head.

### 18. Variability of trading activity: avoid stocks whose trading swings the most (Chordia, Subrahmanyam & Anshuman)
- **Added:** 2026-11-21
- **Source:** Chordia, Subrahmanyam & Anshuman (2001), "Trading activity and expected stock returns", Journal of
  Financial Economics 59(1), 3-32: https://research.iimb.ac.in/fac_pubs/1268 (working paper:
  https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2014/03/0121.pdf)
- **Why:** the paper expected stocks with jumpier liquidity to pay a premium, and found the opposite: a strong
  *negative* link between the variability of dollar volume (and turnover) and later returns, even after controlling for
  the level of trading, size, book-to-market and momentum. A volume-only idea the log hasn't tried: Amihud (8) is the
  *level* of price impact, rvol is the last few weeks' volume, continuing overreaction (9) signs volume by price moves;
  none reads how *unsteady* trading has been.
- **Computed as:** `cvvol` = coefficient of variation (sample std / mean) of daily dollar volume (close x volume) over
  the last 252 sessions (~1 year) up to the pick's own date, clipped to [0, 5]; 0 without 120 priced sessions or with no
  volume. The paper uses monthly dollar volume over 36 months; we use a year of daily data from our feed (IEX by
  default, a slice of total volume, fine for ranking stocks against each other): a data and hold-length choice, not the
  paper's exact measure. Daily CV also rises with event spikes (earnings days), which the monthly version smooths.
  `market.cvvol` / `market.cvvol_features`; stored for new picks via `market.features` and `nn.make_features` (not
  MODEL_NUMERIC); backfilled for older picks by `research.enrich` using closes and volumes up to each pick's own date
  only (other features untouched). Directional (bearish calls flip it, so the rule shorts the stock whose trading swings
  most). Research rule: `steady trading activity (-z_cvvol)`; `z_cvvol` is also available to the learned
  ridge/gbm/net once its coverage passes (learn_keys).
- **What to look at:** raw and risk-matched lift, t, t_nw, lift_w, same_as_app / lift_diff, and the luck bar (now 47
  tries); compare with illiquidity (8, `z_amihud`, which cleared `clear` and `clear_adj` on 2026-11-21) and high vol:
  jumpy trading goes with small, volatile names, and in this sample those have done *well*, so the paper's side may run
  the wrong way here as MAX (5) and IVOL (13) did.
- **Note:** until enrich finishes backfilling older picks they read `cvvol = 0`; trust the result once `cvvol` is out of
  `provisional` in the research kv (coverage share >= 99%).
- **Result:** pending. At run 2026-11-21 21:05 UTC `cvvol` coverage was 12.6% (still in `provisional`); enrich is
  backfilling it.

### 19. Timing of the 52-week high: stocks that set their high recently (Bhootra & Hur)
- **Added:** 2026-11-21 (late)
- **Source:** Bhootra & Hur (2013), "The timing of 52-week high price and momentum", Journal of Banking & Finance
  37(10), 3773-3782: https://ideas.repec.org/a/eee/jbfina/v37y2013i10p3773-3782.html (also
  https://econpapers.repec.org/RePEc:eee:jbfina:v:37:y:2013:i:10:p:3773-3782)
- **Why:** stocks whose 52-week high was set recently beat stocks whose high was set long ago, by about 0.70% a month
  top decile vs bottom, and the classic "near the 52-week high" strategy (George & Hwang 2004) earns about twice as
  much among recent-high stocks. Read as recency bias: investors anchor on a fresh high and under-react to the news
  that made it, while an old high has faded from view. New to the log: the baseline "near highs (z_dist_high)" reads
  *how far* the price is from its high (and ran the wrong way here, -1.06% on 2026-11-02); this reads *when* the high
  was set. Two stocks 10% below their highs can have set them last week or last year. A position-length idea (the
  paper holds for months), so it suits our ~90-day hold.
- **Computed as:** `hi_age` = sessions since the highest close of the last 252 sessions (~1 year) up to the pick's own
  date, divided by 251 (0 = the high is today, 1 = a year ago); ties take the latest day; 0.5 (neutral, also
  `research.NEUTRAL`) without 200 priced sessions. The paper counts days since the 52-week high; dividing by the window
  only rescales it (rules are z-scored within a belief). `market.hi_age` / `market.hi_age_features`; stored for new
  picks via `market.features` and `nn.make_features` (not MODEL_NUMERIC); backfilled for older picks by
  `research.enrich` using closes up to each pick's own date only (other features untouched). Directional (bearish
  calls flip it, so the rule shorts the stock whose high is the most distant). Research rule:
  `recent 52-week high (-z_hi_age)`; `z_hi_age` is also available to the learned ridge/gbm/net once its coverage passes
  (learn_keys).
- **What to look at:** raw and risk-matched lift, t, t_nw, lift_w, same_as_app / lift_diff, pos_blocks /
  last_block_lift, and the luck bar (now 48 tries). Compare with "near highs (z_dist_high)" and the momentum rows
  (12-1, MAD, echo): a fresh high goes with strong recent momentum, so a result that only restates momentum adds
  little; lift_diff against the app tells whether it picks different stocks.
- **Note:** until enrich finishes backfilling older picks they read the neutral 0.5; trust the result once `hi_age` is
  out of `provisional` in the research kv (coverage share >= 99%). `cvvol` (idea 18) is backfilled first in the same
  loop, so `hi_age` fills in alongside or just after it.
- **Result:** pending.

### 20. Level of trading activity: low dollar volume (Brennan, Chordia & Subrahmanyam)
- **Added:** 2026-11-21 (night, extra run)
- **Source:** Brennan, Chordia & Subrahmanyam (1998), "Alternative factor specifications, security characteristics,
  and the cross-section of expected stock returns", Journal of Financial Economics 49(3), 345-373:
  https://ideas.repec.org/a/eee/jfinec/v49y1998i3p345-373.html
- **Why:** after Fama-French and Connor-Korajczyk risk adjustment, size and book-to-market, the paper finds a strong
  *negative* link between a stock's dollar trading volume and its later returns, read as a liquidity premium (heavily
  traded stocks are cheap to trade, so investors accept less). Idea 18 (`cvvol`) reads how *unsteady* trading is, and
  Chordia, Subrahmanyam & Anshuman control for the level; this tests the level itself. Amihud (idea 8) is price
  impact per dollar, which mixes volume with volatility; this is volume alone. Also a rough size proxy, since we have
  no market caps. Slow-moving, so it suits our ~90-day hold.
- **Computed as:** `ldvol` = log of mean daily dollar volume (close x volume) over the last 252 sessions (~1 year) up
  to the pick's own date; 15.0 (neutral, also `research.NEUTRAL`) without 120 priced sessions with volume. Our feed is
  IEX by default, a slice of total volume, so the level is not an absolute size but ranks stocks against each other.
  `market.ldvol` / `market.ldvol_features`; stored for new picks via `market.features` and `nn.make_features` (not
  MODEL_NUMERIC); backfilled for older picks by `research.enrich` using closes and volumes up to each pick's own date
  only (other features untouched). Directional (bearish calls flip it, so the rule shorts the most heavily traded
  stock). Research rule: `low dollar volume (-z_ldvol)`; `z_ldvol` is also available to the learned ridge/gbm/net once
  its coverage passes (learn_keys).
- **What to look at:** raw and risk-matched lift, t, t_nw, lift_w, same_as_app / lift_diff, pos_blocks /
  last_block_lift, and the luck bar (now 49 tries). Read it next to illiquidity (z_amihud, which cleared `clear`, is in
  `luck.steady` and was ahead in its latest stretch, +1.73%): if ldvol repeats Amihud, the price-impact part adds
  nothing; if Amihud beats it clearly, volatility per dollar traded is what carries that rule.
- **Note:** until enrich finishes backfilling older picks they read the neutral 15.0; trust the result once `ldvol` is
  out of `provisional` (coverage share >= 99%). Backfilled after `cvvol` and `hi_age` in the same loop.
- **Result:** pending.
