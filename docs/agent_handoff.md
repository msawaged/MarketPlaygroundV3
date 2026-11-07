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
