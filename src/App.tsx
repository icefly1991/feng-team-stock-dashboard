import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'

type AdjustmentKey = 'qfq' | 'none'
type MetricKey = 'distance_ma250_pct' | 'ytd_return_pct' | 'distance_52w_high_pct'
type SummaryKey = 'watchlist_total' | 'today_up' | 'today_down'

type Row = {
  code: string
  name: string
  close: number
  today_return_pct: number
  distance_ma250_pct: number
  ytd_return_pct: number
  distance_52w_high_pct: number
}

type DashboardData = {
  updated_at: string
  adjustments: Record<AdjustmentKey, { summary: Record<SummaryKey, number>; rows: Row[] }>
}

const tabs: { id: MetricKey; label: string }[] = [
  { id: 'distance_ma250_pct', label: '距年线' },
  { id: 'ytd_return_pct', label: '今年涨跌幅' },
  { id: 'distance_52w_high_pct', label: '距52周高点' },
]

const descendingMetrics: MetricKey[] = ['distance_ma250_pct']

const cards: { key: SummaryKey; label: string; note: string }[] = [
  { key: 'watchlist_total', label: '自选总数', note: '今日跟踪池' },
  { key: 'today_up', label: '今日上涨', note: '收红个股' },
  { key: 'today_down', label: '今日下跌', note: '回撤个股' },
]

const metricText: Record<MetricKey, string> = {
  distance_ma250_pct: '距年线',
  ytd_return_pct: '今年涨跌幅',
  distance_52w_high_pct: '距52周高点',
}

const adjustmentText = { qfq: '前复权', none: '除权' }
const dashboardUrl = `${import.meta.env.BASE_URL}data/dashboard.json`

const descendingBands = [
  { separator: '20%', test: (v: number) => v >= 20 },
  { separator: '0%', test: (v: number) => v >= 0 && v < 20 },
  { separator: '-10%', test: (v: number) => v > -10 && v < 0 },
  { separator: '-20%', test: (v: number) => v <= -10 && v > -20 },
  { separator: null, test: (v: number) => v <= -20 },
] as const

const ascendingBands = [
  { separator: '-20%', test: (v: number) => v <= -20 },
  { separator: '-10%', test: (v: number) => v <= -10 && v > -20 },
  { separator: '0%', test: (v: number) => v > -10 && v < 0 },
  { separator: '20%', test: (v: number) => v >= 0 && v < 20 },
  { separator: null, test: (v: number) => v >= 20 },
] as const

const formatPct = (value: number) => `${value > 0 ? '+' : value < 0 ? '-' : ''}${Math.abs(value).toFixed(1)}%`

const getMetricTextClass = (value: number) =>
  value > 0 ? 'text-emerald-700' : value < 0 ? 'text-rose-600' : 'text-slate-500'

const getActiveMetricCellClass = (metric: MetricKey, activeMetric: MetricKey) =>
  metric === activeMetric
    ? 'mx-auto w-[84%] rounded-[1.1rem] border border-sky-100/90 bg-[linear-gradient(180deg,rgba(249,252,255,0.98),rgba(242,248,252,0.94))] px-3.5 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_8px_24px_rgba(15,23,42,0.06)]'
    : 'w-full px-2 py-2'

