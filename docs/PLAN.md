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

- [x] `demo.py` (or `collect.py --demo`): seeded fake `daily.csv`, about 12 weeks, 4 made-up projects (`web-app`, `data-pipeline`, `docs-site`, ...), 3 current models. No real data.
- [x] Generate `examples/report.html` from the demo data.
- [x] Capture `docs/img/portal.png` plus a dark-mode variant with the browser tool.
- [x] Embed the screenshot at the top of the README.
- [ ] Optional: GitHub Pages link to the live demo report.
- [x] `./screenshots.sh` regenerates the demo report and screenshots (instead of a Makefile).

## Phase 2: Setup guide (`docs/SETUP.md`)

- [x] Prerequisites: Python 3, git; macOS (launchd), with notes for Linux (cron/systemd) and Windows (Task Scheduler/WSL).
- [x] Steps: clone, run `python3 collect.py`, open `report.html`, optionally `./install-schedule.sh`, how to uninstall.
- [x] Where transcripts live; `CLAUDE_CONFIG_DIR`.
- [x] The 30-day pruning caveat: the first run recovers only about 30 days, so run it early.
- [x] Optional tip: raise `cleanupPeriodDays` in Claude Code settings.
- [x] Troubleshooting: "No transcripts found", launchd not firing (`logs/update.log`), wrong week boundaries.
- [x] Link from the README.
- [x] Root `CLAUDE.md` so Claude Code can walk a new user through setup.

## Phase 3: Slack summary (local, self-DM only)

Decision: Pattern B (local only). A cloud Routine (Pattern A: push data to a private repo, Routine reads it) is a possible future alternative, documented but not built. Slack messages go **only** to the user's own DM; this is an explicit rule in `CLAUDE.md` and `docs/SLACK.md`.

- [x] `summary.py`: deterministic Slack text for the last completed week (`--no-projects`, `--link`).
- [x] `docs/SLACK.md`: setup, copy-pasteable scheduled-task prompt, self-DM rule, comparison of delivery methods.
- [x] Self-DM-only rule in `CLAUDE.md`.
- [x] Sample message using synthetic data.
- [x] Migrated the maintainer's scheduled task `claude-usage-slack-report`: new `data/` paths, uses `summary.py`, fires after the reset (15:05 plus jitter), self-DM only.
- [x] `summary.py` tests (week selection around the reset boundary).
- [ ] Future: team rollup via a private shared data repo and a cloud Routine (must still respect the self-DM rule or get its own explicit rule).

## Phase 4: New figures and data

- [x] Cache hit rate per week: `cache_read / (input + cache_write + cache_read)` (line chart, axis spans at least 10 points so noise isn't exaggerated).
- [x] Per-message trends: est. cost, output tokens, or total tokens per message (toggle).
- [ ] Daily calendar heatmap, last 12 weeks.
- [ ] Model mix over time (stacked share).
- [x] Burn-down: running total through the selected allowance week vs. the typical week and earlier weeks, with an optional budget line (`CLAUDE_USAGE_WEEKLY_BUDGET`, cost view).
- [ ] Week-over-week delta and rolling 4-week average in `WEEKLY.md`.
- [ ] Subscription value: API-equivalent cost vs. plan price (configurable).
- [ ] Day-of-week and hour-of-day patterns (needs an hour key or a separate table).
- [ ] New collected fields, added carefully because merge-by-max keys on the current schema: sessions per day, subagent vs. main-thread share (`isSidechain`), tool-call counts, 5m vs 1h cache-write split.

## Phase 5: Code and repo hygiene

- [x] Tests (`tests/`, `python3 -m unittest discover`): `week_start` (boundaries, rollover, DST, custom resets), reset config parsing, dedup by message and request ID, merge-by-max (extracted to `merge_daily`), CSV round trip, `cost()`, and `summary.py` week selection.
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
- Is this for individual use per person, or a team rollup?
