import BusinessCell from './BusinessCell'
import { useEffect, useMemo, useRef, useState } from 'react'
import { CopyStockButton, StockCopyProvider } from './StockCopy'
import { StockHistoryCode, StockHistoryProvider } from './StockHistoryPreview'
import { ShareholderBadge, ShareholderProvider } from './ShareholderWatch'
import { compareStockValues } from './stockSort'
import { SectorCell, SectorFilter } from './StockSectors'
import { matchesSector, useStockSectors } from './useStockSectors'
import { isBeijingStock, smallCapVisible } from './smallCapVisibility'

type Row = {
  code: string; ts_code: string; name: string; market: string; industry: string; main_business: string; market_cap_rank: number
  main_business_keywords?: string[]
  total_market_cap_yi: number; close: number | null; today_return_pct: number | null
  distance_ma250_pct: number | null; position_52w_pct: number | null
  annual_periods: string[]; annual_net_profit: Record<string, number | null>; annual_ann_dates: Record<string, string | null>
  latest_report: { period: string; ann_date: string; net_profit: number | null } | null
  loss_status: 'loss' | 'no_loss' | 'unknown'; loss_reasons: string[]; financial_complete: boolean
  avg_range_60d_pct: number | null; large_move_60d_days?: number; avg_amount_60d_yi: number | null; activity_note?: string
}
type Data = {
  schema_version: number; trade_date: string; updated_at: string; financial_as_of: string; adjustment: string
  filters: { include_st: boolean; include_bj: boolean; target: number }
  summary: { universe: number; selected: number }; rows: Row[]
  screened: { target: number; include_st: boolean; universe: number; checked: number; rows: Row[] }
  errors?: { code: string; stage: string; error: string }[]
}
type SortKey = 'total_market_cap_yi' | 'distance_ma250_pct' | 'position_52w_pct' | 'avg_range_60d_pct'
const labels: Record<SortKey, string> = { total_market_cap_yi: '总市值', distance_ma250_pct: '距年线', position_52w_pct: '52周内位置', avg_range_60d_pct: '60日活跃度' }
const number = (v: number | null | undefined) => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(2) : '—'
const pct = (v: number | null | undefined) => v == null ? '—' : `${number(v)}%`
const profit = (v: number | null | undefined) => v == null ? '—' : `${number(v / 100_000_000)}亿`
const date = (v: string | null | undefined) => v ? `${v.slice(0, 4)}-${v.slice(4, 6)}-${v.slice(6, 8)}` : '—'
const grid = 'grid grid-cols-[28px_112px_132px_52px_56px_72px_64px_100px_120px_minmax(104px,1fr)_100px_136px] gap-3 items-center px-4 [&>div]:min-w-0'
const width = 'min-w-[1240px] w-full'

function validate(data: Data) {
  if (data.schema_version !== 2 || data.adjustment !== 'qfq' || !/^\d{8}$/.test(data.trade_date) ||
      !/^\d{8}$/.test(data.financial_as_of) || data.filters?.target !== 250 || !Array.isArray(data.rows) || data.rows.length !== 250 ||
      data.summary?.selected !== 250 || new Set(data.rows.map(r => r.code)).size !== 250 ||
      data.rows.some((r, i) => !/^\d{6}$/.test(r.code) || !Number.isFinite(r.total_market_cap_yi) || r.total_market_cap_yi <= 0 ||
        r.market_cap_rank !== i + 1 || (i > 0 && compareStockValues(data.rows[i - 1], r, data.rows[i - 1].total_market_cap_yi, r.total_market_cap_yi, true) > 0) ||
        !/^\d{6}\.(SH|SZ|BJ)$/.test(r.ts_code) || !['loss', 'no_loss', 'unknown'].includes(r.loss_status) || !Array.isArray(r.annual_periods) || !Array.isArray(r.loss_reasons)) ||
      data.screened?.target !== 100 || data.screened.include_st !== false || !Array.isArray(data.screened.rows) || data.screened.rows.length !== 100 ||
      new Set(data.screened.rows.map(r => r.code)).size !== 100 || data.screened.rows.some((r, i) =>
        !/^\d{6}$/.test(r.code) || !/^\d{6}\.(SH|SZ)$/.test(r.ts_code) || /ST/i.test(r.name) || r.loss_status !== 'no_loss' || !r.financial_complete ||
        !Number.isFinite(r.total_market_cap_yi) || r.total_market_cap_yi <= 0 || r.market_cap_rank !== i + 1 ||
        (i > 0 && compareStockValues(data.screened.rows[i - 1], r, data.screened.rows[i - 1].total_market_cap_yi, r.total_market_cap_yi, true) > 0))) {
    throw new Error('小市值双榜数据未就绪，请更新数据后重试')
  }
}

