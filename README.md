# claude-usage

Weekly history of my Claude Code token usage, built from the local transcripts in `~/.claude/projects`.

- [`WEEKLY.md`](WEEKLY.md): weekly totals, plus a by-model and by-project breakdown for the last two weeks
- `data/daily.csv`: the durable record, one row per date × allowance week × project × model
- [`report.html`](report.html): charts by project and model for any week, plus weekly history
- `data/weekly.csv`: weekly rollup by model

Claude Code deletes transcripts after about 30 days, so `daily.csv` keeps the history. Each run merges new numbers into it by taking the larger value per row, so pruned transcripts never remove data. Run it at least every few weeks or older days will be lost before they're recorded.

## Usage

```bash
./update.sh             # collect, commit a snapshot, push if a remote exists
python3 collect.py      # collect only, no commit
./install-schedule.sh   # run update.sh every Thursday 14:55 via launchd
```

Requires only Python 3 (stdlib). Token counts come straight from the API `usage` fields; streamed messages are de-duplicated by message and request ID. Weeks run Thursday 15:00 to Thursday 15:00 local time, matching the weekly allowance reset.
