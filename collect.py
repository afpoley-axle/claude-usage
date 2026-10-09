#!/usr/bin/env python3
"""Collect Claude Code token usage from local transcripts into a git-trackable history.

Reads every ~/.claude/projects/**/*.jsonl transcript, de-duplicates assistant
messages (streamed responses are written several times), and aggregates usage
per (local date, project, model) into data/daily.csv. Then rebuilds
data/weekly.csv, data/WEEKLY.md and data/report.html from that history.

Claude Code deletes old transcripts (30 days by default), so daily.csv is the
durable record: existing rows are merged with fresh ones by taking the max of
each counter, so pruned transcripts never erase history.
"""

import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from report import cost, write_report

ROOT = Path(__file__).resolve().parent
# All generated files live in one directory, git-ignored by default. Point
# CLAUDE_USAGE_DATA_DIR elsewhere (e.g. a separate private repo) to keep them.
DATA = Path(os.environ.get("CLAUDE_USAGE_DATA_DIR", ROOT / "data")).expanduser().resolve()
DAILY_CSV = DATA / "daily.csv"
WEEKLY_CSV = DATA / "weekly.csv"
REPORT_MD = DATA / "WEEKLY.md"
REPORT_HTML = DATA / "report.html"
PROJECTS_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "projects"

METRICS = ["messages", "input", "output", "cache_write", "cache_write_1h", "cache_read"]
KEY = ["date", "week_start", "project", "model"]

# Weekly allowance reset, local time. Default Thursday 15:00; override with
# CLAUDE_USAGE_RESET_DAY (mon..sun) and CLAUDE_USAGE_RESET_HOUR (0-23).
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def reset_schedule():
    day = os.environ.get("CLAUDE_USAGE_RESET_DAY", "thu").strip().lower()[:3]
    hour = os.environ.get("CLAUDE_USAGE_RESET_HOUR", "15").strip()
    if day not in WEEKDAYS or not hour.isdigit() or not 0 <= int(hour) <= 23:
        sys.exit(f"Bad reset config: CLAUDE_USAGE_RESET_DAY={day!r} (mon..sun), CLAUDE_USAGE_RESET_HOUR={hour!r} (0-23)")
    return WEEKDAYS.index(day), int(hour)


RESET_WEEKDAY, RESET_HOUR = reset_schedule()


def project_name(cwd, fallback):
    if cwd:
        cwd = re.sub(r"/\.claude/worktrees/.*$", "", cwd)
        return Path(cwd).name or cwd
    return fallback


