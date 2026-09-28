import unittest

import pandas as pd

from scripts.data_pipeline.active_metrics import activity_metrics, rank_candidates, snapshot_metrics
from scripts.data_pipeline.active_financials import assess_profitability, reports_as_of, ttm, Ineligible
from scripts.generate_active_dashboard import adjusted_history, market_candidates


def bars(closes, start="2025-01-01"):
    dates = pd.bdate_range(start, periods=len(closes)).strftime("%Y%m%d")
    return pd.DataFrame({"trade_date": dates, "open": closes, "close": closes,
                         "high": [v * 1.02 for v in closes], "low": [v * .98 for v in closes],
                         "amount": [100000.] * len(closes), "vol": [100.] * len(closes)})


def financial_frames():
    periods = ["20211231", "20221231", "20231231", "20241231", "20251231", "20250630", "20260630"]
    values = [80, 90, 100, 110, 120, 50, 70]
    reports = [{"end_date": p, "ann_date": f"{int(p[:4])+1}0331" if p.endswith("1231") else p[:4]+"0820",
                "f_ann_date": None, "report_type": "1", "n_income_attr_p": v, "update_flag": "0"}
               for p, v in zip(periods, values)]
    income = pd.DataFrame(reports)
    quality = pd.DataFrame([{**r, "profit_dedt": r["n_income_attr_p"] * .8} for r in reports])
    return income, quality


class ActivityTests(unittest.TestCase):
    def test_new_listing_has_activity_but_not_fake_52week_metrics(self):
        f = bars([10.] * 123)
        self.assertIsNotNone(activity_metrics(f)["avg_range_120d_pct"])
        self.assertIsNone(snapshot_metrics(f)["position_52w_pct"])
        self.assertIsNone(snapshot_metrics(f)["distance_ma250_pct"])

    def test_normalization_and_units(self):
        a = activity_metrics(bars([10.] * 121))
        b = activity_metrics(bars([1000.] * 121))
        self.assertAlmostEqual(a["avg_range_60d_pct"], 4)
        self.assertAlmostEqual(a["avg_range_60d_pct"], b["avg_range_60d_pct"])
        self.assertEqual(a["avg_amount_60d_yi"], 1)

    def test_gap_included(self):
        f = bars([100.] * 61)
        f.loc[60, ["open", "close", "high", "low"]] = [120, 120, 122, 119]
        self.assertAlmostEqual(activity_metrics(f)["avg_range_60d_pct"], (59 * 4 + 22) / 60)

    def test_missing_history_is_not_zero(self):
        self.assertIsNone(activity_metrics(bars([10.] * 60))["avg_range_60d_pct"])
        self.assertIsNone(activity_metrics(bars([10.] * 120))["avg_range_120d_pct"])

    def test_split_adjustment(self):
        f = bars([100.] * 60 + [50.] * 61)
        f["adj_factor"] = [1.] * 60 + [2.] * 61
        self.assertAlmostEqual(activity_metrics(adjusted_history(f))["avg_range_120d_pct"], 4)

    def test_invalid_price_and_duplicate_rejected(self):
        f = bars([10.] * 121)
        f.loc[5, "high"] = 5
        with self.assertRaises(ValueError): activity_metrics(f)
        with self.assertRaises(ValueError): activity_metrics(pd.concat([bars([10.] * 121), bars([10.])]))

    def test_missing_amount_not_zero(self):
        f = bars([10.] * 121)
        f.loc[120, "amount"] = float("nan")
        self.assertIsNone(activity_metrics(f)["avg_amount_60d_yi"])

    def test_uses_latest_window_not_full_history(self):
        f = bars([10.] * 200)
        f.loc[:139, "high"] = 12
        self.assertAlmostEqual(activity_metrics(f)["avg_range_60d_pct"], 4)

    def test_size_only_small_weight(self):
        common = {"avg_range_60d_pct": 4, "avg_range_120d_pct": 4, "large_move_60d_pct": 10}
        rows = [{**common, "code": "000001", "total_market_cap_yi": 10},
                {**common, "code": "000002", "total_market_cap_yi": 100}]
        self.assertEqual(rank_candidates(rows)[0]["code"], "000001")
        rows[1].update(avg_range_60d_pct=8, avg_range_120d_pct=8)
        self.assertEqual(rank_candidates(rows)[0]["code"], "000002")


