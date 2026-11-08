from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import update_health as health
import report_update_alert as alert


class UpdateHealthTests(unittest.TestCase):
    def test_weekend_and_holiday_use_last_open_day(self):
        calendar = {"days": {"20261030": "1", "20261031": "0", "20261101": "0", "20261102": "1"}}
        for day in (1, 2):
            self.assertEqual(health.expected_trade_date(calendar, datetime(2026, 11, day, 8, tzinfo=health.TZ), morning=True), "20261030")
        self.assertEqual(health.expected_trade_date(calendar, datetime(2026, 11, 2, 17, tzinfo=health.TZ)), "20261102")

    def test_missing_calendar_is_not_assumed_weekday(self):
        with self.assertRaises(ValueError):
            health.expected_trade_date({"days": {}}, datetime(2026, 11, 2, 8, tzinfo=health.TZ), morning=True)

    def test_core_rejects_stale_partial_errors_and_invalid_price(self):
        good = {"trade_date": "20261106", "updated_at": "2026-11-06 17:00", "rows": [{"code": "1", "close": 3}]}
        self.assertEqual(health.validate_core("growth-market-dashboard.json", good, "20261106"), 1)
        for changed in ({"trade_date": "20261105"}, {"errors": ["upstream unavailable"]}, {"rows": []}, {"rows": [{"code": "1", "close": float('nan')}]}, {"rows": good["rows"] * 2}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                health.validate_core("growth-market-dashboard.json", {**good, **changed}, "20261106")

    def test_watchlist_requires_both_adjustments_and_all_stocks(self):
        data = {"trade_date": "20261106", "updated_at": "2026-11-06 17:00", "adjustments": {"qfq": {"summary": {"watchlist_total": 2}, "rows": [{"code": "1", "close": 2}]}}}
        with self.assertRaisesRegex(ValueError, "incomplete"):
            health.validate_core("dashboard.json", data, "20261106")

    def test_small_cap_requires_both_rankings(self):
        with self.assertRaisesRegex(ValueError, "250 and 100"):
            health.validate_core("small-cap-dashboard.json", {"trade_date": "20261106", "updated_at": "2026-11-06 17:00", "rows": []}, "20261106")

    def test_online_rejects_wrong_release_and_content_hash(self):
        with patch.object(health, "request_json", return_value={"schema_version": 1, "run_id": "old", "trade_date": "20261106"}):
            with self.assertRaisesRegex(ValueError, "current workflow"):
                health.check_online("https://example.test", "20261106", "new")
            with patch.object(health, "fetch_bytes", return_value=b'{}'):
                with self.assertRaisesRegex(ValueError, "differs"):
                    health.check_online("https://example.test", "20261106")

    def test_empty_or_retained_output_cannot_be_sealed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            health.write_json(root / "update-context.json", {"started_at": "2026-11-06T17:00:00+08:00", "expected_trade_date": "20261106"})
            health.write_json(root / "dashboard.json", {"updated_at": "2026-11-05 17:00"})
            with self.assertRaisesRegex(ValueError, "old output"):
                health.seal(root, "new")
            self.assertFalse((root / "update-health.json").exists())

    def test_incident_daily_dedup_and_recovery(self):
        now = datetime(2026, 11, 8, 8, tzinfo=timezone.utc)
        self.assertEqual(alert.incident_action(None, False, now), "create")
        self.assertEqual(alert.incident_action(None, True, now), "none")
        existing = {"state": "open", "updated_at": (now - timedelta(hours=2)).isoformat()}
        self.assertEqual(alert.incident_action(existing, False, now), "none")
        self.assertEqual(alert.incident_action(existing, True, now), "resolve")
        existing["updated_at"] = (now - timedelta(days=1)).isoformat()
        self.assertEqual(alert.incident_action(existing, False, now), "remind")

    def test_seal_and_live_verification_then_tampering(self):
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "data"
            now = datetime.now(health.TZ)
            day = now.strftime("%Y%m%d")
            stamp = now.isoformat()
            row = {"code": "000001", "close": 3}
            health.write_json(directory / "update-context.json", {
                "started_at": stamp, "expected_trade_date": day, "calendar": {"days": {day: "1"}},
            })
            health.write_json(directory / "dashboard.json", {
                "updated_at": stamp, "trade_date": day,
                "adjustments": {mode: {"summary": {"watchlist_total": 1}, "rows": [row]} for mode in ("qfq", "none")},
            })
            health.write_json(directory / "growth-market-dashboard.json", {"updated_at": stamp, "trade_date": day, "rows": [row]})
            rows = [{"code": str(i).zfill(6), "close": 3} for i in range(250)]
            health.write_json(directory / "small-cap-dashboard.json", {"updated_at": stamp, "trade_date": day, "rows": rows, "screened": {"rows": rows[:100]}})
            for name in health.AUX:
                health.write_json(directory / name, {"updated_at": stamp, "stocks": {}})
            paths = ["watchlist-history/qfq/000001.json", "watchlist-history/none/000001.json", "growth-history/000001.json"]
            paths += [f"small-cap-history/{day}/{row['code']}.json" for row in rows]
            for name in paths:
                health.write_json(directory / name, {"trade_date": day, "metrics": {"close": 3}})
            health.seal(directory, "release.1")
            self.assertFalse((directory / "update-context.json").exists())
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=folder))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}"
                result = health.check_online(url, day, "release.1")
                self.assertEqual(result["trade_date"], day)
                (directory / "dashboard.json").write_text('{}', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, "differs"):
                    health.check_online(url, day, "release.1")
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