function App() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [adjustment, setAdjustment] = useState<AdjustmentKey>('qfq')
  const [tab, setTab] = useState<MetricKey>('distance_ma250_pct')
  const [error, setError] = useState(false)

  useEffect(() => {
    document.title = '每日数据更新'
    let mounted = true
    fetch(dashboardUrl)
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((json: DashboardData) => mounted && setData(json))
      .catch(() => mounted && setError(true))
    return () => {
      mounted = false
    }
  }, [])

  const current = data?.adjustments[adjustment]
  const rows = useMemo(
    () =>
      current
        ? [...current.rows].sort((a, b) =>
            descendingMetrics.includes(tab) ? b[tab] - a[tab] : a[tab] - b[tab],
          )
        : [],
    [current, tab],
  )
  const maxMetric = useMemo(() => Math.max(...rows.map((row) => Math.abs(row[tab])), 1), [rows, tab])
  const groupedRows = useMemo(() => {
    const activeBands = descendingMetrics.includes(tab) ? descendingBands : ascendingBands
    return activeBands.map((band) => ({ ...band, rows: rows.filter((row) => band.test(row[tab])) }))
  }, [rows, tab])
  const tableGridClass = 'grid grid-cols-[4%_16%_11%_11%_12%_12%_28%] gap-[1%]'
  const displayGroups = useMemo(
    () => (tab === 'distance_52w_high_pct' ? [{ separator: null, rows }] : groupedRows),
    [groupedRows, rows, tab],
  )

  if (error || (data && !current)) return <StateView text="无法加载 /data/dashboard.json" error />
  if (!data || !current) return <StateView text="加载中..." />

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(186,230,253,0.2),transparent_30%),linear-gradient(180deg,#fcfbf8_0%,#f5f1ea_58%,#f1ece5_100%)] px-4 py-6 text-slate-900 sm:px-6 sm:py-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="relative overflow-hidden rounded-[2rem] border border-white/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.97),rgba(247,242,234,0.94))] p-5 shadow-[0_24px_60px_rgba(15,23,42,0.06)] sm:p-7">
          <div className="absolute inset-x-0 top-0 h-28 bg-[radial-gradient(circle_at_top,rgba(191,219,254,0.32),transparent_72%)]" />
          <div className="absolute right-[-5rem] top-[-5rem] h-40 w-40 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.95),rgba(255,255,255,0))]" />
          <div className="relative flex flex-col gap-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <div className="inline-flex rounded-full border border-slate-200/80 bg-white/80 px-3 py-1 text-[11px] font-medium tracking-[0.22em] text-slate-500">DAILY MARKET SNAPSHOT</div>
                <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl lg:text-5xl">每日数据更新</h1>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">每个交易日下午 4:30 后更新数据。</p>
                <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
                  <span className="rounded-full border border-slate-200 bg-white/85 px-3 py-1">实时生成静态看板</span>
                  <span className="rounded-full border border-slate-200 bg-white/70 px-3 py-1">按指标排序浏览</span>
                  <span className="rounded-full border border-slate-200 bg-white/70 px-3 py-1">支持前复权 / 除权</span>
                </div>
              </div>
              <div className="rounded-[1.4rem] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(255,255,255,0.72))] px-4 py-3 text-sm text-slate-600 shadow-[0_10px_30px_rgba(15,23,42,0.05)] backdrop-blur">
                <div className="text-[11px] font-medium tracking-[0.16em] text-slate-400">LAST REFRESH</div>
                <div className="mt-1 text-sm font-medium text-slate-900">更新时间：{data.updated_at}</div>
              </div>
            </div>

            <div className="rounded-[1.6rem] border border-slate-200/80 bg-white/70 p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
              <div className="grid grid-cols-2 gap-1">
                {(['qfq', 'none'] as const).map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setAdjustment(key)}
                    className={`rounded-[1.2rem] px-4 py-3 text-sm font-medium transition ${adjustment === key ? 'bg-white text-slate-950 shadow-[0_8px_18px_rgba(15,23,42,0.08)]' : 'text-slate-500 hover:bg-white/60'}`}
                  >
                    {adjustmentText[key]}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 rounded-[1.6rem] border border-slate-200/80 bg-white/65 px-4 py-3 text-sm text-slate-600">
              <div>当前口径：<span className="font-medium text-slate-900">{adjustmentText[adjustment]}</span>，下方榜单与汇总数据已同步切换。</div>
              <div className="rounded-full bg-slate-900 px-3 py-1 text-[11px] font-medium tracking-[0.14em] text-white">FOCUS MODE</div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {cards.map((card, index) => (
                <motion.div key={card.key} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 + index * 0.06, duration: 0.3 }} className="rounded-[1.75rem] border border-white/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,245,239,0.95))] p-5 shadow-[0_18px_40px_rgba(15,23,42,0.05)]">
                  <p className="text-sm text-slate-500">{card.label}</p>
                  <p className="mt-4 text-4xl font-semibold tracking-tight text-slate-950">{current.summary[card.key]}</p>
                  <p className="mt-3 text-sm text-slate-500">{card.note}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </motion.section>

        <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08, duration: 0.35 }} className="rounded-[2rem] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.82),rgba(250,250,248,0.78))] p-5 shadow-[0_24px_60px_rgba(15,23,42,0.05)] backdrop-blur-sm sm:p-6">
          <div className="sticky top-0 z-40 -mx-1 pb-1 backdrop-blur-xl">
            <div className="overflow-x-auto">
              <div className="flex min-w-max gap-2 px-1">
              {tabs.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setTab(item.id)}
                  className={`rounded-full border px-4 py-2.5 text-sm font-medium transition ${tab === item.id ? 'border-slate-300/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(246,247,249,0.92))] text-slate-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_8px_22px_rgba(15,23,42,0.08)]' : 'border-slate-200/80 bg-white/72 text-slate-600 hover:border-slate-300/80 hover:bg-white/90'}`}
                >
                  {item.label}
                </button>
              ))}
              </div>
            </div>
          </div>

          <div className="mt-5 rounded-[1.85rem] border border-slate-200/75 bg-[linear-gradient(180deg,rgba(255,255,255,0.95),rgba(248,247,244,0.92))] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.9),0_18px_44px_rgba(15,23,42,0.04)] sm:p-5">
            <div className="-mx-4 -mt-4 mb-5 border-b border-slate-200/60 bg-[rgba(255,255,255,0.72)] px-4 py-4 backdrop-blur-xl sm:-mx-5 sm:-mt-5 sm:px-5 sm:py-5">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold tracking-tight text-slate-950">{metricText[tab]}榜单</h2>
                <p className="mt-1 text-sm text-slate-600">当前展示基于 {adjustmentText[adjustment]} 口径排序</p>
              </div>
              <div className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-500">{tab === 'distance_52w_high_pct' ? '连续排序视图' : '可视化榜单'}</div>
              </div>
            </div>

            <div className="mt-5 overflow-visible rounded-[1.5rem] border border-slate-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(250,250,249,0.9))] shadow-[inset_0_1px_0_rgba(255,255,255,0.92)]">
              <div className="min-w-[960px]">
                <div className={`sticky top-[72px] z-40 ${tableGridClass} min-h-[108px] border-b border-slate-200/85 bg-[#fcfcfb] px-4 py-3.5 text-[11px] font-medium tracking-[0.18em] text-slate-400 shadow-[0_10px_24px_rgba(15,23,42,0.06)]`}>
                  <div className="flex items-center justify-center">
                    <span className="text-[10px] text-slate-300">#</span>
                  </div>
                  <div className="flex -translate-x-1 items-center justify-center px-2 text-center">
                    <span>股票</span>
                  </div>
                  <div className="flex items-center justify-end px-2">
                    <span>收盘价</span>
                  </div>
                  <div className="flex items-center justify-end px-2">
                    <span>今日</span>
                  </div>
                  <div className={`${tab === 'distance_ma250_pct' ? 'hidden' : 'flex'} items-center justify-end px-2`}>
                    <span>距年线</span>
                  </div>
                  <div className={`${tab === 'ytd_return_pct' ? 'hidden' : 'flex'} translate-x-1 items-center justify-self-center px-2 text-center`}>
                    <span>YTD</span>
                  </div>
                  <div className={`${tab === 'distance_52w_high_pct' ? 'hidden' : 'flex'} items-center justify-end px-2`}>
                    <span>52周高点</span>
                  </div>
                  <div className="flex items-center justify-center px-2 text-slate-700">
                    <span>{metricText[tab]}</span>
                  </div>
                </div>

                <div className="space-y-3 px-3 py-3">
                  {displayGroups.map((group, groupIndex) => (
                    <div key={group.separator ?? `all-${groupIndex}`} className="space-y-2">
                      {group.rows.length ? (
                        <>
                          {group.rows.map((row) => {
                          const index = rows.findIndex((item) => item.code === row.code) + 1
                          return (
                            <div key={`${adjustment}-${group.separator ?? 'all'}-${row.code}`} className={`${tableGridClass} items-center rounded-[1.2rem] border border-slate-200/60 bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(250,250,248,0.88))] px-4 py-3.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)] transition hover:border-slate-300/75 hover:bg-white hover:shadow-[0_12px_30px_rgba(15,23,42,0.05)]`}>
                              <div className="sticky left-0 z-10 flex justify-center bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(250,250,248,0.88))]">
                                <p className="text-[11px] font-medium tabular-nums text-slate-300">{index}</p>
                              </div>

                              <div className="sticky left-[5%] z-10 min-w-0 rounded-[0.95rem] pr-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(250,250,248,0.88))] shadow-[14px_0_22px_rgba(250,250,249,0.98)]">
                                <div className="min-w-0 rounded-[0.95rem] px-3 py-2">
                                  <p className="truncate text-[15px] font-medium tracking-[-0.01em] text-slate-900">{row.name}</p>
                                  <p className="mt-0.5 text-[12px] font-medium tracking-[0.08em] text-slate-400">{row.code}</p>
                                </div>
                              </div>

                              <div className="px-2 text-right text-[15px] font-medium tabular-nums text-slate-900">{row.close.toFixed(1)}</div>
                              <div className={`px-2 text-right text-[13px] font-medium tabular-nums ${getMetricTextClass(row.today_return_pct)}`}>{formatPct(row.today_return_pct)}</div>

                              <div className={`${tab === 'distance_ma250_pct' ? 'hidden' : 'block'} px-2 text-right text-[13px] tabular-nums py-2`}>
                                <div className="flex items-center justify-end gap-3">
                                  <span className={`font-medium ${getMetricTextClass(row.distance_ma250_pct)}`}>{formatPct(row.distance_ma250_pct)}</span>
                                </div>
                              </div>

                              <div className={`${tab === 'ytd_return_pct' ? 'hidden' : 'block'} px-2 text-right text-[13px] tabular-nums py-2`}>
                                <div className="flex items-center justify-end gap-3">
                                  <span className={`font-medium ${getMetricTextClass(row.ytd_return_pct)}`}>{formatPct(row.ytd_return_pct)}</span>
                                </div>
                              </div>

                              <div className={`${tab === 'distance_52w_high_pct' ? 'hidden' : 'block'} px-2 text-right text-[13px] tabular-nums py-2`}>
                                <div className="flex items-center justify-end gap-3">
                                  <span className={`font-medium ${getMetricTextClass(row.distance_52w_high_pct)}`}>{formatPct(row.distance_52w_high_pct)}</span>
                                </div>
                              </div>

                              <div className="px-2">
                                <div className={`text-center text-[13px] tabular-nums ${getActiveMetricCellClass(tab, tab)}`}>
                                  <div className="flex items-center justify-center gap-3">
                                    <span className={`font-medium ${getMetricTextClass(row[tab])}`}>{formatPct(row[tab])}</span>
                                  </div>
                                  <div className="mt-2 h-[6px] w-full overflow-hidden rounded-full bg-slate-200/70">
                                    <div
                                      className={`h-full rounded-full ${row[tab] >= 0 ? 'bg-[linear-gradient(90deg,rgba(16,185,129,0.72),rgba(52,211,153,0.92))]' : 'bg-[linear-gradient(90deg,rgba(245,158,11,0.72),rgba(251,191,36,0.92))]'}`}
                                      style={{ width: `${(Math.abs(row[tab]) / maxMetric) * 100}%` }}
                                    />
                                  </div>
                                </div>
                              </div>
                            </div>
                          )
                        })}
                          {group.separator ? (
                            <div className="flex items-center gap-2 px-1 pt-1.5">
                              <div className="flex items-center gap-2 text-[11px] font-medium tabular-nums tracking-[0.14em] text-slate-300">
                                <span className="h-px w-3 bg-slate-300" />
                                <span>{group.separator}</span>
                              </div>
                              <div className="h-px flex-1 bg-slate-200/90" />
                            </div>
                          ) : null}
                        </>
                      ) : (
                        <div className="px-1 py-2 text-sm text-slate-400">这个区间暂无股票</div>
                      )}
                    </div>
                  ))}
                  </div>
                </div>
              </div>
            </div>
        </motion.section>
      </div>
    </main>
  )
}

function StateView({ text, error = false }: { text: string; error?: boolean }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[linear-gradient(180deg,#fcfbf8_0%,#f5f1ea_100%)] px-4">
      <div className={`rounded-[1.6rem] border px-5 py-4 text-sm shadow-[0_16px_40px_rgba(15,23,42,0.05)] ${error ? 'border-rose-200 bg-rose-50 text-rose-600' : 'border-slate-200 bg-white text-slate-600'}`}>{text}</div>
    </main>
  )
}

export default App
