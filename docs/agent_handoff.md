# Agent handoff

Short notes between the Claude sessions working on this repo (build chat, research routine, polish routine, weekly
brain upgrade). Newest at the bottom. One entry per session that pushed something: date, who, what changed, files,
and anything the others must know. Keep entries to a few lines; details go in the topic logs.

## 2026-11-06 (research routine)
- Added idea 5, MAX effect ("avoid lottery stocks", rule `-z_max5`), commit 6b6efd1. New feature `max5` in
  `market.py` (`max5`, `max_features`, `features()`), `nn.make_features` num (not MODEL_NUMERIC), `research.FEATS` +
  `DIRECTIONAL`, and `research.enrich` backfill. Test: `test_max_effect_lottery_rule_and_enrich_backfill`.
- `enrich` is backfilling `max5` for older picks; research results for that rule are unreliable until it finishes.
- Logged the 2026-11-06 16:15 rerun (after volatile ideas were excluded) in `docs/research_ideas.md`.

## 2026-11-07 (research routine)
- Added `CLAUDE.md` and this file so sessions can hand work to each other through the repo.

## 2026-11-07 (polish routine)
- seeder.news_beliefs: the "I don't think ..." side no longer lower-cases names/acronyms (`_lower_first`); existing
  DB rows ("aI", "iran") are unchanged and age out of the feed. Belief text format is otherwise the same.
- /v4/brain `graded[]` gains `stock_vs_market`; Brain page "Just graded" shows the stock's move vs S&P, and the
  ranker box says "retrained <date>" instead of "live since". Files: backend/v4/seeder.py, backend/v4/brain.py,
  backend/v4/tests/test_v4.py, frontend/src/components/BrainPage.jsx.

## 2026-11-08 (build chat, CTO)
- research.py: new `MLPRanker`/`_fit_mlp`; ranker v2 now also evaluates "neural net (learned)" / "(risk-adjusted)"
  and `fit_production` may pick `mlp`/`mlp_adj` (kind "mlp", stored in GBM_KEY). Gate untouched. nn.py:
  `_training_rows` ORDER BY p.id. Details in docs/brain_upgrades.md (2026-11-08). Murad is in hospital: he wants
  sessions self-sufficient and to notify only when his action is needed.
- brain.py `_forward()` → `/v4/brain` `forward`: live forward test (non-backfill calls, directional ideas) per
  checkpoint: #1 beat rate, avg, lift vs same-belief ideas, t. BrainPage shows it under the scorecard. This is the
  metric Murad will use before trading his own money; don't fold backfill into it.
- augment.py (new) + seeder hourly `augment` step + research.load(include_aug) / run / fit_production "+ shifted"
  candidates. research.load builds compact rows directly (FeatRow.from_array, `_matrix`). Shifted calls are
  training-only; don't let them into tests or baselines. Env: MP_AUG_SHIFTS, MP_AUG_BATCH, MP_AUG_MAX.
- IMPORTANT: picks.final_rank is 0-based (0 = the #1 shown). research/lineages/brain used == 1 (the #2) until
  today; fixed. Use rank 0 for "app #1" everywhere. Expect ranker v2 + net to turn off at the next refit (the real #1
  is a higher bar). New: confidence thirds (`research.confidence_label`, ranker `confidence`, pick `confidence`,
  features `rv2_conf`/`rv2_spread`/`rv2`), `/v4/brain` `forward.by_confidence`.
## 2026-11-08 (daily polish walk)
- Frontend only: WhatsNew.jsx (no "Smarter #1 pick" claim while ranker v2 can be off; date Nov 8), BrainPage.jsx forward
  test now renders `forward.by_confidence` (keys high/medium/low) and a t-stat note; its lift is labelled "vs our
  average idea" because `_forward` and research lift include the #1 in the average. StrategyCard badge tooltip reworded.
  No backend changes. If you change `_forward`'s lift to exclude the #1, update those labels.
