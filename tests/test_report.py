import unittest

import report

ZERO = dict(input=0, output=0, cache_write=0, cache_write_1h=0, cache_read=0, messages=0)


def usage(**kw):
    return dict(ZERO, **kw)


class PriceLookupTest(unittest.TestCase):
    def test_exact_and_dated_ids(self):
        self.assertEqual(report.price_for("claude-haiku-4-5"), report.PRICES["claude-haiku-4-5"])
        self.assertEqual(report.price_for("claude-haiku-4-5-20251001"), report.PRICES["claude-haiku-4-5"])

    def test_longest_prefix_wins(self):
        self.assertEqual(report.price_for("claude-opus-5-5"), report.PRICES["claude-opus-5-5"])
        self.assertEqual(report.price_for("claude-opus-5"), report.PRICES["claude-opus-5"])
        self.assertNotEqual(report.PRICES["claude-opus-5-5"], report.PRICES["claude-opus-5"])

    def test_no_partial_word_match(self):
        self.assertIsNone(report.price_for("claude-opus-50"))

    def test_unknown_model(self):
        self.assertIsNone(report.price_for("some-other-model"))
        self.assertIsNone(report.price_for("unknown"))


class CostTest(unittest.TestCase):
    def setUp(self):
        self._saved = dict(report.PRICES)
        report.PRICES.clear()
        report.PRICES["test-model"] = (10.0, 50.0, 1.0)  # input, output, cache read per million
        self.addCleanup(lambda: (report.PRICES.clear(), report.PRICES.update(self._saved)))

    def test_each_component(self):
        self.assertAlmostEqual(report.cost("test-model", usage(input=1_000_000)), 10.0)
        self.assertAlmostEqual(report.cost("test-model", usage(output=1_000_000)), 50.0)
        self.assertAlmostEqual(report.cost("test-model", usage(cache_read=1_000_000)), 1.0)

    def test_cache_write_5m_is_1_25x_input(self):
        self.assertAlmostEqual(report.cost("test-model", usage(cache_write=1_000_000)), 12.5)

    def test_cache_write_1h_is_2x_input(self):
        self.assertAlmostEqual(report.cost("test-model", usage(cache_write=1_000_000, cache_write_1h=1_000_000)), 20.0)

    def test_cache_write_mixed_ttl(self):
        # 400k at 5m (1.25x) + 600k at 1h (2x) = 400k*12.5/M + 600k*20/M = 5 + 12
        self.assertAlmostEqual(report.cost("test-model", usage(cache_write=1_000_000, cache_write_1h=600_000)), 17.0)

    def test_unpriced_model_costs_zero(self):
        self.assertEqual(report.cost("mystery", usage(input=10**9, output=10**9)), 0.0)

    def test_total_excludes_messages_and_1h_subset(self):
        self.assertEqual(report.total(usage(input=1, output=2, cache_write=3, cache_write_1h=3, cache_read=4, messages=99)), 10)


if __name__ == "__main__":
    unittest.main()


class WriteReportTest(unittest.TestCase):
    """The HTML embeds its data as JSON; check the per-day data the burn-down chart reads."""

    def render(self, daily, **kw):
        import json
        import re
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "report.html"
            report.write_report(daily, path, "2026-10-08", **kw)
            return json.loads(re.search(r"const D = (\{.*\});\n", path.read_text()).group(1))

    def daily(self):
        row = lambda **kw: {**dict.fromkeys(report.METRICS, 0), **kw}
        m = "claude-sonnet-5-5"
        return {
            ("2026-10-08", "2026-10-08", "a", m): row(messages=2, output=1000),
            ("2026-10-08", "2026-10-01", "b", m): row(messages=1, output=500),  # same date, before the reset
            ("2026-10-09", "2026-10-08", "a", m): row(messages=3, output=2000),
        }

    def test_days_split_by_week_and_sum_to_week_totals(self):
        data = self.render(self.daily())
        week = next(w for w in data["weeks"] if w["week"] == "2026-10-08")
        self.assertEqual(sorted(week["days"]), ["2026-10-08", "2026-10-09"])
        self.assertEqual(week["days"]["2026-10-08"]["messages"], 2)
        self.assertEqual(sum(d["output"] for d in week["days"].values()),
                         sum(m["output"] for m in week["models"].values()))
        prev = next(w for w in data["weeks"] if w["week"] == "2026-10-01")
        self.assertEqual(list(prev["days"]), ["2026-10-08"])

    def test_budget_is_passed_through(self):
        self.assertIsNone(self.render(self.daily())["budget"])
        self.assertEqual(self.render(self.daily(), budget=150.0)["budget"], 150.0)
