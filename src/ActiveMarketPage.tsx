import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { CopyStockButton, StockCopyProvider } from './StockCopy'
import { StockHistoryCode, StockHistoryProvider } from './StockHistoryPreview'
import { compareStockValues } from './stockSort'
import type { ActiveData, ActiveRow } from './activeTypes'

const pct = (v: number | null | undefined) => typeof v === 'number' && Number.isFinite(v) ? `${v.toFixed(2)}%` : '—'
const fixed = (v: number | null | undefined) => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(2) : '—'
const yi = (v: number) => `${(v / 100_000_000).toFixed(2)}亿`
const date = (v: string) => `${v.slice(0, 4)}-${v.slice(4, 6)}-${v.slice(6, 8)}`
type SortKey = 'avg_range_60d_pct' | 'avg_range_120d_pct' | 'avg_amount_60d_yi' | 'total_market_cap_yi' | 'position_52w_pct' | 'distance_ma250_pct'
const sortLabels: Record<SortKey, string> = {
  avg_range_60d_pct: '60日平均波幅', avg_range_120d_pct: '120日平均波幅', avg_amount_60d_yi: '60日日均成交额',
  total_market_cap_yi: '总市值', position_52w_pct: '52周内位置', distance_ma250_pct: '距年线',
}
const grid = 'grid grid-cols-[32px_144px_72px_116px_100px_96px_86px_88px_88px_100px] gap-3 items-center px-4'
const width = 'min-w-[1062px] w-full'

function validate(data: ActiveData) {
  if (data.schema_version !== 1 || data.adjustment !== 'qfq' || !/^\d{8}$/.test(data.trade_date) ||
      !/^\d{8}$/.test(data.financial_as_of) || !Array.isArray(data.rows) || !data.rows.length ||
      data.rows.length !== data.summary?.selected || new Set(data.rows.map(r => r.code)).size !== data.rows.length) throw new Error('股票池数据格式或版本不正确')
  for (const row of data.rows) {
    const f = row.financials
    if (!/^\d{6}$/.test(row.code) || ![row.close, row.total_market_cap_yi, row.avg_range_60d_pct, row.avg_range_120d_pct, row.avg_amount_60d_yi].every(v => Number.isFinite(v) && v > 0) ||
        !f || f.annual_reports?.length !== 3 || ![f.ttm_net_profit, f.ttm_recurring_profit].every(v => Number.isFinite(v) && v > 0) ||
        f.annual_reports.some((r, i) => ![r.net_profit, r.recurring_profit].every(v => Number.isFinite(v) && v > 0) ||
          !/^\d{4}1231$/.test(r.period) || r.ann_date > data.financial_as_of || r.recurring_ann_date > data.financial_as_of ||
          (i > 0 && Number(r.period.slice(0, 4)) !== Number(f.annual_reports[i - 1].period.slice(0, 4)) + 1))) throw new Error('股票池盈利依据或行情不完整')
  }
}

