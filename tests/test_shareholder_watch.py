import unittest

import pandas as pd

from scripts.generate_shareholder_watch import build_stock, normalized_name


def report(period, announcement, names):
    return [{"end_date": period, "ann_date": announcement, "holder_name": name,
             "hold_amount": 1000 + index, "hold_float_ratio": 0.5} for index, name in enumerate(names)]


class ShareholderTests(unittest.TestCase):
    def setUp(self):
        self.names = {"A", "B", "C"}
        self.old = report("20260331", "20260420", ["A", "B"] + [f"old{i}" for i in range(8)])
        self.new = report("20260630", "20260820", ["B", "C"] + [f"new{i}" for i in range(8)])

    def build(self, rows):
        return build_stock(pd.DataFrame(rows), self.names, "20260918")

    def test_new_exit_continuing_and_ratios(self):
        result = self.build(self.old + self.new)
        self.assertEqual({m["name"]: m["state"] for m in result["matches"]}, {"A": "exit", "B": "continuing", "C": "new"})
        self.assertEqual(result["matches"][2]["current"]["float_ratio_pct"], 0.5)

    def test_missing_and_partial_previous_not_new(self):
        for rows in [self.new, self.old[:2] + self.new]:
            matches = self.build(rows)["matches"]
            self.assertEqual(next(m for m in matches if m["name"] == "C")["state"], "unknown")

    def test_partial_current_does_not_claim_exit_or_fallback(self):
        result = self.build(self.old + self.new[:2])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["current"]["period"], "20260630")
        self.assertNotIn("A", [m["name"] for m in result["matches"]])

    def test_extra_holder_does_not_prove_completeness(self):
        rows = self.old + self.new + report("20260630", "20260820", ["extra"])
        result = self.build(rows)
        self.assertEqual(result["status"], "partial")
        self.assertNotIn("A", [m["name"] for m in result["matches"]])

    def test_future_disclosure_and_late_old_revision(self):
        rows = self.old + self.new + report("20260930", "20261020", ["A"])
        rows += report("20260331", "20260901", ["A", "B"] + [f"rev{i}" for i in range(8)])
        result = self.build(rows)
        self.assertEqual(result["current"]["period"], "20260630")
        self.assertEqual(result["previous"]["ann_date"], "20260901")

    def test_revision_is_whole_snapshot_not_union(self):
        result = self.build(self.old + self.new + report("20260630", "20260901", ["B"]))
        self.assertEqual(len(result["current"]["holders"]), 1)
        self.assertNotIn("C", [m["name"] for m in result["matches"]])

    def test_duplicates_conflicts_and_invalid_shares(self):
        self.assertTrue(self.build(self.new + self.new)["current"]["complete"])
        for amount in [100, float("nan"), -1]:
            with self.assertRaises(ValueError):
                self.build(self.new + [{**self.new[0], "hold_amount": amount}])

    def test_exact_name_and_missing_data(self):
        result = self.build(report("20260630", "20260820", ["AB", "B investment", "C fund"]))
        self.assertEqual(result["matches"], [])
        self.assertEqual(normalized_name(" Ａ "), "A")
        self.assertEqual(self.build([])["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
