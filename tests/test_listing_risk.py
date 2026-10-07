import unittest
from scripts.data_pipeline.listing_risk import listing_risk
from scripts.generate_small_cap_dashboard import select_smallest
import pandas as pd

class ListingRiskTests(unittest.TestCase):
    def test_yuandao_decision_is_time_bounded(self):
        stock = {'ts_code': '301139.SZ', 'name': '元道通信'}
        self.assertIsNone(listing_risk(stock, '20260920'))
        self.assertEqual(listing_risk(stock, '20260921')['status'], 'termination_decided')
        self.assertIn('szse.cn', listing_risk(stock, '20261007')['source']['url'])

    def test_all_terminal_states_but_not_st_are_excluded(self):
        self.assertTrue(listing_risk({'name': '测试退'}))
        self.assertTrue(listing_risk({'name': '退市测试'}))
        self.assertTrue(listing_risk({'name': '测试', 'list_status': 'D'}))
        self.assertIsNone(listing_risk({'name': '*ST测试', 'list_status': 'L'}))
        self.assertIsNone(listing_risk({'name': '测试', 'delist_date': '20261028'}, '20261007'))

    def test_filter_before_rank_and_refill(self):
        basic = pd.DataFrame([
            {'ts_code':'301139.SZ','symbol':'301139','name':'元道退'},
            {'ts_code':'600001.SH','symbol':'600001','name':'正常一'},
            {'ts_code':'600002.SH','symbol':'600002','name':'正常二'}])
        market = pd.DataFrame({'ts_code': basic.ts_code, 'total_mv':[1,2,3]})
        selected, count = select_smallest(basic, market, target=2)
        self.assertEqual(count,2)
        self.assertEqual([r['symbol'] for r in selected],['600001','600002'])
