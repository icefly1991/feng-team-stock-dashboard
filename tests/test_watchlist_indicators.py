import unittest

import pandas as pd

from scripts.data_pipeline.indicators import build_metrics, build_since_november_metrics


class WatchlistSinceNovemberTests(unittest.TestCase):
    def frame(self, end="20261110"):
        dates = pd.bdate_range(end=pd.Timestamp(end), periods=300)
        frame = pd.DataFrame({"trade_date": dates.strftime("%Y%m%d"),
                              "close": 10.0, "high": 12.0, "low": 8.0})
        frame.loc[frame.index[-1], "close"] = 11.0
        return frame

    def test_exact_november_second_low_instead_of_close_or_period_low(self):
        frame = self.frame()
        frame.loc[frame.trade_date == "20261102", ["close", "low"]] = [10.0, 9.25]
        frame.loc[frame.trade_date == "20261103", "low"] = 7.0
        metrics = build_metrics(frame.iloc[::-1], "20260101")
        self.assertEqual(metrics["since_nov2_date"], "20261102")
        self.assertEqual(metrics["since_nov2_return_pct"], 18.92)
        self.assertEqual(metrics["since_nov2_low"], 9.25)

    def test_before_november_does_not_use_previous_year(self):
        metrics = build_metrics(self.frame("20260917"), "20260101")
        for key in ("since_nov2_return_pct", "since_nov2_low", "since_nov2_date"):
            self.assertIsNone(metrics[key])

    def test_suspension_does_not_substitute_a_later_session(self):
        frame = self.frame()
        frame = frame[frame.trade_date != "20261102"]
        metrics = build_metrics(frame, "20260101")
        self.assertIsNone(metrics["since_nov2_date"])
        self.assertIsNone(metrics["since_nov2_low"])
        self.assertIsNone(metrics["since_nov2_return_pct"])

    def test_each_adjustment_uses_its_own_series(self):
        frame = self.frame()
        other = frame.copy()
        other.loc[other.trade_date == "20261102", ["close", "low"]] = [20.0, 18.5]
        self.assertEqual(build_metrics(frame, "20260101")["since_nov2_return_pct"], 37.5)
        metrics = build_metrics(other, "20260101")
        self.assertEqual(metrics["since_nov2_return_pct"], -40.54)
        self.assertEqual(metrics["since_nov2_low"], 18.5)

    def test_invalid_baseline_is_missing_instead_of_zero_or_later_session(self):
        for value in (0.0, float("nan"), float("inf")):
            with self.subTest(value=value):
                frame = self.frame()
                frame.loc[frame.trade_date == "20261102", ["close", "low"]] = value
                metrics = build_since_november_metrics(frame, "20260101")
                self.assertIsNone(metrics["since_nov2_return_pct"])
                self.assertIsNone(metrics["since_nov2_low"])
                self.assertEqual(metrics["since_nov2_date"], "20261102")


if __name__ == "__main__":
    unittest.main()
