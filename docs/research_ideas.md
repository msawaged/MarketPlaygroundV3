# Ranker research ideas log

Each idea is added as a fixed scoring rule in `backend/v4/research.run()` and tested walk-forward (90-day embargo,
calls never seen) against the current #1 pick. Nothing here goes into the live ranking directly; ranker v2
(`research.fit_production`) keeps its own out-of-sample gate.

Metrics: **lift** = #1 pick's 90-day excess return minus the belief's average idea; **beat** = share of #1 picks that
beat the S&P 500 in the belief's direction; **t** = t-stat of lift.

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
- **Result:** pending.
