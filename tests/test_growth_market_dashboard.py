from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from scripts import generate_growth_market_dashboard as growth


def make_pro(market_caps: list[object]) -> Mock:
    codes = [f"300{index:03d}" for index in range(len(market_caps))]
    pro = Mock()
    pro.stock_basic.return_value = pd.DataFrame([
        {"ts_code": f"{code}.SZ", "symbol": code, "name": f"Company {index}",
         "market": "创业板", "list_date": "20200101"}
        for index, code in enumerate(codes)
    ])
    pro.daily_basic.return_value = pd.DataFrame([
        {"ts_code": f"{code}.SZ", "trade_date": "20260915", "close": 10,
         "total_mv": cap, "circ_mv": 50000}
        for code, cap in zip(codes, market_caps)
    ])
    pro.trade_cal.return_value = pd.DataFrame({
        "cal_date": ["20260908", "20260909", "20260910", "20260911", "20260914", "20260915"]
    })
    pro.stock_company.return_value = pd.DataFrame([
        {"ts_code": f"{code}.SZ", "main_business": "Test business"} for code in codes
    ])
    pro.income.return_value = pd.DataFrame([
        {"end_date": f"{year}1231", "ann_date": f"{year + 1}0430",
         "f_ann_date": f"{year + 1}0430", "report_type": "1",
         "n_income_attr_p": 10000000, "update_flag": "1"}
        for year in range(date.today().year - 3, date.today().year)
    ])
    return pro


class TotalMarketCapTests(unittest.TestCase):
    def test_uses_total_market_cap_instead_of_small_circulating_cap(self) -> None:
        pro = make_pro([240000, 300000])
        candidates, universe = growth.load_candidates(pro, "20260915")
        self.assertEqual(universe, 2)
        self.assertEqual([row["symbol"] for row in candidates], ["300000"])
        self.assertEqual(candidates[0]["total_market_cap_yi"], 24)
        self.assertNotIn("circulating_market_cap_yi", candidates[0])
        fields = pro.daily_basic.call_args.kwargs["fields"].split(",")
        self.assertIn("total_mv", fields)
        self.assertNotIn("circ_mv", fields)

    def test_strict_boundary_is_evaluated_before_rounding(self) -> None:
        pro = make_pro([249999.999, 250000, 250000.001])
        candidates, _ = growth.load_candidates(pro, "20260915")
        self.assertEqual([row["symbol"] for row in candidates], ["300000"])
        self.assertAlmostEqual(candidates[0]["total_market_cap_yi"], 24.9999999)
        self.assertLess(candidates[0]["total_market_cap_yi"], 25)

    def test_invalid_total_caps_do_not_fall_back_to_circulating_caps(self) -> None:
        pro = make_pro([None, float("nan"), float("inf"), -float("inf"), 0, -1, "invalid", "120000"])
        candidates, universe = growth.load_candidates(pro, "20260915")
        self.assertEqual(universe, 1)
        self.assertEqual([row["symbol"] for row in candidates], ["300007"])
        self.assertEqual(candidates[0]["total_market_cap_yi"], 12)

    def test_existing_board_st_and_listing_age_filters_remain(self) -> None:
        pro = make_pro([100000] * 7)
        basic = pro.stock_basic.return_value
        basic.loc[0, "name"] = "*ST company"
        basic.loc[1, "name"] = "st company"
        basic.loc[2, "market"] = "主板"
        basic.loc[3, "symbol"] = "600000"
        basic.loc[4, "list_date"] = "20260909"
        basic.loc[5, "list_date"] = "20260908"
        basic.loc[6, ["symbol", "market"]] = ["688001", "科创板"]
        candidates, universe = growth.load_candidates(pro, "20260915")
        self.assertEqual(universe, 2)
        self.assertEqual([row["symbol"] for row in candidates], ["300005", "688001"])

    def test_main_exports_new_schema_and_total_cap_order(self) -> None:
        pro = make_pro([190000, 120000, 120000])
        bars = pd.DataFrame({
            "trade_date": pd.bdate_range(end="2026-09-15", periods=252).strftime("%Y%m%d"),
            "close": 10.0, "high": 12.0, "low": 8.0, "pct_chg": 1.0,
        })
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "growth.json"
            with (
                patch.dict(os.environ, {"TUSHARE_TOKEN": "test-token"}),
                patch.object(growth.ts, "pro_api", return_value=pro),
                patch.object(growth.ts, "pro_bar", return_value=bars) as pro_bar,
                patch.object(growth, "get_latest_trade_date", return_value="20260915"),
                patch.object(growth, "OUTPUT_FILE", output),
                redirect_stdout(io.StringIO()),
            ):
                growth.main()
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["filters"]["total_market_cap_lt_yi"], 25)
        self.assertNotIn("circulating_market_cap_lt_yi", payload["filters"])
        self.assertEqual([row["code"] for row in payload["rows"]], ["300001", "300002", "300000"])
        self.assertEqual(payload["summary"]["displayed_total"], 3)
        self.assertEqual(payload["summary"]["profitable_candidates"], 3)
        self.assertEqual(payload["summary"]["latest_report_candidates"], 3)
        self.assertEqual(len(payload["rows"][0]["annual_periods"]), 3)
        self.assertIn("per stock", payload["filters"]["annual_period_rule"])
        self.assertEqual(payload["rows"][0]["latest_report"]["net_profit"], 10000000)
        self.assertEqual(payload["trade_date"], "20260915")
        self.assertTrue(all(row["position_52w_pct"] == 50 for row in payload["rows"]))
        self.assertTrue(all(row["distance_ma250_pct"] == 0 for row in payload["rows"]))
        self.assertTrue(all(call.kwargs["api"] is pro for call in pro_bar.call_args_list))

    def test_missing_or_nonpositive_annual_profit_excludes_stock(self) -> None:
        for profits in ([-1, 10, 10], [10, 0, 10], [10, 10, None]):
            with self.subTest(profits=profits):
                pro = make_pro([120000])
                pro.income.return_value["n_income_attr_p"] = profits
                with (
                    patch.dict(os.environ, {"TUSHARE_TOKEN": "test-token"}),
                    patch.object(growth.ts, "pro_api", return_value=pro),
                    patch.object(growth.ts, "pro_bar") as pro_bar,
                    patch.object(growth, "get_latest_trade_date", return_value="20260915"),
                    self.assertRaisesRegex(RuntimeError, "profitable: 0"),
                ):
                    growth.main()
                pro_bar.assert_not_called()

    def test_unsuccessful_generation_preserves_previous_file(self) -> None:
        pro = make_pro([300000])
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "growth.json"
            old_data = '{"filters":{"circulating_market_cap_lt_yi":20}}\n'
            output.write_text(old_data, encoding="utf-8")
            with (
                patch.dict(os.environ, {"TUSHARE_TOKEN": "test-token"}),
                patch.object(growth.ts, "pro_api", return_value=pro),
                patch.object(growth, "get_latest_trade_date", return_value="20260915"),
                patch.object(growth, "OUTPUT_FILE", output),
                self.assertRaisesRegex(RuntimeError, "No growth-market rows generated"),
            ):
                growth.main()
            self.assertEqual(output.read_text(encoding="utf-8"), old_data)


