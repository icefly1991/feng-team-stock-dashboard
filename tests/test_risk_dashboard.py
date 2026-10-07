import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from generate_risk_dashboard import stock_union


class RiskDashboardTests(unittest.TestCase):
    def test_three_page_union_deduplicates_and_preserves_exchange(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            main = {'adjustments': {'qfq': {'rows': [{'code': '688001', 'name': '测试科创'}, {'code': '300001', 'name': '测试创业'}]}}}
            growth = {'rows': [{'code': '688001', 'name': '测试科创', 'market': '科创板'}]}
            small = {'rows': [{'code': '920001', 'ts_code': '920001.BJ', 'name': '测试北交', 'market': '北交所'}],
                     'screened': {'rows': [{'code': '600001', 'ts_code': '600001.SH', 'name': '测试主板', 'market': '主板'}]}}
            for name, value in [('dashboard.json', main), ('growth-market-dashboard.json', growth), ('small-cap-dashboard.json', small)]:
                (folder / name).write_text(json.dumps(value), encoding='utf-8')
            stocks = stock_union(folder)
            self.assertEqual(len(stocks), 4)
            mapping = {s['code']: s for s in stocks}
            self.assertEqual(mapping['920001']['ts_code'], '920001.BJ')
            self.assertEqual(mapping['300001']['market'], '创业板')
            self.assertEqual(len(stock_union(folder, 'watchlist')), 2)
            self.assertEqual(len(stock_union(folder, 'small-cap')), 2)


if __name__ == '__main__':
    unittest.main()