class FinancialTests(unittest.TestCase):
    def test_ttm_components_and_five_years(self):
        result = assess_profitability(*financial_frames(), "20260927")
        self.assertEqual(result["ttm_net_profit"], 140)
        self.assertAlmostEqual(result["ttm_recurring_profit"], 112)
        self.assertTrue(result["five_year_profitable"])
        self.assertEqual([r["period"] for r in result["annual_reports"]], ["20231231", "20241231", "20251231"])

    def test_loss_year_no_backtracking(self):
        income, quality = financial_frames()
        income.loc[income.end_date == "20251231", "n_income_attr_p"] = -1
        with self.assertRaises(Ineligible): assess_profitability(income, quality, "20260927")

    def test_missing_annual_no_skipping(self):
        income, quality = financial_frames()
        with self.assertRaises(Ineligible): assess_profitability(income[income.end_date != "20241231"], quality, "20260927")

    def test_nonrecurring_profit_not_accepted(self):
        income, quality = financial_frames()
        quality.loc[quality.end_date == "20241231", "profit_dedt"] = 0
        with self.assertRaises(Ineligible): assess_profitability(income, quality, "20260927")

    def test_latest_ttm_loss(self):
        income, quality = financial_frames()
        income.loc[income.end_date == "20260630", "n_income_attr_p"] = -200
        with self.assertRaises(Ineligible): assess_profitability(income, quality, "20260927")

    def test_future_revision_excluded(self):
        income, quality = financial_frames()
        revision = {**income[income.end_date == "20251231"].iloc[0].to_dict(), "ann_date": "20261001", "n_income_attr_p": -500}
        amended = pd.concat([income, pd.DataFrame([revision])])
        self.assertEqual(assess_profitability(amended, quality, "20260927")["ttm_net_profit"], 140)
        with self.assertRaises(Ineligible): assess_profitability(amended, quality, "20261002")

    def test_actual_announcement_and_consolidated(self):
        income, _ = financial_frames()
        row = {**income.iloc[-1].to_dict(), "f_ann_date": "20261001", "n_income_attr_p": -1}
        extra = {**row, "f_ann_date": None, "report_type": "2"}
        result = reports_as_of(pd.concat([income, pd.DataFrame([row, extra])]), "20260927")
        self.assertEqual(result["20260630"]["n_income_attr_p"], 70)

    def test_stale_latest_and_missing_ttm_period(self):
        income, quality = financial_frames()
        with self.assertRaises(Ineligible): assess_profitability(income[income.end_date != "20260630"], quality, "20260927")
        with self.assertRaises(Ineligible): assess_profitability(income[income.end_date != "20250630"], quality, "20260927")

    def test_annual_ttm_uses_annual_only(self):
        self.assertEqual(ttm({"20251231": {"profit": 50}}, "20251231", "profit"), 50)


class MarketScreenTests(unittest.TestCase):
    def screen(self, name="正常公司", code="000001.SZ", cap=100000, missing=False, amount=100000):
        basic = pd.DataFrame([{"ts_code": code, "symbol": code[:6], "name": name,
                               "market": "主板", "industry": "机械"}])
        market = pd.DataFrame([{"ts_code": code, "total_mv": cap}])
        raw = bars([10.] * 121)
        raw["ts_code"], raw["adj_factor"], raw["amount"] = code, 1., amount
        dates = raw.trade_date.tolist()
        if missing:
            raw = raw.iloc[1:]
        return market_candidates(basic, market, raw, dates)[0]

    def test_st_and_b_shares_not_selected(self):
        self.assertFalse(self.screen(name="*ST测试"))
        self.assertFalse(self.screen(code="900001.SH"))
        self.assertFalse(self.screen(code="200001.SZ"))
        self.assertEqual(len(self.screen()), 1)

    def test_zero_and_nonfinite_marketcap_not_selected(self):
        for value in (0, -1, float("nan"), float("inf")):
            self.assertFalse(self.screen(cap=value))

    def test_missing_session_not_selected(self):
        self.assertFalse(self.screen(missing=True))

    def test_liquidity_threshold_units(self):
        self.assertEqual(len(self.screen(amount=50000)), 1)
        self.assertFalse(self.screen(amount=49999))


if __name__ == '__main__':
    unittest.main()
