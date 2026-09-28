export type Financials = {
  annual_reports: { period: string; net_profit: number; recurring_profit: number; ann_date: string; recurring_ann_date: string }[]
  five_year_profitable: boolean; latest_period: string; latest_ann_date: string
  ttm_net_profit: number; ttm_recurring_profit: number; profit_yoy_pct: number | null
  ttm_operating_cashflow: number; debt_asset_pct: number; quality_period: string
  cash_ann_date: string; balance_ann_date: string; quality_warnings: string[]
  ttm_evidence: { period: string; net_profit: number; recurring_profit: number; ann_date: string; recurring_ann_date: string }[]
}
export type ActiveRow = {
  code: string; name: string; ts_code: string; market: string; industry: string
  close: number; today_return_pct: number; total_market_cap_yi: number
  avg_range_60d_pct: number; avg_range_120d_pct: number; large_move_60d_pct: number
  avg_amount_60d_yi: number; median_amount_60d_yi: number; activity_score: number
  position_52w_pct: number | null; distance_ma250_pct: number | null; source_url: string
  financials: Financials

}
export type ActiveData = {
  schema_version: number; trade_date: string; updated_at: string; financial_as_of: string; adjustment: string
  summary: { universe: number; activity_candidates: number; reviewed: number; selected: number; target: number }
  rows: ActiveRow[]; errors: { code: string; stage: string; error: string }[]
}
