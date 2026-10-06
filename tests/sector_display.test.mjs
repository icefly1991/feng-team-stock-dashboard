import { test } from 'node:test'
import assert from 'node:assert/strict'
import { conceptDisplay, businessSectors } from '../src/sectorDisplay.ts'
import { isBeijingStock, smallCapVisible } from '../src/smallCapVisibility.ts'

const data = { heat: { status: 'ok', concepts: {
  '机器人概念': { rank: 1, hot: true }, '人工智能': { rank: 2, hot: true },
  '芯片': { rank: 3, hot: true }, '小盘': { rank: 80, hot: false },
} }, stocks: { '920001': { status: 'ok', industry: ['自动化设备'], concepts: ['小盘', '机器人概念', '人工智能', '芯片'] } } }

test('hot concepts first, at most two, every other concept remains folded', () => {
  assert.deepEqual(conceptDisplay(data, ['未知', '芯片', '小盘', '人工智能', '机器人概念']), {
    visible: ['机器人概念', '人工智能'], hidden: ['芯片', '小盘', '未知'],
  })
})
test('unavailable heat folds all concepts instead of inventing popularity', () => {
  assert.deepEqual(conceptDisplay({ ...data, heat: { status: 'unavailable' } }, ['小盘']).visible, [])
})
test('business concepts must exist in classification and match a business keyword', () => {
  assert.deepEqual(businessSectors(data, '920001', ['工业机器人', '自动化设备']), [
    { name: '自动化设备', kind: 'industry' }, { name: '机器人概念', kind: 'concepts' },
  ])
})
test('missing business or classification never creates concept labels', () => {
  assert.deepEqual(businessSectors(null, '920001', ['人工智能']), [])
  assert.deepEqual(businessSectors(data, '920001', []), [])
})
test('general financial and size attributes stay folded even when rising', () => {
  const snapshot = { heat: { status: 'ok', concepts: { '融资融券': { rank: 1, hot: true } } } }
  assert.deepEqual(conceptDisplay(snapshot, ['融资融券']), { visible: [], hidden: ['融资融券'] })
})
test('Beijing and losses are independent filters, including their intersection', () => {
  const rows = [
    { ts_code: '920001.BJ', market: '北交所', loss_status: 'loss' },
    { ts_code: '920002.BJ', market: '北交所', loss_status: 'no_loss' },
    { ts_code: '600001.SH', market: '主板', loss_status: 'loss' },
    { ts_code: '300001.SZ', market: '创业板', loss_status: 'no_loss' },
    { ts_code: '000001.SZ', market: '主板', loss_status: 'unknown' },
  ]
  for (const [losses, beijing, expected] of [[false, false, [3, 4]], [true, false, [2, 3, 4]], [false, true, [1, 3, 4]], [true, true, [0, 1, 2, 3, 4]]]) {
    assert.deepEqual(rows.map((r, i) => smallCapVisible(r, losses, beijing) ? i : -1).filter(i => i >= 0), expected)
  }
})
test('exchange suffix identifies Beijing without guessing from numerical code', () => {
  assert.equal(isBeijingStock({ ts_code: '920001.BJ', market: '', loss_status: 'unknown' }), true)
  assert.equal(isBeijingStock({ market: '北交所', loss_status: 'unknown' }), true)
  assert.equal(isBeijingStock({ ts_code: '600001.SH', market: '主板', loss_status: 'no_loss' }), false)
})
