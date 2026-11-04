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
- **Result:** pending.
