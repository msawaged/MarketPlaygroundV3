# MarketPlayground: notes for every Claude session

Several Claude sessions work on this repo: the build chat with Murad, plus scheduled routines (daily ranker
research, daily polish walk, weekly brain upgrade). They can't message each other, so they coordinate here.

- **Before you start:** pull `v4-polish` and read the newest entries in `docs/agent_handoff.md`.
- **When you finish:** if you pushed anything, add a short dated entry at the bottom of `docs/agent_handoff.md`
  (who you are, what changed, files touched, anything another session must know or should not undo).
- Branch `v4-polish` auto-deploys to Render. Run the backend tests before pushing:
  `PYTHONPATH=./ python -m pytest backend/v4/tests -q`.
- Topic logs: ranker research ideas in `docs/research_ideas.md`, brain upgrades in `docs/brain_upgrades.md`,
  UI polish in `docs/polish_log.md`.
- Ranker v2's gate (`research._passes`, `fit_production`) is changed only deliberately, and the change is written up in
  `docs/brain_upgrades.md`.
