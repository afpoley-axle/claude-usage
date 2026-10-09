#!/usr/bin/env python3
"""Print a short Slack-formatted summary of the last completed allowance week.

    python3 summary.py                  # last completed week, from the data folder
    python3 summary.py --no-projects    # omit project names
    python3 summary.py --link URL       # append a report link

Reads daily.csv from CLAUDE_USAGE_DATA_DIR (default ./data). Prints text only;
it never sends anything. Delivery rules are in docs/SLACK.md: the message may
only ever go to your own Slack DM.
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime

from collect import KEY, METRICS, WEEKDAYS, RESET_HOUR, RESET_WEEKDAY, load_daily, week_start
from report import cost, total


def fmt(n):
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= size:
            return f"{n / size:.1f}{unit}"
    return str(int(n))


def week_totals(daily):
    weeks = defaultdict(lambda: {"projects": defaultdict(lambda: dict.fromkeys(METRICS + ["cost"], 0)),
                                 "all": dict.fromkeys(METRICS + ["cost"], 0)})
    for (_, wk, project, model), m in daily.items():
        m = dict(m, cost=cost(model, m))
        for k, v in m.items():
            weeks[wk]["all"][k] += v
            weeks[wk]["projects"][project][k] += v
    return weeks


def build(daily, now, show_projects=True, link=None):
    weeks = week_totals(daily)
    current = week_start(now)
    done = sorted(w for w in weeks if w < current)
    if not done:
        return None
    wk = done[-1]
    t = weeks[wk]["all"]
    lines = [f"*Claude Code usage, week of {wk}*",
             f"• Total tokens: {fmt(total(t))} (output {fmt(t['output'])}) across {t['messages']:,} messages",
             f"• Estimated cost: ${t['cost']:,.2f} (API list-price equivalent, not what your plan bills)"]
    prev = done[-2] if len(done) > 1 else None
    if prev and total(weeks[prev]["all"]):
        change = (total(t) / total(weeks[prev]["all"]) - 1) * 100
        lines.append(f"• vs week of {prev}: {change:+.0f}% tokens")
    if show_projects:
        top = sorted(weeks[wk]["projects"].items(), key=lambda kv: -total(kv[1]))[:3]
        lines.append("• Top projects:")
        lines += [f"    {name}: {fmt(total(m))} tokens, ${m['cost']:,.2f}" for name, m in top]
    if link:
        lines.append(f"Report: {link}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-projects", action="store_true", help="omit project names")
    ap.add_argument("--link", default=os.environ.get("CLAUDE_USAGE_REPORT_URL"), help="report URL to append")
    ap.add_argument("--now", help="ISO local time to treat as now (for testing)")
    args = ap.parse_args()
    now = datetime.fromisoformat(args.now).astimezone() if args.now else datetime.now().astimezone()
    text = build(load_daily(), now, not args.no_projects, args.link)
    if text is None:
        sys.exit("No completed allowance week in the data yet.")
    print(text)


if __name__ == "__main__":
    main()
