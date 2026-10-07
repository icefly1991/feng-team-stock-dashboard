export type RiskSource = { title: string; url: string }
export type RiskTrigger = { title: string; points: number; module: string; metric: string | null; source: RiskSource | null }
export type RiskResult = {
  score: number; level: string; complete: boolean; raw_score: number; combination_points: number; floor: number
  modules: { key: string; label: string; score: number }[]; triggers: RiskTrigger[]
  combinations: { title: string; points: number }[]; floors: { title: string; score: number; source: RiskSource | null }[]
  missing: string[]; latest_warning: string | null
}
export type RiskRow = {
  id: string; ts_code: string; name: string; market: string; as_of: string; historical: boolean
  context: { period: string; annual_period: string; ann_date: string; revenue_ttm: number | null; revenue_threshold: number | null }
  metrics: Record<string, number | boolean | string | string[] | null>; risk: RiskResult; documents: RiskSource[]
  events: { id: string; title: string; published_at: string; source: RiskSource; note?: string }[]
}
export const riskDate = (v: string | null) => v ? `${v.slice(0, 4)}-${v.slice(4, 6)}-${v.slice(6, 8)}` : '—'
export const riskScoreText = (v: number) => Number.isInteger(v) ? String(v) : v.toFixed(1)
export const riskChinese = (value: string) => ({
  CLEAN: '低风险', WATCH: '需关注', HIGH: '高风险', SEVERE: '严重风险', 'VERY SEVERE': '极高风险', 'HARD AVOID': '应回避',
  severe: '严重', ordinary: '普通', disclaimer: '无法表示', adverse: '否定', standard: '标准无保留', qualified: '保留',
  csrc_investigation: '证监会立案', fund_occupation: '资金占用', illegal_guarantee: '违规担保',
  debt_overdue: '债务逾期', bank_freeze: '银行账户冻结', confirmed_fraud: '已确认财务造假',
} as Record<string, string>)[value] || '待核实'
export function riskLevel(result: RiskResult) {
  return result.score < 20 && !result.complete ? '待核查' : riskChinese(result.level)
}
export function riskHighest(result: RiskResult) {
  return [...result.floors].sort((a, b) => b.score - a.score)[0]?.title ||
    [...result.triggers].sort((a, b) => b.points - a.points)[0]?.title || '已核实数据暂未触发加分项'
}
export function chineseRiskText(text: string) {
  return text.replace(/\bTTM\b/g, '近十二个月').replace(/\bCFO\b/g, '经营现金流').replace(/\bEBIT\b/g, '息税前利润')
    .replace(/\bST\b/g, '风险警示').replace(/Tushare/gi, '财务数据平台')
}
export const riskMetricLabels: Record<string, string> = {
  deducted_net_profit: '近十二个月扣非净利润', consecutive_loss_years: '连续年度扣非亏损', revenue_to_st_threshold: '近十二个月营收 / 收入阈值',
  lowest_profit_metric: '近十二个月利润孰低', net_asset_growth: '净资产同比变动', negative_net_assets: '净资产为负',
  goodwill_to_equity: '商誉 / 净资产', cfo_negative_years: '连续年度经营现金流为负', cash_conversion_3y: '三年累计经营现金流 / 归母净利',
  ar_growth_minus_revenue_growth: '应收增速 − 营收增速', ar_to_revenue: '期末应收 / 近十二个月营收',
  other_receivables_to_equity: '其他应收款 / 净资产', cash_to_short_debt: '现金 / 短债', interest_coverage: '近十二个月息税前利润 / 利息费用',
  annual_report_inquiry: '年报问询', inquiry_severity: '问询级别', second_inquiry: '二次问询',
  audit_opinion: '财报审计意见', internal_control_opinion: '内控审计意见', csrc_or_governance_event: '立案 / 治理事件',
}
export const riskMissingLabels: Record<string, string> = {
  announcement_coverage: '年报问询、二次问询、内控、立案、治理及流动性公告未完整扫描',
  ar_ratio_abnormal: '应收占比异常的历史 / 同行阈值待确认', governance_points_25_to_40: '资金占用 / 担保的25–40分分档待确认',
  fund_occupation_equity_ratio: '资金占用金额 / 净资产缺失', freeze_major_account: '冻结账户是否主要账户待核实',
  annual_st_trigger: '扣除后的年度营收或年度利润触发条件尚未核实',
}
export function riskMetricText(key: string, value: RiskRow['metrics'][string]) {
  if (value == null) return '待核实'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (Array.isArray(value)) return value.length ? value.map(riskChinese).join('、') : '公告未完整扫描'
  if (typeof value === 'string') return riskChinese(value)
  if (['deducted_net_profit', 'lowest_profit_metric'].includes(key)) return `${(value / 100_000_000).toFixed(3)}亿元`
  if (['goodwill_to_equity', 'ar_to_revenue', 'other_receivables_to_equity'].includes(key)) return `${(value * 100).toFixed(1)}%`
  if (key === 'net_asset_growth') return `${value.toFixed(1)}%`
  if (key === 'ar_growth_minus_revenue_growth') return `${value.toFixed(1)}个百分点`
  if (key === 'cash_to_short_debt') return value.toFixed(4)
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}
