import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import collect
import summary

EDT = timezone(timedelta(hours=-4))


def row(**kw):
    base = dict.fromkeys(collect.METRICS, 0)
    base.update(kw)
    return base


class BuildTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.multiple(collect, RESET_WEEKDAY=3, RESET_HOUR=15)
        patcher.start()
        self.addCleanup(patcher.stop)
        m = "claude-sonnet-5-5"
        self.daily = {
            ("2026-09-25", "2026-09-24", "alpha", m): row(messages=10, output=1000, cache_read=9_000_000),
            ("2026-10-02", "2026-10-01", "alpha", m): row(messages=20, output=2000, cache_read=15_000_000),
            ("2026-10-02", "2026-10-01", "beta", m): row(messages=5, output=500, cache_read=5_000_000),
            ("2026-10-02", "2026-10-01", "gamma", m): row(messages=1, output=10, cache_read=1_000),
            ("2026-10-02", "2026-10-01", "delta", m): row(messages=1, output=10, cache_read=500),
            ("2026-10-09", "2026-10-08", "alpha", m): row(messages=3, output=300, cache_read=1_000_000),
        }

    def now(self, day, hh, mm):
        return datetime(2026, 10, day, hh, mm, tzinfo=EDT)

    def test_reports_last_completed_week_after_reset(self):
        text = summary.build(self.daily, self.now(8, 15, 5))
        self.assertIn("week of 2026-10-01", text)
        self.assertIn("27 messages", text)

    def test_before_reset_reports_previous_week(self):
        # 14:58 Thursday is still the 10-01 week, so the last *completed* one is 09-24.
        text = summary.build(self.daily, self.now(8, 14, 58))
        self.assertIn("week of 2026-09-24", text)

    def test_in_progress_week_is_never_reported(self):
        text = summary.build(self.daily, self.now(9, 12, 0))  # Friday, week 10-08 in progress
        self.assertIn("week of 2026-10-01", text)
        self.assertNotIn("week of 2026-10-08", text)

    def test_change_vs_previous_week(self):
        text = summary.build(self.daily, self.now(8, 15, 5))
        self.assertIn("vs week of 2026-09-24: +", text)

    def test_top_three_projects_by_tokens(self):
        text = summary.build(self.daily, self.now(8, 15, 5))
        self.assertIn("alpha", text)
        self.assertIn("beta", text)
        self.assertIn("gamma", text)
        self.assertNotIn("delta", text)  # 4th place is cut

    def test_no_projects_flag_hides_names(self):
        text = summary.build(self.daily, self.now(8, 15, 5), show_projects=False)
        for name in ("alpha", "beta", "gamma", "Top projects"):
            self.assertNotIn(name, text)

    def test_link_is_appended(self):
        text = summary.build(self.daily, self.now(8, 15, 5), link="https://example.com/r")
        self.assertTrue(text.endswith("Report: https://example.com/r"))

    def test_none_without_a_completed_week(self):
        only_current = {k: v for k, v in self.daily.items() if k[1] == "2026-10-08"}
        self.assertIsNone(summary.build(only_current, self.now(9, 12, 0)))
        self.assertIsNone(summary.build({}, self.now(9, 12, 0)))

    def test_single_completed_week_has_no_change_line(self):
        one = {k: v for k, v in self.daily.items() if k[1] == "2026-10-01"}
        self.assertNotIn("vs week of", summary.build(one, self.now(8, 15, 5)))


class FmtTest(unittest.TestCase):
    def test_units(self):
        self.assertEqual(summary.fmt(999), "999")
        self.assertEqual(summary.fmt(1500), "1.5K")
        self.assertEqual(summary.fmt(2_500_000), "2.5M")
        self.assertEqual(summary.fmt(3_100_000_000), "3.1B")


if __name__ == "__main__":
    unittest.main()
