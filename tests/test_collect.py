import csv
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import collect

EDT = timezone(timedelta(hours=-4))


def at(y, m, d, hh=12, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=EDT)


class WeekStartTest(unittest.TestCase):
    """Default reset: Thursday 15:00. 2026-10-08 is a Thursday."""

    def setUp(self):
        patcher = mock.patch.multiple(collect, RESET_WEEKDAY=3, RESET_HOUR=15)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_just_before_reset_is_previous_week(self):
        self.assertEqual(collect.week_start(at(2026, 10, 8, 14, 59)), "2026-10-01")

    def test_at_reset_starts_new_week(self):
        self.assertEqual(collect.week_start(at(2026, 10, 8, 15, 0)), "2026-10-08")

    def test_rest_of_week(self):
        for day in (9, 10, 11, 12, 13, 14):  # Fri .. Wed
            self.assertEqual(collect.week_start(at(2026, 10, day)), "2026-10-08", day)

    def test_next_reset_boundary(self):
        self.assertEqual(collect.week_start(at(2026, 10, 15, 14, 59)), "2026-10-08")
        self.assertEqual(collect.week_start(at(2026, 10, 15, 15, 0)), "2026-10-15")

    def test_month_and_year_rollover(self):
        # Thursday 2026-12-31 15:00 starts a week; Jan 2 belongs to it.
        self.assertEqual(collect.week_start(at(2027, 1, 2)), "2026-12-31")

    def test_dst_change_week(self):
        # US DST ends 2026-11-01 (a Sunday). Fixed-offset datetimes on each side
        # of the change must still land in the Thursday 2026-10-29 week.
        edt = datetime(2026, 11, 1, 0, 30, tzinfo=timezone(timedelta(hours=-4)))
        est = datetime(2026, 11, 1, 3, 0, tzinfo=timezone(timedelta(hours=-5)))
        self.assertEqual(collect.week_start(edt), "2026-10-29")
        self.assertEqual(collect.week_start(est), "2026-10-29")

    def test_custom_reset(self):
        with mock.patch.multiple(collect, RESET_WEEKDAY=0, RESET_HOUR=9):  # Monday 09:00
            self.assertEqual(collect.week_start(at(2026, 10, 12, 8, 59)), "2026-10-05")
            self.assertEqual(collect.week_start(at(2026, 10, 12, 9, 0)), "2026-10-12")

    def test_midnight_reset(self):
        with mock.patch.multiple(collect, RESET_WEEKDAY=6, RESET_HOUR=0):  # Sunday 00:00
            self.assertEqual(collect.week_start(at(2026, 10, 11, 0, 0)), "2026-10-11")
            self.assertEqual(collect.week_start(at(2026, 10, 10, 23, 59)), "2026-10-04")


class ResetScheduleTest(unittest.TestCase):
    def run_with(self, **env):
        with mock.patch.dict(os.environ, env, clear=False):
            for k in ("CLAUDE_USAGE_RESET_DAY", "CLAUDE_USAGE_RESET_HOUR"):
                if k not in env:
                    os.environ.pop(k, None)
            return collect.reset_schedule()

    def test_default_is_thursday_15(self):
        self.assertEqual(self.run_with(), (3, 15))

    def test_custom_values_and_case(self):
        self.assertEqual(self.run_with(CLAUDE_USAGE_RESET_DAY="Monday", CLAUDE_USAGE_RESET_HOUR="9"), (0, 9))
        self.assertEqual(self.run_with(CLAUDE_USAGE_RESET_DAY="SUN", CLAUDE_USAGE_RESET_HOUR="0"), (6, 0))

    def test_bad_values_exit(self):
        for env in ({"CLAUDE_USAGE_RESET_DAY": "xyz"}, {"CLAUDE_USAGE_RESET_HOUR": "24"},
                    {"CLAUDE_USAGE_RESET_HOUR": "-1"}, {"CLAUDE_USAGE_RESET_HOUR": "noon"}):
            with self.assertRaises(SystemExit, msg=env):
                self.run_with(**env)


