# Setup guide

About five minutes. You need Python 3 and git; there is nothing to `pip install`.

> Prefer to have Claude do it? Open this repo in Claude Code and say "help me set up claude-usage". The repo's [CLAUDE.md](../CLAUDE.md) walks it through these steps.

## 1. Get the code

```bash
git clone <repo-url> claude-usage
cd claude-usage
python3 --version   # 3.8 or newer
```

## 2. Pick where your data lives

Your usage history is personal, so it is kept out of this repo. By default it goes in `./data/`, which is git-ignored.

Better: keep it in a fixed folder outside the repo, so it survives re-cloning and is shared by every checkout or git worktree of the tool.

```bash
mkdir -p ~/claude-usage-data
echo 'export CLAUDE_USAGE_DATA_DIR=~/claude-usage-data' >> ~/.zshrc   # or ~/.bashrc
source ~/.zshrc
```

If you skip this, everything still works; just don't delete `data/`, because it is the only copy of your history once Claude Code prunes old transcripts.

## 3. Set your allowance reset time (optional)

Reports group usage into weeks that start when your weekly allowance resets. The default is **Thursday 15:00 local time**. If yours differs, set it before your first run:

```bash
export CLAUDE_USAGE_RESET_DAY=mon     # mon..sun
export CLAUDE_USAGE_RESET_HOUR=9      # 0-23, local time
```

Add these to your shell profile too. To find your reset time, check the usage screen in Claude Code or your Claude account settings, which shows when your weekly limit resets. Changing it later re-buckets only days that still have transcripts (about 30 days).

## 4. Run it

```bash
python3 collect.py
```

You should see something like `179 daily rows -> /Users/you/claude-usage-data: daily.csv, weekly.csv, WEEKLY.md, report.html`. Open `report.html` in a browser.

What it reads: every transcript under `~/.claude/projects` (or `$CLAUDE_CONFIG_DIR/projects`). Nothing leaves your machine.

**First run caveat:** Claude Code deletes transcripts after about 30 days (the `cleanupPeriodDays` setting in your Claude Code `settings.json`), so your first run can only recover roughly the last month. Run it regularly from now on, and optionally raise `cleanupPeriodDays` to keep more transcripts around.

## 5. Run it automatically (recommended)

### macOS

```bash
./install-schedule.sh
```

This installs a launchd agent that runs `update.sh` every week, five minutes before your reset. If the Mac is asleep, it runs on wake. It saves your `CLAUDE_USAGE_*` variables at install time, so rerun the installer if you change them. Logs go to `logs/update.log`.

Check it, run it now, or remove it:

```bash
launchctl print gui/$(id -u)/com.claude-usage.weekly | head
launchctl kickstart -k gui/$(id -u)/com.claude-usage.weekly
launchctl bootout gui/$(id -u)/com.claude-usage.weekly && rm ~/Library/LaunchAgents/com.claude-usage.weekly.plist
```

### Linux

`install-schedule.sh` is macOS only. Add a cron entry that runs `collect.py` weekly, for example every Thursday at 14:55:

```cron
55 14 * * 4 CLAUDE_USAGE_DATA_DIR=$HOME/claude-usage-data /usr/bin/python3 /path/to/claude-usage/collect.py >> /path/to/claude-usage/logs/update.log 2>&1
```

### Windows

Use Task Scheduler (weekly trigger) to run `python C:\path\to\claude-usage\collect.py`, or run the Linux instructions inside WSL. Under WSL, set `CLAUDE_CONFIG_DIR` if Claude Code runs on the Windows side, so the tool finds its transcripts.

## 6. Share or back up your data (optional)

Nothing is committed or pushed by default. To back up your history or feed it to a weekly Slack post, make the data folder its own **private** repo:

```bash
cd ~/claude-usage-data
git init && git remote add origin <your-private-repo-url>
cd -
CLAUDE_USAGE_PUSH=1 ./update.sh
```

`update.sh` refuses to push unless the data folder is its own git repo, so your data cannot end up in the tool repo.

## 7. Weekly Slack DM (optional)

Get last week's totals as a Slack message to yourself, built locally with `python3 summary.py`. See [SLACK.md](SLACK.md). It only ever goes to your own DM.

## Updating prices

Estimated cost uses the `PRICES` table at the top of `report.py`. When a new model ships, add a line for it and rerun `collect.py`. Models without a price are counted as $0 and listed at the bottom of the report.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No transcripts found at ...` | Claude Code hasn't written transcripts there. Check `ls ~/.claude/projects`, or set `CLAUDE_CONFIG_DIR` if you use a custom config directory. |
| `Bad reset config` | `CLAUDE_USAGE_RESET_DAY` must be `mon`..`sun`, and `CLAUDE_USAGE_RESET_HOUR` a number from 0 to 23. |
| Weeks start on the wrong day or hour | Check the reset variables in the same shell (or in the launchd job: rerun `./install-schedule.sh` after exporting them). |
| Scheduled job never runs | Read `logs/update.log`. Confirm it is loaded with `launchctl print gui/$(id -u)/com.claude-usage.weekly`. Make sure `python3` works in a login shell (`zsh -l -c 'python3 --version'`). |
| Cost totals look low | A model has no entry in `PRICES`; see the note at the bottom of `report.html`. |
| History looks short | Only transcripts from the last ~30 days exist on the first run. It fills in going forward. |
| `CLAUDE_USAGE_PUSH=1 ... is not its own git repo` | Run `git init` inside the data folder first (step 6). |
| History disappeared after re-cloning | Data lives in the data folder, not the repo. Use a fixed `CLAUDE_USAGE_DATA_DIR` (step 2) and restore from your private data repo or backup. |
