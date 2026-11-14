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
  "+ app (25%)" mixes). Learned ridge weight on z_seas +0.0035. Re-check once enrich reports nothing remaining. Same
  run: app +1.49% / 53.4% / t 4.54 (adj +1.24% / t 3.89); illiquidity premium +1.21% / 53.1% / t 4.04 (adj +1.00% /
  t 3.44); random beat 51.0%.

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
- **Result:** pending.
