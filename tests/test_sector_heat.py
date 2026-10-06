import unittest
from unittest.mock import patch
from scripts.data_pipeline.sector_heat import parse_concept_quotes, quote_dates, collect_heat
import json


class SectorHeatTests(unittest.TestCase):
    def payload(self):
        return 'var snapshot = ' + json.dumps({f'gn_{i}': f'gn_{i},板块{i},10,5,1,{20-i},100,{100000000+i},sz000001'
                                             for i in range(20)}, ensure_ascii=False) + ';'

    def test_rank_hot_cutoff_and_unit(self):
        concepts, leaders = parse_concept_quotes(self.payload())
        self.assertEqual(concepts['板块0']['rank'], 1)
        self.assertEqual(concepts['板块0']['amount_yi'], 1)
        self.assertEqual(sum(v['hot'] for v in concepts.values()), 4)
        self.assertEqual(len(leaders), 3)

    def test_incomplete_snapshot_rejected(self):
        with self.assertRaises(ValueError):
            parse_concept_quotes('var x = {}')

    def test_reference_dates_must_agree(self):
        self.assertEqual(quote_dates(',2026-09-30,15:00:00,' * 3), '2026-09-30')
        for text in ('', ',2026-09-30,15:00:00,' * 2 + ',2026-09-29,15:00:00,'):
            with self.assertRaises(ValueError):
                quote_dates(text)

    def test_network_failure_has_no_fake_heat(self):
        import requests
        with patch('scripts.data_pipeline.sector_heat.requests.get', side_effect=requests.Timeout):
            self.assertEqual(collect_heat('2026-10-05')['status'], 'unavailable')
