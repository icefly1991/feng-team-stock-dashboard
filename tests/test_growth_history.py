import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pandas as pd
from scripts.generate_growth_history import build_history
from scripts import generate_growth_history as history
from scripts.data_pipeline.summary import build_dashboard_payload
from scripts.data_pipeline.tushare_client import normalize_ts_code


class HistoryTests(unittest.TestCase):
    def test_adjustment_date_and_exchange(self):
        for adj in ('qfq', 'none'):
            payload = build_history(self.frame(), '002478', 'test', '20260916', adj)
            self.assertEqual(payload['adjustment'], adj)
            self.assertEqual(payload['code'], '002478')
        self.assertEqual(normalize_ts_code('002478'), '002478.SZ')
        self.assertEqual(normalize_ts_code('603617'), '603617.SH')
        self.assertEqual(normalize_ts_code('688013'), '688013.SH')
        payload = build_dashboard_payload({'qfq': [], 'none': []}, [], 0,
                                          updated_at='2026-09-17 10:00', trade_date='20260916')
        self.assertEqual(payload['trade_date'], '20260916')
        self.assertEqual(payload['updated_at'], '2026-09-17 10:00')

    def test_watchlist_generation_modes_and_failure_preserves_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'public/data'
            data.mkdir(parents=True)
            row = {'code': '002478', 'name': 'test', 'close': 17}
            (data / 'dashboard.json').write_text(json.dumps({'trade_date': '20260916',
                'adjustments': {adj: {'rows': [row]} for adj in ('qfq', 'none')}}), encoding='utf-8')
            with patch.object(history, 'ROOT', root), patch.dict(history.os.environ, {'TUSHARE_TOKEN': 'test'}), \
                 patch.object(history.ts, 'pro_api', return_value=Mock()), \
                 patch.object(history.ts, 'pro_bar', return_value=self.frame()) as bars, \
                 patch.object(history.time, 'sleep'):
                history.generate('watchlist')
                self.assertEqual([call.kwargs['adj'] for call in bars.call_args_list], ['qfq', None])
                self.assertTrue(all(call.kwargs['ts_code'] == '002478.SZ' for call in bars.call_args_list))
                path = data / 'watchlist-history/qfq/002478.json'
                old = path.read_bytes()
                bars.return_value = pd.DataFrame()
                with self.assertRaises(RuntimeError):
                    history.generate('watchlist')
                self.assertEqual(path.read_bytes(), old)
                bars.return_value = self.frame().assign(close=12)
                with self.assertRaises(RuntimeError):
                    history.generate('watchlist')
                self.assertEqual(path.read_bytes(), old)

    def frame(self):
        return pd.DataFrame([
            {"trade_date": "20260911", "open": 10, "high": 15, "low": 9, "close": 12, "vol": 100},
            {"trade_date": "20260914", "open": 12, "high": 14, "low": 11, "close": 13, "vol": 200},
            {"trade_date": "20260916", "open": 13, "high": 18, "low": 10, "close": 17, "vol": 300},
        ])

    def test_weekly_ohlc_volume_and_partial_week(self):
        result = build_history(self.frame().iloc[::-1], "300001", "test", "20260916")
        self.assertEqual(result["weekly"][1], {"time": "2026-09-14", "open": 12, "high": 18,
                                              "low": 10, "close": 17, "volume": 500})
        self.assertEqual(result["weekly"][0]["volume"], 100)
        self.assertAlmostEqual(result["metrics"]["position_pct"], 8 / 9 * 100)
        self.assertAlmostEqual(result["metrics"]["distance_high_pct"], (17 / 18 - 1) * 100)
        self.assertEqual(result["actual_start"], "2026-09-11")

    def test_calendar_cutoff_and_future_excluded(self):
        frame = self.frame()
        for date in ["20210915", "20210916", "20260917"]:
            row = frame.iloc[0].copy()
            row["trade_date"] = date
            frame = pd.concat([frame, row.to_frame().T], ignore_index=True)
        result = build_history(frame, "300001", "test", "20260916")
        self.assertEqual(result["actual_start"], "2021-09-16")
        self.assertEqual(result["actual_end"], "2026-09-16")
        self.assertEqual(len(result["daily"]), 4)

    def test_bad_data_rejected_and_flat_range_missing(self):
        for column, value in [("open", float('nan')), ("vol", -1), ("high", 1), ("low", 99)]:
            frame = self.frame()
            frame.loc[0, column] = value
            with self.assertRaises(ValueError):
                build_history(frame, "300001", "test", "20260916")
        frame = self.frame()
        frame[["open", "high", "low", "close"]] = 10
        self.assertIsNone(build_history(frame, "300001", "test", "20260916")["metrics"]["position_pct"])
        with self.assertRaises(ValueError):
            build_history(pd.concat([frame, frame]), "300001", "test", "20260916")


if __name__ == '__main__':
    unittest.main()