export default function ActiveMarketPage() {
  const [data, setData] = useState<ActiveData | null>(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; ascending: boolean }>({ key: 'avg_range_60d_pct', ascending: false })
  const [expanded, setExpanded] = useState<string | null>(null)
  const header = useRef<HTMLDivElement>(null)
  useEffect(() => {
    document.title = '盈利活跃 A 股'
    let live = true
    fetch(`${import.meta.env.BASE_URL}data/active-dashboard.json`).then(async r => {
      if (!r.ok) throw new Error('盈利活跃股数据尚未生成，请稍后重试')
      const json: ActiveData = await r.json()
      validate(json)
      if (live) setData(json)
    }).catch((e: unknown) => { if (live) setError(e instanceof Error ? e.message : '无法加载数据') })
    return () => { live = false }
  }, [])
  const rows = useMemo(() => {
    const text = query.trim().toLowerCase()
    return (data?.rows ?? []).filter(row => `${row.code} ${row.name} ${row.industry}`.toLowerCase().includes(text))
      .sort((a, b) => compareStockValues(a, b, a[sort.key], b[sort.key], sort.ascending))
  }, [data, query, sort])
  const sortButton = (key: SortKey) => <button type="button" onClick={() => setSort(s => ({ key, ascending: s.key === key ? !s.ascending : !key.startsWith('avg_') }))}
    className={`min-h-11 text-right ${sort.key === key ? 'font-semibold text-sky-700' : 'text-slate-500'}`}
    aria-label={`${sortLabels[key]}排序${sort.key === key ? (sort.ascending ? '，当前升序' : '，当前降序') : ''}`}>
    {sortLabels[key]} {sort.key === key ? (sort.ascending ? '↑' : '↓') : '↕'}</button>

  return <main className="min-h-screen bg-[#f7f5f0] px-3 py-6 text-slate-900 sm:px-6"><StockCopyProvider><StockHistoryProvider>
    <div className="mx-auto max-w-[1400px] space-y-5">
      <nav className="flex flex-wrap gap-4 text-sm text-sky-700"><a href="#">← 自选股看板</a><a href="#growth-market">小市值股票池</a></nav>
      <section className="rounded-3xl border border-white bg-white/90 p-5 shadow-sm sm:p-7">
        <p className="text-xs tracking-widest text-slate-400">A-SHARE RESEARCH</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">盈利活跃 A 股</h1>
        <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-600">持续盈利，持续活跃，中小市值优先。近 60 个交易日约三个月；平均波幅越大，日常价格波动越大。点击列标题可比较排序。</p>
        {data && <>
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500"><span>行情：{date(data.trade_date)}</span><span>财报截至：{date(data.financial_as_of)}</span><span>生成：{data.updated_at}（北京）</span><span>前复权 · Tushare</span></div>
          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[['盈利活跃股', data.rows.length], ['入选股平均60日波幅', pct(data.rows.reduce((n, r) => n + r.avg_range_60d_pct, 0) / data.rows.length)], ['已核验候选', data.summary.reviewed], ['活跃行情候选', data.summary.activity_candidates]].map(([label, value]) =>
              <div key={label} className="rounded-2xl bg-slate-50 p-4"><div className="text-xs text-slate-500">{label}</div><div className="mt-2 text-2xl font-semibold tabular-nums">{value}</div></div>)}
          </div>
          {data.rows.length < data.summary.target && <p className="mt-3 text-sm text-amber-700">本次符合条件 {data.rows.length} 只，目标约 {data.summary.target} 只；未降低盈利标准补足数量。</p>}
          {!!data.errors.length && <p className="mt-3 text-sm text-amber-700">{data.errors.length} 只候选因数据未就绪未纳入，名单可能不完整。</p>}
        </>}
        <details className="mt-5 text-sm leading-6 text-slate-600"><summary className="cursor-pointer font-medium text-sky-700">筛选与指标说明</summary>
          <p className="mt-3">沪深北普通 A 股，排除 ST、退市整理和近期行情不连续的股票。连续三年归母与扣非净利润均正，最近十二个月也均正。60 日日均成交额 ≥ 0.5 亿元、中位 ≥ 0.3 亿元，60/120 日平均波幅均 ≥ 2%。按持续活跃度与小市值加分选取最多 100 只，每次更新重算。</p>
          <p className="mt-2">每日真实波幅 = 当日高低差、最高价与昨收差绝对值、最低价与昨收差绝对值三者最大值。每天除以前一日收盘价，再取 60 日算术平均。包含跳空，不表示累计涨幅或收益；4% 相比 2% 表示平均每日波幅约两倍。</p>
        </details>
      </section>
      {error ? <p role="alert" className="rounded-2xl bg-white p-6 text-rose-700">{error}</p> : !data ? <p role="status">正在加载股票池…</p> :
        <section className="min-w-0 rounded-3xl border border-white bg-white p-3 shadow-sm sm:p-5">
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm text-slate-600">搜索 <input aria-label="搜索盈利活跃股" value={query} onChange={e => { setQuery(e.target.value); setExpanded(null) }} placeholder="名称、代码、行业" className="ml-2 max-w-[190px] rounded-xl border border-slate-200 px-3 py-2" /></label>
            <span className="text-xs text-slate-500">{rows.length} 只 · {sortLabels[sort.key]}{sort.ascending ? '从低到高' : '从高到低'}</span>
          </div>
          <div className="mt-4 rounded-xl border border-slate-200">
            <div ref={header} className="sticky top-0 z-30 overflow-hidden rounded-t-xl bg-slate-50 shadow-sm">
              <div className={`${grid} ${width} py-2 text-xs`}><div>#</div><div className="sticky left-0 z-10 self-stretch bg-slate-50 py-3">股票 / 详情</div><div className="text-right">收盘</div>
                <div className="text-right">{sortButton('avg_range_60d_pct')}</div><div className="text-right">{sortButton('avg_range_120d_pct')}</div><div className="text-right">{sortButton('avg_amount_60d_yi')}</div><div className="text-right">{sortButton('total_market_cap_yi')}</div><div className="text-right">{sortButton('position_52w_pct')}</div><div className="text-right">{sortButton('distance_ma250_pct')}</div><div className="text-right">TTM归母净利</div>
              </div>
            </div>
            <div className="overflow-x-auto rounded-b-xl" onScroll={e => { if (header.current) header.current.scrollLeft = e.currentTarget.scrollLeft }}>
              <div className={`${width} divide-y divide-slate-100`}>
                {rows.map((row, index) => <Fragment key={row.code}>
                  <div className={`${grid} py-3 text-sm`} data-stock-code={row.code}>
                    <div className="text-xs text-slate-400">{index + 1}</div>
                    <div className="sticky left-0 z-10 bg-white pr-1"><CopyStockButton value={row.name} label="名称" target={`${row.code}:name`} textClassName="font-medium" />
                      <StockHistoryCode code={row.code} name={row.name} tradeDate={data.trade_date} source="active"><CopyStockButton value={row.code} label="代码" target={`${row.code}:code`} secondary /></StockHistoryCode>
                      <button type="button" aria-expanded={expanded === row.code} aria-controls={`details-${row.code}`} onClick={() => setExpanded(expanded === row.code ? null : row.code)} className="min-h-8 text-xs text-sky-700">{expanded === row.code ? '收起详情 ↑' : '盈利依据 ↓'}</button>
                    </div>
                    <div className="text-right tabular-nums">{fixed(row.close)}</div><div className="text-right font-semibold tabular-nums text-sky-700">{pct(row.avg_range_60d_pct)}</div><div className="text-right tabular-nums">{pct(row.avg_range_120d_pct)}</div>
                    <div className="text-right tabular-nums">{fixed(row.avg_amount_60d_yi)}亿</div><div className="text-right tabular-nums">{fixed(row.total_market_cap_yi)}亿</div><div className="text-right tabular-nums">{pct(row.position_52w_pct)}</div><div className="text-right tabular-nums">{pct(row.distance_ma250_pct)}</div><div className="text-right tabular-nums">{yi(row.financials.ttm_net_profit)}</div>
                  </div>
                  {expanded === row.code && <div id={`details-${row.code}`} className="sticky left-0 w-[calc(100vw-54px)] max-w-full bg-slate-50 p-4 sm:w-full"><StockDetails row={row} /></div>}
                </Fragment>)}
              </div>
              {!rows.length && <p className="p-8 text-center text-sm text-slate-500">没有符合当前搜索的股票。</p>}
            </div>
          </div>
        </section>}
    </div>
  </StockHistoryProvider></StockCopyProvider></main>
}

