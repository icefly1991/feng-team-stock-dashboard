import assert from 'node:assert/strict'
import { readableRiskEvidence } from '../src/riskEvidence.ts'

test('risk evidence excludes technical docs and raw snapshots, preserves primary announcements', () => {
  assert.equal(readableRiskEvidence({title:'接口说明',url:'https://tushare.pro/document/2?doc_id=80'}),false)
  assert.equal(readableRiskEvidence({title:'原始记录',url:'data/risk-test-financials/301139.SZ.json'}),false)
  assert.equal(readableRiskEvidence({title:'原始记录',url:'https://example.com/raw.json'}),false)
  assert.equal(readableRiskEvidence({title:'终止上市公告',url:'https://disc.static.szse.cn/announcement.PDF'}),true)
})
import test from 'node:test'
import { chineseRiskText, riskChinese, riskLevel, riskMetricText, riskHighest } from '../src/riskDisplay.ts'

test('risk terminology is Chinese and unknown values remain unverified', () => {
  for (const value of ['CLEAN', 'WATCH', 'HIGH', 'SEVERE', 'VERY SEVERE', 'HARD AVOID']) {
    assert(!/[A-Za-z]/.test(riskChinese(value)))
  }
  assert.equal(riskChinese('unexpected_vendor_value'), '待核实')
  assert.equal(chineseRiskText('TTM CFO / EBIT ST Tushare'), '近十二个月 经营现金流 / 息税前利润 风险警示 财务数据平台')
  assert.equal(riskMetricText('csrc_or_governance_event', ['csrc_investigation', 'debt_overdue']), '证监会立案、债务逾期')
})
test('incomplete zero risk is unverified and missing values are not zero', () => {
  assert.equal(riskLevel({ score: 0, complete: false, level: 'CLEAN' }), '待核查')
  assert.equal(riskLevel({ score: 51, complete: false, level: 'HIGH' }), '高风险')
  assert.equal(riskMetricText('deducted_net_profit', null), '待核实')
})
test('floor reason takes precedence over ordinary points', () => {
  assert.equal(riskHighest({ floors: [{ score: 70, title: '立案' }, { score: 90, title: '无法表示意见' }], triggers: [{ points: 35, title: '收入低于线' }] }), '无法表示意见')
})
