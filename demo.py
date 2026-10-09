#!/usr/bin/env python3
"""Generate a synthetic example report in examples/ (no real usage data).

    python3 demo.py

Writes examples/daily.csv, weekly.csv, WEEKLY.md and report.html from seeded
random numbers, using the same code path as collect.py. Safe to commit; used
for the README screenshot.
"""

import os
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parent / "examples"
# Must be set before importing collect, which reads it at import time.
os.environ["CLAUDE_USAGE_DATA_DIR"] = str(EXAMPLES)
os.environ["CLAUDE_USAGE_RESET_DAY"] = "thu"
os.environ["CLAUDE_USAGE_RESET_HOUR"] = "15"

import collect  # noqa: E402
from report import write_report  # noqa: E402

LAST_DAY = date(2026, 10, 8)  # fixed so the example is reproducible
WEEKS = 12
PROJECTS = {  # name -> (base share of activity, weekly drift)
    "web-app": (1.0, 0.00),
    "data-pipeline": (0.7, 0.03),
    "docs-site": (0.35, -0.01),
    "mobile-client": (0.25, 0.04),
    "infra-scripts": (0.15, 0.00),
}
MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"]


def model_mix(progress):
    """Usage shifts from Opus toward Sonnet over the period."""
    opus = 0.55 - 0.30 * progress
    haiku = 0.08
    return [opus, 1 - opus - haiku, haiku]


def generate(rng):
    rows = {}
    first = LAST_DAY - timedelta(days=WEEKS * 7 - 1)
    for i in range((LAST_DAY - first).days + 1):
        day = first + timedelta(days=i)
        progress = i / ((LAST_DAY - first).days)
        if day.weekday() >= 5 and rng.random() < 0.8:
            continue  # mostly weekdays
        intensity = rng.uniform(0.3, 1.6) * (1 + 0.5 * progress)
        week_ts = datetime.combine(day, time(12)).astimezone()
        week = collect.week_start(week_ts)
        for project, (share, drift) in PROJECTS.items():
            weight = max(share + drift * (i / 7), 0.02)
            if rng.random() > min(0.35 + weight, 0.95):
                continue
            for model, mshare in zip(MODELS, model_mix(progress)):
                msgs = int(rng.gauss(60, 15) * weight * intensity * mshare * 3)
                if msgs < 1:
                    continue
                cw = int(msgs * rng.uniform(6e3, 11e3))
                rows[(day.isoformat(), week, project, model)] = {
                    "messages": msgs,
                    "input": int(msgs * rng.uniform(5, 60)),
                    "output": int(msgs * rng.uniform(600, 1500)),
                    "cache_write": cw,
                    "cache_write_1h": int(cw * rng.uniform(0.3, 0.9)) if model != MODELS[2] else 0,
                    "cache_read": int(msgs * rng.uniform(1.5e5, 3.5e5)),
                }
    return rows


def main():
    daily = generate(random.Random(2026))
    collect.write_csv(collect.DAILY_CSV, collect.KEY + collect.METRICS,
                      [list(k) + [v[m] for m in collect.METRICS] for k, v in sorted(daily.items())])
    collect.build_report(daily)
    write_report(daily, collect.REPORT_HTML, collect.week_start(
        datetime.combine(LAST_DAY, time(12)).astimezone()), "Thu 15:00")
    print(f"{len(daily)} synthetic daily rows -> {EXAMPLES}")


if __name__ == "__main__":
    main()