class FinancialScreenTests(unittest.TestCase):
    periods = ("20231231", "20241231", "20251231")

    @staticmethod
    def report(period: str, profit: object, announced: str, **kwargs: object) -> dict:
        return {"end_date": period, "n_income_attr_p": profit, "ann_date": announced,
                "f_ann_date": announced, "report_type": "1", "update_flag": "1", **kwargs}

    def setUp(self) -> None:
        self.annual = [self.report(f"{year}1231", 10, f"{year + 1}0430") for year in (2023, 2024, 2025)]

    def load(self, rows: list[dict], as_of: str = "20260916") -> dict | None:
        pro = Mock()
        pro.income.return_value = pd.DataFrame(rows)
        return growth.load_financials(pro, "300001.SZ", as_of)

    def test_cross_year_and_staggered_annual_disclosure(self) -> None:
        future = self.report("20261231", 20, "20270320")
        for cutoff in ("20261231", "20270101", "20270319"):
            self.assertEqual(self.load(self.annual + [future], cutoff)["annual_periods"], list(self.periods))
        first = self.load(self.annual + [future], "20270320")
        second = self.load(self.annual + [{**future, "f_ann_date": "20270420"}], "20270320")
        self.assertEqual(first["annual_periods"], ["20241231", "20251231", "20261231"])
        self.assertEqual(first["annual_ann_dates"]["20261231"], "20270320")
        self.assertEqual(second["annual_periods"], list(self.periods))

    def test_annual_gaps_and_latest_bad_year_never_skipped(self) -> None:
        older = self.report("20221231", 10, "20230420")
        self.assertIsNone(self.load([older, self.annual[0], self.annual[2]]))
        for profit in (None, float("inf")):
            self.assertIsNone(self.load(self.annual + [self.report("20261231", profit, "20270320")], "20270401"))
        for profit in (0, -1):
            result = self.load(self.annual + [self.report("20261231", profit, "20270320")], "20270401")
            self.assertEqual(result["annual_periods"][-1], "20261231")
            self.assertFalse(all(v > 0 for v in result["annual_net_profit"].values()))

    def test_old_annual_revision_does_not_move_anchor(self) -> None:
        result = self.load(self.annual + [self.report("20231231", 5, "20260901", report_type="4")])
        self.assertEqual(result["annual_periods"], list(self.periods))
        self.assertEqual(result["annual_net_profit"]["20231231"], 5)
        self.assertEqual(result["annual_ann_dates"]["20231231"], "20260901")

    def test_main_keeps_independent_windows_during_annual_season(self) -> None:
        pro = make_pro([120000] * 2)
        pro.trade_cal.return_value = pd.DataFrame({"cal_date": pd.bdate_range(end="2027-03-22", periods=6).strftime("%Y%m%d")})
        pro.income.side_effect = [
            pd.DataFrame(self.annual),
            pd.DataFrame(self.annual + [self.report("20261231", 20, "20270320")]),
        ]
        bars = pd.DataFrame({"trade_date": pd.bdate_range(end="2027-03-22", periods=252).strftime("%Y%m%d"),
                             "close": 10.0, "high": 12.0, "low": 8.0, "pct_chg": 1.0})
        now = datetime(2027, 3, 22, 17, tzinfo=growth.BEIJING_TZ)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "growth.json"
            with (patch.dict(os.environ, {"TUSHARE_TOKEN": "test-token"}),
                  patch.object(growth.ts, "pro_api", return_value=pro),
                  patch.object(growth.ts, "pro_bar", return_value=bars),
                  patch.object(growth, "datetime") as clock,
                  patch.object(growth, "get_latest_trade_date", return_value="20270322"),
                  patch.object(growth, "OUTPUT_FILE", output), patch.object(growth.time, "sleep"),
                  redirect_stdout(io.StringIO())):
                clock.now.return_value = now
                growth.main()
            data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["rows"][0]["annual_periods"], list(self.periods))
        self.assertEqual(data["rows"][1]["annual_periods"], ["20241231", "20251231", "20261231"])
        self.assertEqual(data["summary"]["displayed_total"], 2)

    def test_selects_latest_period_not_latest_announcement(self) -> None:
        result = self.load(self.annual + [
            self.report("20260630", 0, "20260820"),
            self.report("20251231", 20, "20260910", report_type="4"),
        ])
        self.assertEqual(result["latest_report"], {"period": "20260630", "ann_date": "20260820", "net_profit": 0})
        self.assertEqual(result["annual_net_profit"]["20251231"], 20)

    def test_negative_missing_or_nonfinite_latest_never_falls_back(self) -> None:
        for value in (-0.001, None, float("nan"), float("inf"), "invalid"):
            with self.subTest(value=value):
                result = self.load(self.annual + [self.report("20260630", value, "20260820")])
                self.assertEqual(result["latest_report"]["period"], "20260630")
                self.assertEqual(result["latest_report"]["net_profit"], -0.001 if value == -0.001 else None)

    def test_latest_revision_wins_even_if_missing_profit(self) -> None:
        for value in (-5, None):
            result = self.load(self.annual + [
                self.report("20260630", 10, "20260820"),
                self.report("20260630", value, "20260901", update_flag="0"),
            ])
            self.assertEqual(result["latest_report"]["net_profit"], value)
            self.assertEqual(result["latest_report"]["ann_date"], "20260901")

    def test_same_day_update_flag_and_actual_announcement(self) -> None:
        result = self.load(self.annual + [
            self.report("20260630", 20, "20260820", f_ann_date="20260825", update_flag="0"),
            self.report("20260630", 5, "20260820", f_ann_date="20260825"),
        ])
        self.assertEqual(result["latest_report"]["net_profit"], 5)
        self.assertEqual(result["latest_report"]["ann_date"], "20260825")

    def test_ignores_future_disclosures_and_non_cumulative_reports(self) -> None:
        result = self.load(self.annual + [
            self.report("20260630", 3, "20260820", f_ann_date=None),
            self.report("20260630", -10, "20260901", f_ann_date="20260920"),
            self.report("20260930", -10, "20260915"),
            *[self.report("20260630", -10, "20260910", report_type=str(t)) for t in (2, 3, 5, 6, 7, 9)],
        ])
        self.assertEqual(result["latest_report"], {"period": "20260630", "ann_date": "20260820", "net_profit": 3})

    def test_all_three_years_required_and_no_rounding_at_zero(self) -> None:
        self.assertIsNone(self.load(self.annual[1:]))
        self.annual[0]["n_income_attr_p"] = 0.001
        self.assertEqual(self.load(self.annual)["annual_net_profit"]["20231231"], 0.001)
        self.annual[0]["n_income_attr_p"] = float("inf")
        self.assertIsNone(self.load(self.annual))

    def test_main_enforces_latest_nonnegative_and_counts_stages(self) -> None:
        pro = make_pro([120000] * 4)
        year = date.today().year
        base = pro.income.return_value.to_dict("records")
        pro.income.side_effect = [pd.DataFrame(base + [self.report(f"{year}0630", profit, f"{year}0820")])
                                  for profit in (0, 10, -0.001, None)]
        bars = pd.DataFrame({"trade_date": pd.bdate_range(end="2026-09-15", periods=252).strftime("%Y%m%d"),
                             "close": 10.0, "high": 12.0, "low": 8.0, "pct_chg": 1.0})
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "growth.json"
            with (patch.dict(os.environ, {"TUSHARE_TOKEN": "test-token"}),
                  patch.object(growth.ts, "pro_api", return_value=pro),
                  patch.object(growth.ts, "pro_bar", return_value=bars),
                  patch.object(growth, "get_latest_trade_date", return_value="20260915"),
                  patch.object(growth, "OUTPUT_FILE", output), patch.object(growth.time, "sleep"),
                  redirect_stdout(io.StringIO())):
                growth.main()
            data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["summary"]["profitable_candidates"], 4)
        self.assertEqual(data["summary"]["latest_report_candidates"], 2)
        self.assertEqual([r["code"] for r in data["rows"]], ["300000", "300001"])


if __name__ == "__main__":
    unittest.main()
