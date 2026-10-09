# Project plan: polish claude-usage for sharing

Goal: make this repo something coworkers can clone, set up in minutes, and get a weekly usage summary in Slack.

Status key: `[ ]` todo, `[x]` done.

## Phase 0: Before sharing (blockers)

- [x] **Privacy decision.** Decided: tool-only repo, `data/` git-ignored, all generated files written there. (Git history before this branch still contains old snapshots; see open questions.)
- (original options:) `data/daily.csv`, `WEEKLY.md` and `report.html` contain real project names, and the git history has about 14 snapshots of them. Choose one:
  - Tool-only repo: gitignore `data/`, `WEEKLY.md`, `report.html`; keep personal data in a separate private repo.
  - Keep data, but add `--anonymize` / `PROJECT_ALIASES` to `collect.py` and squash or rewrite history.
- [x] Add `LICENSE` (MIT).
- [x] Gitignore each user's own `data/` so coworkers don't commit it back.
- [x] Make the allowance reset configurable (`RESET_WEEKDAY` / `RESET_HOUR` in `collect.py`) via env var or `config.toml`; document how to find your own reset time.
- [x] Make `git push` in `update.sh` opt-in.
- [x] Document the `PRICES` table in `report.py` and the "unpriced model" warning, so users know to update it when new models ship.

## Phase 1: Demo data and README figure

- [ ] `demo.py` (or `collect.py --demo`): seeded fake `daily.csv`, about 12 weeks, 4 made-up projects (`web-app`, `data-pipeline`, `docs-site`, ...), 3 current models. No real data.
- [ ] Generate `examples/report.html` from the demo data.
- [ ] Capture `docs/img/portal.png` plus a dark-mode variant with the browser tool.
- [ ] Embed the screenshot at the top of the README.
- [ ] Optional: GitHub Pages link to the live demo report.
- [ ] `make screenshots` target so images don't go stale.

## Phase 2: Setup guide (`docs/SETUP.md`)

- [ ] Prerequisites: Python 3, git; macOS (launchd), with notes for Linux (cron/systemd) and Windows (Task Scheduler/WSL).
- [ ] Steps: clone, run `python3 collect.py`, open `report.html`, optionally `./install-schedule.sh`, how to uninstall.
- [ ] Where transcripts live; `CLAUDE_CONFIG_DIR`.
- [ ] The 30-day pruning caveat: the first run recovers only about 30 days, so run it early.
- [ ] Optional tip: raise `cleanupPeriodDays` in Claude Code settings.
- [ ] Troubleshooting: "No transcripts found", launchd not firing (`logs/update.log`), wrong week boundaries.
- [ ] Link from the README.

## Phase 3: Routines and Slack sync (`docs/ROUTINES.md`)

Design note: a Routine runs in the cloud and cannot read `~/.claude/projects` on a laptop.

- [ ] Pattern A (recommended): launchd runs `update.sh` and pushes `data/` to GitHub. A weekly Routine (Thursday, shortly after the reset) clones the repo, reads the CSVs, and posts a summary to Slack via the Slack connector.
- [ ] Pattern B (local only): a scheduled task on the machine or a Slack webhook called from `update.sh` (`slack-post.sh` using `curl`).
- [ ] `summary.py`: deterministic Slack text (week-over-week change, top project, top model, cost) so the Routine only posts it.
- [ ] Copy-pasteable Routine prompt.
- [ ] Connector and channel setup steps; schedule recommendation.
- [ ] Sample Slack message screenshot (synthetic data).
- [ ] Failure modes: laptop asleep, stale data, missed runs.
- [ ] Team version: each person pushes `data/<username>/daily.csv`; the Routine aggregates.

## Phase 4: New figures and data

- [ ] Cache hit rate per week: `cache_read / (input + cache_write + cache_read)`.
- [ ] Cost per message and output tokens per message trends.
- [ ] Daily calendar heatmap, last 12 weeks.
- [ ] Model mix over time (stacked share).
- [ ] Burn-down: cumulative spend within the current allowance week, with a budget line.
- [ ] Week-over-week delta and rolling 4-week average in `WEEKLY.md`.
- [ ] Subscription value: API-equivalent cost vs. plan price (configurable).
- [ ] Day-of-week and hour-of-day patterns (needs an hour key or a separate table).
- [ ] New collected fields, added carefully because merge-by-max keys on the current schema: sessions per day, subagent vs. main-thread share (`isSidechain`), tool-call counts, 5m vs 1h cache-write split.

## Phase 5: Code and repo hygiene

- [ ] Tests: `week_start` (DST and boundaries), dedup by message and request ID, merge-by-max, `cost()`.
- [ ] Move the inline HTML in `report.py` to `template.html`.
- [ ] `argparse` for `collect.py` (`--no-push`, `--demo`, `--anonymize`, `--since`).
- [ ] `install-schedule.sh`: derive the schedule from the configured reset; add `uninstall-schedule.sh`.
- [ ] README restructure: pitch, screenshot, 3-command quick start, how it works, FAQ, cost-estimate caveat.
- [ ] CHANGELOG; issue/PR templates only if contributors are expected.

## Suggested order

1. Phase 0 privacy decision and LICENSE.
2. Phase 1 demo data and screenshot.
3. Phase 2 setup guide.
4. Phase 3 Routines and Slack.
5. Phase 4 figures, then Phase 5 tests and cleanup.

## Open questions

- Git history on the remote still holds old data snapshots (real project names). Before sharing the repo, publish from a fresh repo or rewrite history (`git filter-repo --path data --path WEEKLY.md --path report.html --invert-paths`).
- Tool-only repo or keep data? (decides Phase 0)
- Pattern A or B for Slack? Which channel?
- Is this for individual use per person, or a team rollup?
