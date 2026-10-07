import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from data_pipeline.risk_score import score_risk
from generate_risk_test import extract
import pandas as pd


def clean():
    return dict(deducted_net_profit=1, consecutive_loss_years=0, revenue_to_st_threshold=2,
        lowest_profit_metric=1, net_asset_growth=0, negative_net_assets=False,
        goodwill_to_equity=0, cfo_negative_years=0, cash_conversion_3y=1,
        ar_growth_minus_revenue_growth=0, ar_ratio_abnormal=False, other_receivables_to_equity=0,
        cash_to_short_debt=2, interest_coverage=2, annual_st_trigger=False)


def event(kind, **params):
    return dict(id=params.pop("id", kind), kind=kind, published_at="20250101", title=kind,
                source={"title": "verified fixture", "url": "https://example.com/verified"}, **params)


class RiskScoreTests(unittest.TestCase):
    def test_terminal_listing_state_always_100_even_if_financials_clean(self):
        for status in ('termination_decided', 'delisting', 'delisted'):
            result = score_risk(clean() | {'listing_status': status}, [], '20261007')
            self.assertEqual(result['score'], 100)
            self.assertEqual(result['floor'], 100)
        self.assertEqual(score_risk(clean() | {'listing_status': 'L'}, [], '20261007')['score'], 0)

    def score(self, metrics=None, events=None, as_of="20260101"):
        return score_risk(metrics or clean(), events or [], as_of, event_coverage=True)

    def test_raw_score_not_weighted(self):
        m = clean() | dict(deducted_net_profit=-1, consecutive_loss_years=3,
                          revenue_to_st_threshold=1.1, goodwill_to_equity=.6)
        r = self.score(m)
        self.assertEqual(r["raw_score"], 45)
        self.assertEqual(r["score"], 45)

    def test_strict_thresholds_and_non_st_ttm(self):
        m = clean() | dict(revenue_to_st_threshold=1.2, net_asset_growth=-30,
                          goodwill_to_equity=.5, ar_growth_minus_revenue_growth=50,
                          other_receivables_to_equity=.2, cash_to_short_debt=.5, interest_coverage=1.5)
        r = self.score(m)
        self.assertEqual(r["raw_score"], 23)  # 8 + 5 + 5 + 5, no overlapping tiers
        m = clean() | dict(revenue_to_st_threshold=.8, lowest_profit_metric=-1)
        self.assertEqual(self.score(m)["score"], 30)  # 15 near + 15 combo, no formal +35
        self.assertEqual(self.score(m | {"annual_st_trigger": True})["score"], 65)

    def test_all_floors(self):
        cases = [(event("csrc_investigation", scope="disclosure"), 70),
                 (event("fund_occupation", equity_ratio=.11), 75),
                 (event("fund_occupation", major=True), 75),
                 (event("internal_control_opinion", opinion="adverse"), 70),
                 (event("audit_opinion", opinion="disclaimer"), 90),
                 (event("bank_freeze", major_account=True), 80),
                 (event("confirmed_fraud"), 100)]
        for e, score in cases:
            with self.subTest(e=e):
                self.assertEqual(self.score(events=[e])["score"], score)
        self.assertEqual(self.score(clean() | {"negative_net_assets": True})["score"], 90)

    def test_inquiry_severity_stages_and_dedup(self):
        severe = event("annual_inquiry", severity="severe", letter_id="first")
        same_letter_reply = severe | {"id": "reply"}
        r = self.score(events=[severe, severe, same_letter_reply])
        self.assertEqual(r["score"], 15)
        second = event("annual_inquiry", id="second", severity="ordinary", letter_id="second")
        r = self.score(events=[severe, second])
        self.assertEqual(r["raw_score"], 25)
        self.assertEqual(r["combination_points"], 10)
        self.assertEqual(r["score"], 35)
        self.assertEqual(self.score(events=[event("annual_inquiry", severity="ordinary")])["score"], 5)

    def test_explicit_second_inquiry_without_first_record(self):
        result = self.score(events=[event("second_inquiry")])
        self.assertEqual(result["score"], 10)
        self.assertEqual(result["combination_points"], 0)

    def test_major_occupation_reason_does_not_invent_ratio(self):
        result = self.score(events=[event("fund_occupation", major=True)])
        self.assertEqual(result["floor"], 75)
        self.assertEqual(result["floors"][0]["title"], "重大资金占用")

    def test_combination_bonuses_and_cap(self):
        events = [event("annual_inquiry", severity="severe"), event("second_inquiry"),
                  event("csrc_investigation", scope="financial"),
                  event("internal_control_opinion", opinion="adverse"),
                  event("fund_occupation", equity_ratio=.2)]
        metrics = clean() | dict(cfo_negative_years=2, ar_growth_minus_revenue_growth=51,
                                lowest_profit_metric=-1, revenue_to_st_threshold=1.1)
        r = self.score(metrics, events)
        self.assertEqual(r["combination_points"], 65)
        self.assertEqual(r["score"], 100)
        self.assertNotIn("fund_occupation", [t["title"] for t in r["triggers"]])
        self.assertIn("governance_points_25_to_40", r["missing"])

    def test_cash_conversion_can_trigger_cfo_combo(self):
        r = self.score(clean() | dict(cash_conversion_3y=.1, ar_growth_minus_revenue_growth=40))
        self.assertEqual(r["score"], 23)

    def test_missing_inputs_not_safe(self):
        r = score_risk({}, [], "20260101")
        self.assertEqual(r["score"], 0)
        self.assertFalse(r["complete"])
        self.assertIn("announcement_coverage", r["missing"])
        r = self.score(clean() | {"deducted_net_profit": float("nan")})
        self.assertFalse(r["complete"])

    def test_unknown_inquiry_classification_not_assumed_ordinary(self):
        r = self.score(events=[event("annual_inquiry")])
        self.assertEqual(r["score"], 0)
        self.assertIn("inquiry_severity", r["missing"])

    def test_known_loss_still_triggers_combination_if_other_profit_missing(self):
        m = clean() | dict(lowest_profit_metric=None, profit_loss_known=True, revenue_to_st_threshold=1.1)
        self.assertEqual(self.score(m)["combination_points"], 15)

    def test_future_resolved_and_latest_audits(self):
        severe = event("annual_inquiry", severity="severe") | {"published_at": "20260201"}
        self.assertEqual(self.score(events=[severe])["score"], 0)
        self.assertEqual(self.score(events=[event("csrc_investigation", scope="financial", resolved_at="20251201")])["score"], 0)
        old = event("audit_opinion", opinion="disclaimer", id="old")
        latest = event("audit_opinion", opinion="standard", id="new") | {"published_at": "20251201"}
        self.assertEqual(self.score(events=[old, latest])["score"], 0)

    def test_bank_freeze_not_all_accounts_hard(self):
        self.assertEqual(self.score(events=[event("bank_freeze", major_account=False)])["score"], 0)

    def test_negative_equity_ratios_not_divided(self):
        from generate_risk_test import divide
        self.assertIsNone(divide(20, -10))
        self.assertIsNone(divide(20, 0))

    def test_half_year_revenue_uses_ttm_and_asof(self):
        periods = [("20221231", "20230401"), ("20231231", "20240401"),
                   ("20240630", "20240801"), ("20241231", "20250401"),
                   ("20250630", "20250801"), ("20251231", "20260401")]
        base = [dict(end_date=p, ann_date=a, f_ann_date=a, report_type="1", update_flag="0",
                     revenue=200 if p.endswith("0630") else 500, total_profit=5,
                     n_income_attr_p=5, ebit=10, fin_exp_int_exp=1,
                     total_hldr_eqy_exc_min_int=100, goodwill=0, accounts_receiv=10,
                     oth_receiv=0, money_cap=100, st_borr=10, non_cur_liab_due_1y=10,
                     n_cashflow_act=20, profit_dedt=3) for p, a in periods]
        frames = {key: pd.DataFrame(base) for key in ("income", "balancesheet", "cashflow", "fina_indicator")}
        m, context = extract(frames, "主板", "20250828")
        self.assertEqual(context["period"], "20250630")
        self.assertEqual(context["revenue_ttm"], 500)
        self.assertAlmostEqual(m["revenue_to_st_threshold"], 500 / 300000000)
        self.assertEqual(m["cash_conversion_3y"], 4)
        self.assertFalse(m["annual_st_trigger"])

        # A late/missing indicator feed must not roll all metrics back to an old period.
        frames["fina_indicator"] = frames["fina_indicator"][frames["fina_indicator"].end_date != "20250630"]
        m, context = extract(frames, "主板", "20250828")
        self.assertEqual(context["period"], "20250630")
        self.assertEqual(context["revenue_ttm"], 500)
        self.assertIsNone(m["deducted_net_profit"])
        self.assertFalse(score_risk(m, [], "20250828")["complete"])

        _, north = extract(frames, "北交所", "20250828")
        self.assertEqual(north["revenue_threshold"], 50000000)

    def test_indicator_empty_duplicate_does_not_erase_value(self):
        from generate_risk_test import indicator_reports_as_of
        frame = pd.DataFrame([
            dict(end_date="20241231", ann_date="20250401", profit_dedt=123, ebit=5),
            dict(end_date="20241231", ann_date="20250401", profit_dedt=None, ebit=None),
            dict(end_date="20241231", ann_date="20260901", profit_dedt=None, ebit=8)])
        self.assertEqual(indicator_reports_as_of(frame, "20250801")["20241231"]["profit_dedt"], 123)
        self.assertTrue(pd.isna(indicator_reports_as_of(frame, "20261001")["20241231"]["profit_dedt"]))


if __name__ == "__main__":
    unittest.main()