def scan_transcripts():
    """Return {(date, project, model): {metric: int}} from current transcripts."""
    messages = {}  # (message id, request id) -> (key, usage)
    for path in PROJECTS_DIR.rglob("*.jsonl"):
        fallback = path.relative_to(PROJECTS_DIR).parts[0]
        try:
            fh = path.open(encoding="utf-8")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"usage"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = rec.get("message")
                if not isinstance(msg, dict) or not msg.get("usage"):
                    continue
                model = msg.get("model") or "unknown"
                if model == "<synthetic>" or not rec.get("timestamp"):
                    continue
                ts = datetime.fromisoformat(rec["timestamp"].replace("Z", "+00:00"))
                local = ts.astimezone()
                key = (local.date().isoformat(), week_start(local),
                       project_name(rec.get("cwd"), fallback), model)
                u = msg["usage"]
                usage = {
                    "input": u.get("input_tokens") or 0,
                    "output": u.get("output_tokens") or 0,
                    "cache_write": u.get("cache_creation_input_tokens") or 0,
                    "cache_write_1h": (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0,
                    "cache_read": u.get("cache_read_input_tokens") or 0,
                }
                mid = (msg.get("id"), rec.get("requestId"))
                if mid in messages:
                    prev = messages[mid][1]
                    usage = {k: max(v, prev[k]) for k, v in usage.items()}
                messages[mid] = (key, usage)

    totals = defaultdict(lambda: dict.fromkeys(METRICS + ["cost"], 0))
    for key, usage in messages.values():
        row = totals[key]
        row["messages"] += 1
        for k, v in usage.items():
            row[k] += v
    return totals


def load_daily():
    rows = {}
    if DAILY_CSV.exists():
        with DAILY_CSV.open(newline="") as fh:
            for r in csv.DictReader(fh):
                rows[tuple(r[k] for k in KEY)] = {m: int(r.get(m) or 0) for m in METRICS}
    return rows


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def week_start(ts):
    """Start of the allowance week containing local datetime ts."""
    start = ts.replace(hour=RESET_HOUR, minute=0, second=0, microsecond=0)
    start -= timedelta(days=(ts.weekday() - RESET_WEEKDAY) % 7)
    if start > ts:
        start -= timedelta(days=7)
    return start.date().isoformat()


def fmt(n):
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= size:
            return f"{n / size:.1f}{unit}"
    return str(n)


def build_report(daily):
    weekly = defaultdict(lambda: dict.fromkeys(METRICS + ["cost"], 0))
    by_model = defaultdict(lambda: defaultdict(lambda: dict.fromkeys(METRICS + ["cost"], 0)))
    by_project = defaultdict(lambda: defaultdict(lambda: dict.fromkeys(METRICS + ["cost"], 0)))
    for (_, wk, project, model), m in daily.items():
        m = dict(m, cost=cost(model, m))
        for k, v in m.items():
            weekly[wk][k] += v
            by_model[wk][model][k] += v
            by_project[wk][project][k] += v

    write_csv(WEEKLY_CSV, ["week_start", "model"] + METRICS + ["est_cost_usd"],
              [[wk, model] + [m[k] for k in METRICS] + [round(m["cost"], 2)]
               for wk in sorted(by_model) for model, m in sorted(by_model[wk].items())])

    def total(m):
        return m["input"] + m["output"] + m["cache_write"] + m["cache_read"]

    lines = ["# Claude Code weekly usage", "",
             f"_Updated {datetime.now().astimezone():%Y-%m-%d %H:%M %Z}. "
             f"Weeks run {WEEKDAYS[RESET_WEEKDAY].title()} {RESET_HOUR:02d}:00 to {WEEKDAYS[RESET_WEEKDAY].title()} {RESET_HOUR:02d}:00 (local time), matching the allowance reset. Generated by `collect.py`; do not edit._", "",
             "| Week of | Messages | Input | Output | Cache write | Cache read | Total | Est. cost |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for wk in sorted(weekly, reverse=True):
        m = weekly[wk]
        lines.append(f"| {wk} | {m['messages']:,} | {fmt(m['input'])} | {fmt(m['output'])} | "
                     f"{fmt(m['cache_write'])} | {fmt(m['cache_read'])} | **{fmt(total(m))}** | ${m['cost']:,.2f} |")

    for wk in sorted(weekly, reverse=True)[:2]:
        for title, groups in (("model", by_model[wk]), ("project", by_project[wk])):
            lines += ["", f"## Week of {wk} by {title}", "",
                      f"| {title.title()} | Messages | Output | Total | Est. cost |", "|---|---:|---:|---:|---:|"]
            for name, m in sorted(groups.items(), key=lambda kv: -total(kv[1])):
                lines.append(f"| {name} | {m['messages']:,} | {fmt(m['output'])} | {fmt(total(m))} | ${m['cost']:,.2f} |")
    REPORT_MD.write_text("\n".join(lines) + "\n")


def main():
    if not PROJECTS_DIR.is_dir():
        sys.exit(f"No transcripts found at {PROJECTS_DIR}")
    daily = load_daily()
    scanned = scan_transcripts()
    # If the reset day/hour changed, a re-scanned day lands in a different week
    # than its old row. Drop the stale row instead of counting the day twice.
    fresh_days = {k[0:1] + k[2:] for k in scanned}
    for key in [k for k in daily if k[0:1] + k[2:] in fresh_days and k not in scanned]:
        del daily[key]
    for key, fresh in scanned.items():
        old = daily.get(key)
        daily[key] = {m: max(fresh[m], old[m]) for m in METRICS} if old else fresh
    write_csv(DAILY_CSV, KEY + METRICS,
              [list(k) + [v[m] for m in METRICS] for k, v in sorted(daily.items())])
    build_report(daily)
    write_report(daily, REPORT_HTML, week_start(datetime.now().astimezone()),
                 f"{WEEKDAYS[RESET_WEEKDAY].title()[:3]} {RESET_HOUR:02d}:00")
    print(f"{len(daily)} daily rows -> {DATA}: {DAILY_CSV.name}, {WEEKLY_CSV.name}, {REPORT_MD.name}, {REPORT_HTML.name}")


if __name__ == "__main__":
    main()
