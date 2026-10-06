import unittest

import pandas as pd

from scripts.generate_small_cap_dashboard import assess_losses, select_smallest, screen_non_loss


def reports(values=None):
    values = values or {}
    return pd.DataFrame([{"end_date": p, "ann_date": p[:4] + "0831" if not p.endswith("1231") else str(int(p[:4]) + 1) + "0330",
                          "f_ann_date": None, "report_type": "1", "update_flag": "0", "n_income_attr_p": values.get(p, 10)}
                         for p in ("20221231", "20231231", "20241231", "20251231", "20260630")])


class LossTests(unittest.TestCase):
    def test_any_loss_in_last_three_years(self):
        result = assess_losses(reports({"20241231": -2}), "20261005")
        self.assertEqual(result["loss_status"], "loss")
        self.assertEqual(result["annual_periods"], ["20231231", "20241231", "20251231"])

    def test_latest_loss_and_zero(self):
        self.assertEqual(assess_losses(reports({"20260630": -1}), "20261005")["loss_status"], "loss")
        self.assertEqual(assess_losses(reports({"20231231": 0, "20260630": 0}), "20261005")["loss_status"], "no_loss")

    def test_missing_year_is_unknown_no_backtracking(self):
        frame = reports()
        frame = frame[frame.end_date != "20241231"]
        result = assess_losses(frame, "20261005")
        self.assertEqual(result["loss_status"], "unknown")
        self.assertIsNone(result["annual_net_profit"]["20241231"])

    def test_known_loss_survives_missing_data(self):
        result = assess_losses(reports({"20241231": float("nan"), "20260630": -1}), "20261005")
        self.assertEqual(result["loss_status"], "loss")
        self.assertFalse(result["financial_complete"])

    def test_future_revision_and_single_quarter_excluded(self):
        frame = reports()
        base = frame.iloc[-1].to_dict()
        frame = pd.concat([frame, pd.DataFrame([{**base, "ann_date": "20261201", "n_income_attr_p": -10},
                                              {**base, "report_type": "2", "ann_date": "20260831", "n_income_attr_p": -5}])])
        self.assertEqual(assess_losses(frame, "20261005")["loss_status"], "no_loss")

    def test_empty_data_unknown(self):
        self.assertEqual(assess_losses(pd.DataFrame(), "20261005")["loss_status"], "unknown")


class RankingTests(unittest.TestCase):
    def test_screening_excludes_st_before_reports_and_replenishes_100(self):
        candidates = [{'ts_code': f'{600000+i}.SH', 'symbol': str(600000+i), 'name': name,
                       'total_market_cap_yi': i+1} for i, name in enumerate(['ST甲', '*ST乙', 'st丙', '*st丁'] + ['正常公司']*100)]
        queried = []
        def load(item):
            queried.append(item['symbol'])
            return {'loss_status': 'no_loss', 'financial_complete': True}
        selected, audit = screen_non_loss(candidates, load)
        self.assertEqual(len(selected), 100)
        self.assertEqual(selected[0]['symbol'], '600004')
        self.assertEqual(selected[-1]['symbol'], '600103')
        self.assertEqual(queried, [r['symbol'] for r in selected])
        self.assertEqual(len(audit), 100)

    def test_screening_scans_beyond_250_then_ranks_first_100(self):
        candidates = [{'ts_code': f'{600000+i}.SH', 'symbol': str(600000+i), 'total_market_cap_yi': i+1} for i in range(400)]
        selected, audit = screen_non_loss(candidates, lambda item: {'loss_status': 'loss' if int(item['symbol']) < 600270 else 'no_loss', 'financial_complete': True})
        self.assertEqual(len(selected), 100)
        self.assertEqual(len(audit), 370)
        self.assertEqual(selected[0]['symbol'], '600270')
        self.assertEqual(selected[-1]['symbol'], '600369')

    def test_screening_excludes_beijing_unknown_and_incomplete_reports(self):
        candidates = [{'ts_code': '920001.BJ', 'symbol': '920001', 'total_market_cap_yi': 1}] + [
            {'ts_code': f'{600000+i}.SH', 'symbol': str(600000+i), 'total_market_cap_yi': i+2} for i in range(3)]
        states = {'600000': {'loss_status': 'unknown', 'financial_complete': False},
                  '600001': {'loss_status': 'no_loss', 'financial_complete': False},
                  '600002': {'loss_status': 'no_loss', 'financial_complete': True}}
        selected, audit = screen_non_loss(candidates, lambda item: states[item['symbol']], target=1)
        self.assertEqual([r['symbol'] for r in selected], ['600002'])
        self.assertEqual(len(audit), 3)

    def test_st_beijing_and_exact_250_original_precision(self):
        basic = pd.DataFrame([{"ts_code": f"{i:06}.BJ", "symbol": f"{i:06}", "name": "*ST test", "market": "北交所"} for i in range(260)])
        market = pd.DataFrame([{"ts_code": f"{i:06}.BJ", "total_mv": 10000 + i / 1000} for i in range(260)])
        rows, total = select_smallest(basic, market)
        self.assertEqual(total, 260)
        self.assertEqual(len(rows), 250)
        self.assertEqual(rows[249]["symbol"], "000249")
        self.assertEqual(select_smallest(basic, market, include_st=False)[0], [])
        self.assertEqual(select_smallest(basic, market, include_bj=False)[0], [])

    def test_b_shares_invalid_market_cap_and_ties(self):
        basic = pd.DataFrame([{"ts_code": code, "symbol": code[:6], "name": code} for code in ("600002.SH", "600001.SH", "200001.SZ", "000001.SZ", "920001.BJ")])
        market = pd.DataFrame([{"ts_code": r.ts_code, "total_mv": value} for r, value in zip(basic.itertuples(), [10000, 10000, 1, float("inf"), -1])])
        rows, _ = select_smallest(basic, market)
        self.assertEqual([r["symbol"] for r in rows], ["600001", "600002"])


if __name__ == "__main__":
    unittest.main()
