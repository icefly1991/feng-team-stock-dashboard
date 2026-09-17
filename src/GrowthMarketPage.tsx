import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Copy } from 'lucide-react'
import { CopyStockButton, StockCopyProvider } from './StockCopy'

type GrowthRow = {
  code: string
  name: string
  close: number
  today_return_pct: number
  total_market_cap_yi: number
  distance_ma250_pct?: number
  distance_52w_high_pct: number
  distance_52w_low_pct: number
  position_52w_pct: number
  annual_net_profit: Record<string, number>
  latest_report: { period: string; ann_date: string; net_profit: number }
  main_business: string
}

type GrowthMarketData = {
  updated_at: string
  trade_date: string
  filters: {
    total_market_cap_lt_yi: number
    annual_periods: string[]
    latest_report_net_profit_rule: string
    financial_as_of: string
    adjustment: string
  }
  summary: {
    growth_market_total: number
    market_cap_candidates: number
    profitable_candidates: number
    latest_report_candidates: number
    displayed_total: number
  }
  rows: GrowthRow[]
}

type SortKey = 'total_market_cap_yi' | 'position_52w_pct' | 'distance_ma250_pct'
const sortLabels: Record<SortKey, string> = {
  total_market_cap_yi: '总市值',
  position_52w_pct: '52周内位置',
  distance_ma250_pct: '距年线',
}

const dataUrl = `${import.meta.env.BASE_URL}data/growth-market-dashboard.json`
// The minimum includes all ten columns, nine gaps and the row's horizontal padding.
// Split the remaining space equally between business text and the position indicator.
const tableGridClass = 'grid grid-cols-[28px_120px_64px_68px_78px_72px_90px_132px_minmax(134px,1fr)_minmax(134px,1fr)] gap-3 [&>div]:min-w-0'
const tableWidthClass = 'w-full min-w-[1060px]'

