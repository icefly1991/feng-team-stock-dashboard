import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from scripts import generate_shareholder_watch as generator


class ShareholderSourceTests(unittest.TestCase):
    def test_beijing_codes_use_exchange_from_dashboard(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config").mkdir()
            data = root / "public/data"
            data.mkdir(parents=True)
            fixtures = {
                root / "config/investor-watchlist.json": {"investors": [{"name": "Investor", "sources": ["source"]}], "sources": {"source": {}}},
                data / "dashboard.json": {"adjustments": {"qfq": {"rows": [{"code": "600001", "name": "Shanghai"}]}}},
                data / "growth-market-dashboard.json": {"rows": [{"code": "300001", "name": "Shenzhen"}]},
                data / "small-cap-dashboard.json": {"rows": [{"code": "920023", "name": "Beijing", "ts_code": "920023.BJ"}],
                                                     "screened": {"rows": [{"code": "600002", "name": "Screened", "ts_code": "600002.SH"}]}},
            }
            for path, value in fixtures.items():
                path.write_text(json.dumps(value), encoding="utf-8")
            pro = Mock()
            pro.top10_floatholders.return_value = pd.DataFrame()
            with patch.object(generator, "ROOT", root), patch.dict("os.environ", {"TUSHARE_TOKEN": "test"}), \
                    patch.object(generator.ts, "pro_api", return_value=pro), patch.object(generator.time, "sleep"):
                generator.generate()
            codes = {call.kwargs["ts_code"] for call in pro.top10_floatholders.call_args_list}
            self.assertEqual(codes, {"600001.SH", "600002.SH", "300001.SZ", "920023.BJ"})
            result = json.loads((data / "shareholder-watch.json").read_text(encoding="utf-8"))
            self.assertEqual(set(result["stocks"]), {"600001", "600002", "300001", "920023"})


if __name__ == "__main__":
    unittest.main()
