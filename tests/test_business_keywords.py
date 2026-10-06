import unittest
from scripts.data_pipeline.business_keywords import business_keywords, overrides


class BusinessKeywordTests(unittest.TestCase):
    def test_curated_config_has_source_hash_and_short_labels(self):
        for code, entry in overrides().items():
            self.assertRegex(entry['source_sha256'], r'^[0-9a-f]{64}$', code)
            self.assertTrue(1 <= len(entry['keywords']) <= 5, code)
            self.assertTrue(all(0 < len(label) <= 18 for label in entry['keywords']))

    def test_changed_source_cannot_reuse_old_labels(self):
        code = next(iter(overrides()))
        self.assertEqual(business_keywords(code, '主营业务发生变更，尚待人工核对。' * 8), [])

    def test_simple_subject_keeps_source_phrases(self):
        self.assertEqual(business_keywords('000000', '主要从事传感器、控制器的研发、生产和销售。'), ['传感器', '控制器'])

    def test_empty_or_long_source_is_not_truncated(self):
        self.assertEqual(business_keywords('000000', ''), [])
        self.assertEqual(business_keywords('000000', '非常复杂且没有清晰短业务词组的完整介绍' * 5), [])