class WeeklyBudgetTest(unittest.TestCase):
    def run_with(self, value):
        env = {} if value is None else {"CLAUDE_USAGE_WEEKLY_BUDGET": value}
        with mock.patch.dict(os.environ, env, clear=False):
            if value is None:
                os.environ.pop("CLAUDE_USAGE_WEEKLY_BUDGET", None)
            return collect.weekly_budget()

    def test_unset_or_blank_is_none(self):
        self.assertIsNone(self.run_with(None))
        self.assertIsNone(self.run_with("  "))

    def test_accepts_numbers_and_dollar_sign(self):
        self.assertEqual(self.run_with("150"), 150.0)
        self.assertEqual(self.run_with("$99.5"), 99.5)

    def test_rejects_bad_values(self):
        for bad in ("abc", "0", "-5"):
            with self.assertRaises(SystemExit, msg=bad):
                self.run_with(bad)


class MergeDailyTest(unittest.TestCase):
    def row(self, **kw):
        base = dict.fromkeys(collect.METRICS, 0)
        base.update(kw)
        return base

    def test_takes_max_per_counter(self):
        key = ("2026-10-08", "2026-10-08", "proj", "claude-sonnet-5-5")
        old = {key: self.row(messages=10, output=500, cache_read=100)}
        fresh = {key: self.row(messages=7, output=900, cache_read=50)}
        merged = collect.merge_daily(old, fresh)[key]
        self.assertEqual((merged["messages"], merged["output"], merged["cache_read"]), (10, 900, 100))

    def test_keeps_rows_for_pruned_days(self):
        old_key = ("2026-08-01", "2026-07-30", "proj", "m")
        new_key = ("2026-10-08", "2026-10-08", "proj", "m")
        old = {old_key: self.row(messages=5)}
        merged = collect.merge_daily(old, {new_key: self.row(messages=1)})
        self.assertEqual(set(merged), {old_key, new_key})
        self.assertEqual(merged[old_key]["messages"], 5)

    def test_does_not_mutate_input(self):
        key = ("2026-10-08", "2026-10-08", "p", "m")
        old = {key: self.row(messages=1)}
        collect.merge_daily(old, {key: self.row(messages=2)})
        self.assertEqual(old[key]["messages"], 1)

    def test_reset_change_replaces_stale_week_row(self):
        stale = ("2026-10-08", "2026-10-01", "p", "m")
        fresh = ("2026-10-08", "2026-10-05", "p", "m")  # same day, different week bucket
        merged = collect.merge_daily({stale: self.row(messages=3)}, {fresh: self.row(messages=3)})
        self.assertEqual(list(merged), [fresh])

    def test_day_straddling_reset_keeps_both_halves(self):
        before = ("2026-10-08", "2026-10-01", "p", "m")
        after = ("2026-10-08", "2026-10-08", "p", "m")
        old = {before: self.row(messages=2), after: self.row(messages=4)}
        merged = collect.merge_daily(old, {before: self.row(messages=2), after: self.row(messages=4)})
        self.assertEqual(set(merged), {before, after})


