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
- **Result:** pending (next research run after deploy).