const formatPct = (value: number | undefined) =>
  typeof value !== 'number' || !Number.isFinite(value) ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(1)}%`
const metricColorClass = (value: number | undefined) =>
  typeof value !== 'number' || !Number.isFinite(value)
    ? 'text-slate-400'
    :
  value > 0 ? 'text-emerald-700' : value < 0 ? 'text-rose-600' : 'text-slate-500'
const formatProfit = (value: number | undefined) =>
  value === undefined ? '—' : `${(value / 100_000_000).toFixed(2)}亿`
const isStStock = (row: GrowthRow) => row.name.toUpperCase().includes('ST')
const formatDate = (date: string) => `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`
const formatReport = (period: string) => `${period.slice(0, 4)}年${({ '0331': '一季报', '0630': '半年报', '0930': '三季报', '1231': '年报' } as Record<string, string>)[period.slice(4)] ?? ''}`

function GrowthMarketPage() {
  const [data, setData] = useState<GrowthMarketData | null>(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; ascending: boolean }>({ key: 'position_52w_pct', ascending: true })
  const headerScrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    document.title = '创业板/科创板小市值股票池'
    let mounted = true
    fetch(dataUrl)
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((json: GrowthMarketData) => {
        if (!mounted) return
        const limit = json.filters?.total_market_cap_lt_yi
        if (
          !Number.isFinite(limit) || limit <= 0 || !Array.isArray(json.rows) ||
          json.rows.some((row) => !Number.isFinite(row.total_market_cap_yi) || row.total_market_cap_yi <= 0 || row.total_market_cap_yi >= limit)
        ) {
          setError('股票池总市值数据尚未就绪，请更新数据后重试')
          return
        }
        const periods = json.filters.annual_periods
        const asOf = json.filters.financial_as_of
        const year = Number(asOf?.slice(0, 4))
        if (
          !/^\d{8}$/.test(asOf ?? '') || !Array.isArray(periods) || periods.length !== 3 ||
          periods.some((period, index) => period !== `${year - 3 + index}1231`) ||
          json.filters.latest_report_net_profit_rule !== 'n_income_attr_p >= 0 (consolidated year-to-date)' ||
          !Number.isInteger(json.summary?.latest_report_candidates) ||
          json.rows.some((row) => {
            const report = row.latest_report
            return periods.some((period) => !Number.isFinite(row.annual_net_profit?.[period]) || row.annual_net_profit[period] <= 0) ||
              !report || !Number.isFinite(report.net_profit) || report.net_profit < 0 ||
              !/^\d{4}(0331|0630|0930|1231)$/.test(report.period) ||
              !/^\d{8}$/.test(report.ann_date) || report.ann_date > asOf ||
              report.period > report.ann_date || report.period < periods[2]
          })
        ) {
          setError('股票池财报数据尚未就绪，请更新数据后重试')
          return
        }
        setData(json)
      })
      .catch(() => mounted && setError('无法加载小市值股票池数据'))
    return () => {
      mounted = false
    }
  }, [])

  const rows = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!data) return []
    const eligibleRows = data.rows.filter((row) => !isStStock(row))
    const filtered = normalized
      ? eligibleRows.filter(
          (row) =>
            row.code.toLowerCase().includes(normalized) ||
            row.name.toLowerCase().includes(normalized) ||
            row.main_business.toLowerCase().includes(normalized),
        )
      : eligibleRows
    return [...filtered].sort((a, b) => {
      const aValue = a[sort.key]
      const bValue = b[sort.key]
      const aValid = typeof aValue === 'number' && Number.isFinite(aValue)
      const bValid = typeof bValue === 'number' && Number.isFinite(bValue)
      if (aValid !== bValid) return aValid ? -1 : 1
      const difference = aValid && bValid ? (aValue - bValue) * (sort.ascending ? 1 : -1) : 0
      return difference || a.code.localeCompare(b.code)
    })
  }, [data, query, sort])

  const sortButton = (key: SortKey) => (
    <button
      type="button"
      onClick={() => setSort((current) => ({ key, ascending: current.key === key ? !current.ascending : true }))}
      aria-label={`${sortLabels[key]}：${sort.key === key ? `当前${sort.ascending ? '升序' : '降序'}，` : ''}点击${sort.key === key && sort.ascending ? '降序' : '升序'}排列`}
      className={`min-h-11 cursor-pointer whitespace-nowrap rounded px-1 focus-visible:outline-2 focus-visible:outline-sky-500 ${sort.key === key ? 'font-semibold text-sky-700' : 'text-slate-500 hover:text-sky-700'}`}
    >
      {sortLabels[key]} <span aria-hidden="true">{sort.key === key ? (sort.ascending ? '↑' : '↓') : '↕'}</span>
    </button>
  )

  if (error) return <PageState text={error} error />
  if (!data) return <PageState text="加载中..." />

  const newerPeriod = data.filters.annual_periods.at(-1) ?? ''
  const formatPeriod = (period: string) => `${period.slice(0, 4)}年`

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(186,230,253,0.22),transparent_32%),linear-gradient(180deg,#fcfbf8_0%,#f2eee7_100%)] px-4 py-6 text-slate-900 sm:px-6 sm:py-8">
      <StockCopyProvider>
      <div className="mx-auto max-w-7xl space-y-6">
        <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-[2rem] border border-white/80 bg-white/85 p-5 shadow-[0_24px_60px_rgba(15,23,42,0.06)] sm:p-7">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <a href="#" className="text-sm font-medium text-sky-700 hover:text-sky-800">← 返回自选股看板</a>
              <p className="mt-5 text-[11px] font-medium tracking-[0.2em] text-slate-400">GROWTH MARKET SCREENER</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">创业板/科创板小市值股票池</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">创业板与科创板普通股票，总市值低于 {data.filters.total_market_cap_lt_yi} 亿元，最近三个完整年度（{data.filters.annual_periods.map((period) => period.slice(0, 4)).join('、')}）归母净利润均为正，且最新已披露财报累计归母净利润不亏损（≥ 0）。最新财报按年初至报告期末累计口径，52 周位置采用前复权价格计算。</p>
            </div>
            <div className="rounded-[1.4rem] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
              <div>交易日：<span className="font-medium text-slate-900">{data.trade_date}</span></div>
              <div className="mt-1">生成时间：<span className="font-medium text-slate-900">{data.updated_at}</span></div>
              <div className="mt-1">财报截至：<span className="font-medium text-slate-900">{formatDate(data.filters.financial_as_of)}</span></div>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <SummaryCard label="30/688 股票" value={data.summary.growth_market_total} />
            <SummaryCard label="总市值初筛" value={data.summary.market_cap_candidates} />
            <SummaryCard label="连续三年盈利" value={data.summary.profitable_candidates} />
            <SummaryCard label="最新财报不亏损" value={data.summary.latest_report_candidates} />
            <SummaryCard label="最终展示" value={data.rows.filter((row) => !isStStock(row)).length} />
          </div>
        </motion.section>

        <section className="rounded-[2rem] border border-white/80 bg-white/82 p-4 shadow-[0_24px_60px_rgba(15,23,42,0.05)] sm:p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-950">股票榜单</h2>
              <p className="mt-1 text-sm text-slate-500">按{sortLabels[sort.key]}{sort.ascending ? '从低到高' : '从高到低'}排列；点击表头切换排序。52 周位置越接近 100%，当前价格越靠近 52 周高点</p>
              <p className="mt-2 flex items-center gap-1.5 text-xs text-slate-500"><Copy size={12} aria-hidden="true" />点击股票名称或代码即可复制</p>
            </div>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索名称、代码或主营业务" className="w-full rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none transition focus:border-sky-300 focus:ring-4 focus:ring-sky-100 sm:w-72" />
          </div>

          <div className="mt-5 rounded-[1.5rem] border border-slate-200/80">
            <div ref={headerScrollRef} className="sticky top-0 z-30 overflow-hidden rounded-t-[1.5rem] border-b border-slate-200/90 bg-slate-50/95 shadow-[0_8px_20px_rgba(15,23,42,0.06)] backdrop-blur-xl">
              <div className={`${tableGridClass} ${tableWidthClass} items-center px-4 py-4 text-[11px] font-medium tracking-[0.12em] text-slate-400`}>
                <div className="sticky left-0 z-20 self-stretch bg-slate-50/95 py-0.5">#</div><div className="sticky left-[40px] z-20 self-stretch bg-slate-50/95 py-0.5 shadow-[14px_0_18px_rgba(248,250,252,0.98)]">股票</div><div className="text-right">收盘价</div><div className="text-right">今日</div>
                <div className="text-right">{sortButton('total_market_cap_yi')}</div>
                <div className="text-right">{sortButton('distance_ma250_pct')}</div>
                <div className="text-right"><span className="block">{formatPeriod(newerPeriod)}</span>归母净利</div><div className="text-right"><span className="block">最新财报</span>归母净利（累计）</div><div className="text-center">主营业务</div>
                <div className="pr-2 text-center">{sortButton('position_52w_pct')}</div>
              </div>
            </div>
            <div
              className="overflow-x-auto rounded-b-[1.5rem]"
              onScroll={(event) => {
                if (headerScrollRef.current) headerScrollRef.current.scrollLeft = event.currentTarget.scrollLeft
              }}
            >
              <div className={`${tableWidthClass} divide-y divide-slate-100 bg-white`}>
                {rows.map((row, index) => (
                  <div key={row.code} className={`group ${tableGridClass} items-center px-4 py-3.5 text-sm hover:bg-slate-50/80`}>
                    <div className="sticky left-0 z-10 self-stretch bg-white py-0.5 text-xs tabular-nums text-slate-300 group-hover:bg-slate-50">{index + 1}</div>
                    <div className="sticky left-[40px] z-10 self-stretch bg-white py-0.5 shadow-[14px_0_18px_rgba(255,255,255,0.98)] group-hover:bg-slate-50">
                      <CopyStockButton value={row.name} label="股票名称" target={`${row.code}:name`} />
                      <CopyStockButton value={row.code} label="股票代码" target={`${row.code}:code`} secondary />
                      <details className="mt-2 text-xs sm:hidden">
                        <summary className="cursor-pointer py-1 text-sky-700">最新财报</summary>
                        <div className="mt-1 space-y-1 pb-1 text-slate-600">
                          <p>{formatReport(row.latest_report.period)}</p>
                          <p>累计归母 {formatProfit(row.latest_report.net_profit)}</p>
                          <p className="text-[11px]">披露 {formatDate(row.latest_report.ann_date)}</p>
                        </div>
                      </details>
                    </div>
                    <div className="text-right font-medium tabular-nums">{row.close.toFixed(2)}</div>
                    <div className={`text-right font-medium tabular-nums ${row.today_return_pct > 0 ? 'text-emerald-700' : row.today_return_pct < 0 ? 'text-rose-600' : 'text-slate-500'}`}>{formatPct(row.today_return_pct)}</div>
                    <div className="text-right tabular-nums text-slate-700">{row.total_market_cap_yi.toFixed(2)}亿</div>
                    <div className={`text-right font-medium tabular-nums ${metricColorClass(row.distance_ma250_pct)}`}>{formatPct(row.distance_ma250_pct)}</div>
                    <div className="text-right tabular-nums text-slate-600">{formatProfit(row.annual_net_profit[newerPeriod])}</div>
                    <div className="text-right tabular-nums text-slate-600">
                      <div className="font-medium text-slate-800">{formatProfit(row.latest_report.net_profit)}</div>
                      <div className="mt-1 text-xs">{formatReport(row.latest_report.period)}</div>
                      <div className="mt-1 text-[11px] text-slate-400">披露 {formatDate(row.latest_report.ann_date)}</div>
                    </div>
                    <div title={row.main_business || '暂无主营业务信息'} className="overflow-hidden text-xs leading-5 text-slate-600 [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2]">{row.main_business || '—'}</div>
                    <div className="mr-2 rounded-[1rem] border border-sky-100 bg-sky-50/70 px-3 py-2.5">
                      <div className="text-center font-medium tabular-nums text-sky-700">{row.position_52w_pct.toFixed(1)}%</div>
                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200/80"><div className="h-full rounded-full bg-gradient-to-r from-sky-500 to-cyan-400" style={{ width: `${Math.min(Math.max(row.position_52w_pct, 0), 100)}%` }} /></div>
                    </div>
                  </div>
                ))}
                {!rows.length ? <div className="px-5 py-10 text-center text-sm text-slate-400">没有匹配的股票</div> : null}
              </div>
            </div>
          </div>
        </section>
      </div>
      </StockCopyProvider>
    </main>
  )
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return <div className="rounded-[1.4rem] border border-slate-200/80 bg-white p-4"><div className="text-sm text-slate-500">{label}</div><div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{value}</div></div>
}

function PageState({ text, error = false }: { text: string; error?: boolean }) {
  return <main className="flex min-h-screen items-center justify-center bg-slate-50"><div className={`rounded-2xl border px-5 py-4 text-sm ${error ? 'border-rose-200 bg-rose-50 text-rose-600' : 'border-slate-200 bg-white text-slate-600'}`}>{text}</div></main>
}

export default GrowthMarketPage