export default function SmallCapMarketPage() {
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [showLosses, setShowLosses] = useState(false)
  const [showBeijing, setShowBeijing] = useState(false)
  const [mode, setMode] = useState<'screened' | 'all'>('screened')
  const [sector, setSector] = useState('')
  const sectors = useStockSectors()
  const [sort, setSort] = useState<{ key: SortKey; ascending: boolean }>({ key: 'total_market_cap_yi', ascending: true })
  const header = useRef<HTMLDivElement>(null)
  const tableScroll = useRef<HTMLDivElement>(null)
  const [scrollState, setScrollState] = useState({ left: false, right: false })
  const updateScrollState = () => {
    const element = tableScroll.current
    if (element) setScrollState({ left: element.scrollLeft > 1, right: element.scrollLeft + element.clientWidth < element.scrollWidth - 1 })
  }
  useEffect(() => {
    const element = tableScroll.current
    if (!element) return
    const observer = new ResizeObserver(() => {
      setScrollState({ left: element.scrollLeft > 1, right: element.scrollLeft + element.clientWidth < element.scrollWidth - 1 })
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [data])
  useEffect(() => {
    document.title = mode === 'screened' ? '沪深非亏损小市值榜' : '全A股最低市值250榜'
  }, [mode])
  useEffect(() => {
    let live = true
    fetch(`${import.meta.env.BASE_URL}data/small-cap-dashboard.json`).then(async response => {
      if (!response.ok) throw new Error('最低市值250榜单尚未生成，请更新数据后重试')
      const json: Data = await response.json()
      validate(json)
      if (live) setData(json)
    }).catch((e: unknown) => { if (live) setError(e instanceof Error ? e.message : '无法加载榜单') })
    return () => { live = false }
  }, [])
  const poolRows = mode === 'screened' ? data?.screened.rows : data?.rows
  const matchedRows = useMemo(() => (poolRows ?? [])
    .filter(r => `${r.code} ${r.name} ${r.main_business} ${(r.main_business_keywords ?? []).join(' ')} ${r.industry}`.toLowerCase().includes(query.trim().toLowerCase()))
    .filter(r => matchesSector(sectors.data, r.code, sector)), [poolRows, query, sector, sectors.data])
  const rows = useMemo(() => matchedRows.filter(r => mode === 'screened' || smallCapVisible(r, showLosses, showBeijing))
    .sort((a, b) => compareStockValues(a, b, a[sort.key], b[sort.key], sort.ascending)), [matchedRows, sort, showLosses, showBeijing, mode])
  const hiddenBeijingCount = showBeijing ? 0 : matchedRows.filter(isBeijingStock).length
  const hiddenLossCount = showLosses ? 0 : matchedRows.filter(r => r.loss_status === 'loss' && (showBeijing || !isBeijingStock(r))).length
  const changeMode = (next: 'screened' | 'all') => {
    setMode(next); setQuery(''); setSector(''); setShowLosses(true); setShowBeijing(true)
    setSort({ key: 'total_market_cap_yi', ascending: true })
    tableScroll.current?.scrollTo({ left: 0 })
  }
  const sortButton = (key: SortKey) => <button type="button" onClick={() => setSort(s => ({ key, ascending: s.key === key ? !s.ascending : key !== 'avg_range_60d_pct' }))}
    className={`min-h-11 rounded px-1 focus-visible:outline-2 focus-visible:outline-sky-500 ${sort.key === key ? 'font-semibold text-sky-700' : 'text-slate-500'}`}
    aria-label={`${labels[key]}排序${sort.key === key ? (sort.ascending ? '，当前升序' : '，当前降序') : ''}`}>
    {labels[key]} {sort.key === key ? (sort.ascending ? '↑' : '↓') : '↕'}</button>

  return <main className="min-h-screen bg-[#f7f5f0] px-3 py-6 text-slate-900 sm:px-6"><StockCopyProvider><ShareholderProvider><StockHistoryProvider>
    <div className="mx-auto max-w-[1440px] space-y-5">
      <nav className="flex flex-wrap gap-4 text-sm text-sky-700"><a href="#">← 自选股看板</a><a href="#growth-market">创业板/科创板小市值股票池</a></nav>
      <section className="rounded-3xl border border-white bg-white/90 p-5 shadow-sm sm:p-7">
        <p className="text-xs tracking-widest text-slate-400">SMALL-CAP · {mode === 'screened' ? 'SHANGHAI / SHENZHEN 100' : 'ALL A-SHARES 250'}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">{mode === 'screened' ? '沪深非亏损小市值榜' : '全A股最低市值250榜'}</h1>
        <div className="mt-4 flex flex-wrap gap-2" aria-label="榜单模式">
          {([['screened', '沪深非亏损100只'], ['all', '全A股最低市值250只']] as const).map(([key, label]) => <button key={key} type="button" aria-pressed={mode === key} onClick={() => changeMode(key)} className={`min-h-11 rounded-full border px-4 py-2 text-sm ${mode === key ? 'border-sky-600 bg-sky-600 text-white' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'}`}>{label}</button>)}
        </div>
        <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-600">{mode === 'screened' ? '先排除北交所、ST/*ST、已确认亏损及财报不完整的公司，再从全沪深A股按总市值取最低100只；零利润可入选，不受全市场前250名限制。' : '按全沪深北总市值选最低250只，包含北交所、ST/*ST及亏损公司；可独立隐藏北交所或亏损股，仍保留全榜排名。'} 最近三个已披露完整年度或最新累计财报任一归母净利润为负则标记亏损，财报不全时单独提示。</p>
        {data && <>
          <p className="mt-3 text-xs leading-6 text-slate-500">{mode === 'all' && data.filters.include_bj ? '沪深北 A 股' : '沪深 A 股'} · {mode === 'all' && data.filters.include_st ? '包含 ST / *ST' : '排除 ST / *ST'} · 行情 {date(data.trade_date)} · 财报截至 {date(data.financial_as_of)} · 生成 {data.updated_at}（北京时间）· Tushare · 前复权</p>
          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {([['榜单股票', poolRows!.length], [mode === 'screened' ? '已核查沪深股票' : '亏损公司', mode === 'screened' ? data.screened.checked : data.rows.filter(r => r.loss_status === 'loss').length], ['财报待核实', poolRows!.filter(r => !r.financial_complete).length], [mode === 'screened' ? '第100名总市值' : '第250名总市值', `${number(poolRows![poolRows!.length - 1].total_market_cap_yi)}亿`]] as const).map(([label, value]) => <div key={label} className="rounded-2xl bg-slate-50 p-4"><div className="text-xs text-slate-500">{label}</div><div className="mt-2 text-2xl font-semibold tabular-nums">{value}</div></div>)}
          </div>
          {!!data.errors?.length && <p className="mt-3 text-sm text-amber-700">{mode === 'screened' ? '核查中财报未能确认的公司不进入默认榜；已入选股票的业务或行情缺失项显示“—”。' : '部分财报、主营业务或行情未能获取，仍保留原市值排名；缺失项显示“—”。'}</p>}
        </>}
        <details className="mt-4 text-sm leading-6 text-slate-600"><summary className="cursor-pointer text-sky-700">活跃度怎么看？</summary>
          <p className="mt-2">近60个交易日平均真实波幅：每日取“最高价−最低价、最高价与昨收差的绝对值、最低价与昨收差的绝对值”的最大值，除以昨收，再取60日平均。越高说明日常波动越大，包含跳空影响。</p>
          <p>同时显示单日绝对涨跌≥3%的天数和日均成交额。点击活跃度按波幅排序；波幅衡量价格变化，成交额衡量交易热度，不合成主观评分。近60日有停牌或历史不足时不比较活跃度；年线及52周历史不足时显示“—”。</p>
        </details>
      </section>
      {error ? <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-700">{error}</div> : !data ? <p role="status" className="p-6 text-center text-slate-500">正在加载榜单…</p> :
      <section className="rounded-3xl bg-white p-4 shadow-sm sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold">股票榜单</h2><p className="mt-2 text-xs text-slate-500">按{labels[sort.key]}{sort.ascending ? '从低到高' : '从高到低'}；# {mode === 'screened' ? '为沪深非亏损筛选后的市值排名' : '保留全市场250名市值排名'}。名称/代码可复制，图表按钮可查看K线。</p></div>
          <input aria-label="搜索最低市值股票" value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索名称、代码、主营业务" className="w-full rounded-full border border-slate-200 px-4 py-2.5 text-sm sm:w-72" /></div>
        {mode === 'all' ? <div className="mt-4 flex flex-wrap items-center gap-3">
          <button type="button" aria-pressed={showLosses} onClick={() => setShowLosses(value => !value)} className="min-h-11 rounded-full border border-rose-200 px-4 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50 focus-visible:outline-2 focus-visible:outline-rose-500">{showLosses ? '隐藏亏损股' : '显示亏损股'}</button>
          <button type="button" aria-pressed={showBeijing} onClick={() => setShowBeijing(value => !value)} className="min-h-11 rounded-full border border-sky-200 px-4 py-2 text-sm font-medium text-sky-700 hover:bg-sky-50 focus-visible:outline-2 focus-visible:outline-sky-500">{showBeijing ? '隐藏北交所股票' : '显示北交所股票'}</button>
          <p role="status" className="text-xs text-slate-500">显示 {rows.length} 只{!showBeijing && ` · 已隐藏 ${hiddenBeijingCount} 只北交所股票`}{!showLosses && ` · 已隐藏 ${hiddenLossCount} 只亏损股`}；隐藏数量不重复计算，# 保留全榜250只市值排名</p>
        </div> : <p role="status" className="mt-4 text-xs text-slate-500">显示 {rows.length} / 100 只；已排除北交所、ST/*ST、亏损及财报不完整公司</p>}
        <SectorFilter data={sectors.data} error={sectors.error} codes={(poolRows ?? []).map(r => r.code)} value={sector} onChange={setSector} />
        {(scrollState.left || scrollState.right) && <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span>表格可左右滑动</span>
          <button type="button" disabled={!scrollState.left} onClick={() => tableScroll.current?.scrollTo({ left: 0 })} className="min-h-11 rounded-lg border border-slate-200 px-3 text-sky-700 disabled:opacity-40">← 返回股票列</button>
          <button type="button" disabled={!scrollState.right} onClick={() => tableScroll.current?.scrollTo({ left: tableScroll.current.scrollWidth })} className="min-h-11 rounded-lg border border-slate-200 px-3 text-sky-700 disabled:opacity-40">查看活跃度 →</button>
        </div>}
        <div className="mt-5 rounded-2xl border border-slate-200">
          <div ref={header} className="sticky top-0 z-30 overflow-hidden rounded-t-2xl border-b border-slate-200 bg-slate-50">
            <div className={`${grid} ${width} py-3 text-xs`}><div className="sticky left-0 z-20 bg-slate-50">#</div><div className="sticky left-[40px] z-20 bg-slate-50 shadow-[-12px_0_0_#f8fafc]">股票</div><div>所属板块</div><div className="text-right">收盘价</div><div className="text-right">今日</div><div className="text-right">{sortButton('total_market_cap_yi')}</div><div className="text-right">{sortButton('distance_ma250_pct')}</div><div className="text-right">最新年报归母净利</div><div className="text-right">最新财报归母净利（累计）</div><div>主营业务</div><div className="text-center">{sortButton('position_52w_pct')}</div><div className="text-right">{sortButton('avg_range_60d_pct')}</div></div>
          </div>
          <div ref={tableScroll} tabIndex={0} aria-label="股票榜单，可左右滚动查看全部列" className="overflow-x-auto rounded-b-2xl" onScroll={e => { if (header.current) header.current.scrollLeft = e.currentTarget.scrollLeft; updateScrollState() }}>
            <div className={`${width} divide-y divide-slate-100`}>
              {rows.map(row => <div key={row.code} className={`group ${grid} py-4 text-sm hover:bg-slate-50`}>
                <div className="sticky left-0 z-10 self-stretch bg-white text-xs text-slate-400 group-hover:bg-slate-50">{row.market_cap_rank}</div>
                <div className="sticky left-[40px] z-10 self-stretch bg-white shadow-[-12px_0_0_white,12px_0_14px_white] group-hover:bg-slate-50">
                  <CopyStockButton value={row.name} label="股票名称" target={`${row.code}:name`} textClassName={row.loss_status === 'loss' ? 'font-medium text-rose-600' : undefined} />
                  <StockHistoryCode code={row.code} name={row.name} tradeDate={data.trade_date} source="small-cap"><CopyStockButton value={row.code} label="股票代码" target={`${row.code}:code`} secondary textClassName={row.loss_status === 'loss' ? 'text-xs tracking-wider text-rose-600' : undefined} /></StockHistoryCode>
                  <p className="mt-1 text-[11px] text-slate-400">{row.market}{row.name.toUpperCase().includes('ST') ? ' · ST风险' : ''}{row.name.includes('退') ? ' · 退市风险' : ''}</p>
                  {row.loss_status === 'loss' && <p title={row.loss_reasons.join('；')} className="mt-1 text-xs font-medium text-rose-600">亏损公司</p>}
                  {!row.financial_complete && <p className="mt-1 text-xs text-amber-700">财报待核实</p>}
                  <ShareholderBadge code={row.code} />
                </div>
                <SectorCell data={sectors.data} code={row.code} onSelect={setSector} />
                <div className="text-right tabular-nums">{number(row.close)}</div><div className={`text-right tabular-nums ${row.today_return_pct != null && row.today_return_pct < 0 ? 'text-rose-600' : 'text-slate-600'}`}>{pct(row.today_return_pct)}</div>
                <div className="text-right tabular-nums">{number(row.total_market_cap_yi)}亿</div><div className="text-right tabular-nums">{pct(row.distance_ma250_pct)}</div>
                <div className="text-right tabular-nums"><p>{profit(row.annual_net_profit[row.annual_periods[2]])}</p><p className="mt-1 text-xs text-slate-400">{row.annual_periods[2]?.slice(0, 4) ?? '—'}年</p>
                  <details className="mt-2 text-xs"><summary className="cursor-pointer py-1 text-sky-700">财报依据</summary><div className="space-y-2 py-2 text-left leading-5 text-slate-600">{row.loss_reasons.map(reason => <p key={reason} className="break-words text-rose-600">{reason}</p>)}{row.annual_periods.map(p => <p key={p}>{p.slice(0, 4)}年：{profit(row.annual_net_profit[p])}<br />披露 {date(row.annual_ann_dates[p])}</p>)}{row.latest_report ? <p>最新累计：{profit(row.latest_report.net_profit)}<br />报告期 {date(row.latest_report.period)}<br />披露 {date(row.latest_report.ann_date)}</p> : <p>最新财报暂无数据</p>}</div></details>
                </div>
                <div className="text-right tabular-nums"><p>{profit(row.latest_report?.net_profit)}</p><p className="mt-1 text-xs text-slate-400">报告期 {date(row.latest_report?.period)}</p><p className="mt-1 text-[11px] text-slate-400">披露 {date(row.latest_report?.ann_date)}</p></div>
                <BusinessCell text={row.main_business} keywords={row.main_business_keywords} sectors={sectors.data} code={row.code} onSelect={setSector} />
                <div className="rounded-xl bg-sky-50 p-3 text-center tabular-nums text-sky-700">{pct(row.position_52w_pct)}<div className="mt-2 h-1.5 rounded-full bg-slate-200"><div className="h-full rounded-full bg-sky-500" style={{ width: `${Math.max(0, Math.min(100, row.position_52w_pct ?? 0))}%` }} /></div></div>
                <div className="text-right tabular-nums"><p className="font-semibold text-sky-700">波幅 {pct(row.avg_range_60d_pct)}</p><p title="单日绝对涨跌至少3%的天数" className="mt-1 text-xs text-slate-500">≥3%：{row.large_move_60d_days ?? '—'}/60天</p><p title="近60个交易日日均成交额" className="mt-1 text-xs text-slate-500">日均 {row.avg_amount_60d_yi == null ? '—' : `${number(row.avg_amount_60d_yi)}亿`}</p>{row.activity_note && <p className="mt-1 text-[11px] text-amber-700">{row.activity_note}</p>}</div>
              </div>)}
              {!rows.length && <p className="p-8 text-center text-slate-400">{matchedRows.length ? `匹配的股票已被隐藏，请按需打开${!showBeijing && hiddenBeijingCount ? '“显示北交所股票”' : ''}${!showBeijing && hiddenBeijingCount && !showLosses && matchedRows.some(r => r.loss_status === 'loss') ? '和' : ''}${!showLosses && matchedRows.some(r => r.loss_status === 'loss') ? '“显示亏损股”' : ''}查看` : '没有匹配的股票'}</p>}
            </div>
          </div>
        </div>
      </section>}
    </div>
  </StockHistoryProvider></ShareholderProvider></StockCopyProvider></main>
}