class CsvRoundTripTest(unittest.TestCase):
    def test_write_then_load(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "sub" / "daily.csv"  # parent dir is created
            key = ("2026-10-08", "2026-10-08", "proj", "claude-sonnet-5-5")
            vals = dict(zip(collect.METRICS, range(1, 7)))
            collect.write_csv(path, collect.KEY + collect.METRICS, [list(key) + [vals[m] for m in collect.METRICS]])
            with mock.patch.object(collect, "DAILY_CSV", path):
                self.assertEqual(collect.load_daily(), {key: vals})

    def test_load_missing_file_is_empty(self):
        with mock.patch.object(collect, "DAILY_CSV", Path("/nonexistent/daily.csv")):
            self.assertEqual(collect.load_daily(), {})


class ProjectNameTest(unittest.TestCase):
    def test_uses_last_path_component(self):
        self.assertEqual(collect.project_name("/Users/me/code/my-app", "fallback"), "my-app")

    def test_worktree_collapses_to_repo(self):
        self.assertEqual(collect.project_name("/Users/me/code/my-app/.claude/worktrees/feat-1", "x"), "my-app")

    def test_fallback_when_no_cwd(self):
        self.assertEqual(collect.project_name(None, "-Users-me-code-app"), "-Users-me-code-app")


class ScanTranscriptsTest(unittest.TestCase):
    def setUp(self):
        self._tz = os.environ.get("TZ")
        os.environ["TZ"] = "UTC"
        time.tzset()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.restore_tz)
        patcher = mock.patch.object(collect, "PROJECTS_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.multiple(collect, RESET_WEEKDAY=3, RESET_HOUR=15)
        patcher.start()
        self.addCleanup(patcher.stop)

    def restore_tz(self):
        if self._tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._tz
        time.tzset()

    def write(self, name, records, raw=()):
        d = Path(self.tmp.name) / "-proj-dir"
        d.mkdir(exist_ok=True)
        lines = [json.dumps(r) for r in records] + list(raw)
        (d / name).write_text("\n".join(lines) + "\n")

    def rec(self, mid="m1", rid="r1", ts="2026-10-08T16:00:00Z", model="claude-sonnet-5-5",
            cwd="/Users/me/code/app", **usage):
        u = {"input_tokens": 1, "output_tokens": 10, "cache_creation_input_tokens": 100,
             "cache_read_input_tokens": 1000}
        u.update(usage)
        return {"timestamp": ts, "cwd": cwd, "requestId": rid,
                "message": {"id": mid, "model": model, "usage": u}}

    def test_aggregates_by_day_project_model(self):
        self.write("a.jsonl", [self.rec("m1", "r1"), self.rec("m2", "r2")])
        totals = collect.scan_transcripts()
        key = ("2026-10-08", "2026-10-08", "app", "claude-sonnet-5-5")
        self.assertEqual(list(totals), [key])
        row = totals[key]
        self.assertEqual((row["messages"], row["input"], row["output"], row["cache_write"], row["cache_read"]),
                         (2, 2, 20, 200, 2000))

    def test_streamed_duplicates_count_once_with_max_usage(self):
        self.write("a.jsonl", [self.rec("m1", "r1", output_tokens=5),
                               self.rec("m1", "r1", output_tokens=40),
                               self.rec("m1", "r1", output_tokens=20)])
        row = next(iter(collect.scan_transcripts().values()))
        self.assertEqual((row["messages"], row["output"]), (1, 40))

    def test_same_message_in_two_files_counts_once(self):
        self.write("a.jsonl", [self.rec("m1", "r1")])
        self.write("b.jsonl", [self.rec("m1", "r1")])
        self.assertEqual(next(iter(collect.scan_transcripts().values()))["messages"], 1)

    def test_skips_synthetic_missing_timestamp_and_bad_lines(self):
        bad_ts = self.rec("m3", "r3")
        del bad_ts["timestamp"]
        self.write("a.jsonl", [self.rec("m1", "r1", model="<synthetic>"), bad_ts, self.rec("m2", "r2")],
                   raw=["{not json", '{"usage": "mentioned but not a record"}'])
        totals = collect.scan_transcripts()
        self.assertEqual(sum(r["messages"] for r in totals.values()), 1)

    def test_one_hour_cache_write_split(self):
        self.write("a.jsonl", [self.rec(cache_creation={"ephemeral_1h_input_tokens": 60})])
        row = next(iter(collect.scan_transcripts().values()))
        self.assertEqual((row["cache_write"], row["cache_write_1h"]), (100, 60))

    def test_null_usage_fields_are_zero(self):
        self.write("a.jsonl", [self.rec(input_tokens=None, cache_read_input_tokens=None)])
        row = next(iter(collect.scan_transcripts().values()))
        self.assertEqual((row["input"], row["cache_read"]), (0, 0))

    def test_worktree_usage_attributed_to_main_project(self):
        self.write("a.jsonl", [self.rec(cwd="/Users/me/code/app/.claude/worktrees/feat")])
        self.assertEqual(next(iter(collect.scan_transcripts()))[2], "app")

    def test_fallback_project_name_from_directory(self):
        self.write("a.jsonl", [self.rec(cwd=None)])
        self.assertEqual(next(iter(collect.scan_transcripts()))[2], "-proj-dir")

    def test_week_bucket_around_reset(self):
        self.write("a.jsonl", [self.rec("m1", "r1", ts="2026-10-08T14:59:00Z"),
                               self.rec("m2", "r2", ts="2026-10-08T15:00:00Z")])
        weeks = sorted(k[1] for k in collect.scan_transcripts())
        self.assertEqual(weeks, ["2026-10-01", "2026-10-08"])


if __name__ == "__main__":
    unittest.main()
