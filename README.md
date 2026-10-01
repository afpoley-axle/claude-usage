# claude-usage

Weekly history of my Claude Code token usage, built from the local transcripts in `~/.claude/projects`.

- [`WEEKLY.md`](WEEKLY.md): weekly totals, plus a by-model and by-project breakdown for the last two weeks
- `data/daily.csv`: the durable record, one row per date × project × model
- `data/weekly.csv`: weekly rollup by model

Claude Code deletes transcripts after about 30 days, so `daily.csv` keeps the history. Each run merges new numbers into it by taking the larger value per row, so pruned transcripts never remove data. Run it at least every few weeks or older days will be lost before they're recorded.

## Usage

```bash
./update.sh             # collect, commit a snapshot, push if a remote exists
python3 collect.py      # collect only, no commit
./install-schedule.sh   # run update.sh every Monday 09:00 via launchd
```

Requires only Python 3 (stdlib). Token counts come straight from the API `usage` fields; streamed messages are de-duplicated by message and request ID. Weeks start Monday, local time.