function StockDetails({ row }: { row: ActiveRow }) {
  const f = row.financials
  return <div className="text-sm">
    <div className="min-w-0 space-y-3"><h2 className="font-semibold">{row.name} · 盈利依据</h2>
      <p className="text-xs text-slate-500">{row.market} · {row.industry} · {f.five_year_profitable ? '连续五年归母盈利' : '通过连续三年盈利筛选'}</p>
      <div className="overflow-x-auto"><table className="w-full min-w-[340px] text-xs"><thead><tr className="border-b border-slate-200 text-left text-slate-500"><th className="py-2">年报</th><th>归母净利</th><th>扣非净利</th><th>披露日期</th></tr></thead><tbody>{f.annual_reports.map(r => <tr key={r.period} className="border-b border-slate-100"><td className="py-2">{r.period.slice(0, 4)}</td><td>{yi(r.net_profit)}</td><td>{yi(r.recurring_profit)}</td><td title={`扣非披露：${date(r.recurring_ann_date)}`}>{date(r.ann_date)}</td></tr>)}</tbody></table></div>
      <p>最近十二个月：归母 {yi(f.ttm_net_profit)}，扣非 {yi(f.ttm_recurring_profit)}。</p>
      <p className="text-xs text-slate-500">最新报告期 {date(f.latest_period)}，披露于 {date(f.latest_ann_date)}；累计归母利润同比 {pct(f.profit_yoy_pct)}。</p>
      <p>TTM经营现金流 {yi(f.ttm_operating_cashflow)} · 资产负债率 {pct(f.debt_asset_pct)}</p>
      <p className="text-xs text-slate-500">现金流披露 {date(f.cash_ann_date)} · 资产负债表披露 {date(f.balance_ann_date)}</p>
      {f.quality_warnings.map(w => <p key={w} className="text-xs text-amber-800">{w}</p>)}
      <details className="text-xs text-slate-600"><summary className="cursor-pointer text-sky-700">查看 TTM 计算依据</summary><p className="mt-2">本期累计 + 上年全年 − 上年同期；年报直接取全年。</p>{f.ttm_evidence.map(e => <p key={e.period} className="mt-2">{date(e.period)}：归母 {yi(e.net_profit)} / 扣非 {yi(e.recurring_profit)}；披露 {date(e.ann_date)} / {date(e.recurring_ann_date)}</p>)}</details>
      <p className="text-xs text-slate-500">60日大幅涨跌（绝对涨跌≥3%）频次：{pct(row.large_move_60d_pct)}；成交额中位数 {fixed(row.median_amount_60d_yi)} 亿。</p>
      <a href={row.source_url} target="_blank" rel="noreferrer" className="inline-block text-xs text-sky-700 underline">巨潮资讯：查询该公司原始公告 ↗</a>
    </div>
  </div>
}
