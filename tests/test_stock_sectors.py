import unittest
from scripts.generate_stock_sectors import parse_sina


class SectorTests(unittest.TestCase):
    def page(self, industry="半导体", concepts=("机器人", "人工智能")):
        return '<title>公司(920023)</title><table class="comInfo1"><tr><td colspan="2">所属行业板块</td></tr>' + \
            (f'<tr><td>{industry}</td><td><a>点击查看</a></td></tr>' if industry else '') + \
            '<tr><td colspan="2">备注：此为申万行业分类</td></tr></table><table class="comInfo1">' + \
            '<tr><td colspan="2">所属概念板块</td></tr><tr><th>概念板块</td><th>同概念个股</td></tr>' + \
            ''.join(f'<tr><td>{tag}</td><td>点击查看</td></tr>' for tag in concepts) + '</table>'

    def test_industry_and_multiple_concepts_exclude_headers(self):
        result = parse_sina(self.page(), '920023')
        self.assertEqual(result['industry'], ['半导体'])
        self.assertEqual(result['concepts'], ['机器人', '人工智能'])
        self.assertEqual(result['status'], 'ok')

    def test_empty_concepts_are_not_a_query_failure(self):
        self.assertEqual(parse_sina(self.page(concepts=()), '920023')['concepts'], [])

    def test_missing_industry_is_partial(self):
        self.assertEqual(parse_sina(self.page(industry=''), '920023')['status'], 'partial')

    def test_wrong_stock_and_missing_sections_rejected(self):
        with self.assertRaises(ValueError):
            parse_sina(self.page(), '300338')
        with self.assertRaises(ValueError):
            parse_sina('<title>920023</title>', '920023')

    def test_duplicates_and_entities(self):
        self.assertEqual(parse_sina(self.page(concepts=('AI&amp;芯片', 'AI&amp;芯片')), '920023')['concepts'], ['AI&芯片'])
