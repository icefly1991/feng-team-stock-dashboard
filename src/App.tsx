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
const cards: { key: SummaryKey; label: string; note: string }[] = [
  { key: 'watchlist_total', label: '自选总数', note: '今日跟踪池' },
  { key: 'today_up', label: '今日上涨', note: '收红个股' },
  { key: 'today_down', label: '今日下跌', note: '回撤个股' },
]
const metricText = {
  distance_ma250_pct: '距年线',
  ytd_return_pct: '今年涨跌幅',
  distance_52w_high_pct: '距52周高点',
}
const adjustmentText = { qfq: '前复权', none: '除权' }
const formatPct = (value: number) => `${value.toFixed(1)}%`
const dashboardUrl = `${import.meta.env.BASE_URL}data/dashboard.json`
const bands = [
  { label: '上涨 20% 以上', test: (v: number) => v >= 20 },
  { label: '上涨 10% 至 20%', test: (v: number) => v >= 10 && v < 20 },
  { label: '区间 -10% 至 10%', test: (v: number) => v > -10 && v < 10 },
  { label: '下跌 10% 至 20%', test: (v: number) => v <= -10 && v > -20 },
  { label: '下跌 20% 以上', test: (v: number) => v <= -20 },
] as const

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
  const rows = useMemo(() => (current ? [...current.rows].sort((a, b) => b[tab] - a[tab]) : []), [current, tab])
  const maxMetric = useMemo(() => Math.max(...rows.map((row) => Math.abs(row[tab])), 1), [rows, tab])
  const groupedRows = useMemo(() => bands.map((band) => ({ ...band, rows: rows.filter((row) => band.test(row[tab])) })), [rows, tab])

  if (error || (data && !current)) return <StateView text="无法加载 /data/dashboard.json" error />
  if (!data || !current) return <StateView text="加载中..." />

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#fcfbf8_0%,#f5f1ea_100%)] px-4 py-6 text-slate-900 sm:px-6 sm:py-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="overflow-hidden rounded-[2rem] border border-white/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.96),rgba(247,242,234,0.94))] p-5 shadow-[0_24px_60px_rgba(15,23,42,0.06)] sm:p-7">
          <div className="absolute inset-x-0 top-0 h-28 bg-[radial-gradient(circle_at_top,rgba(191,219,254,0.32),transparent_72%)]" />
          <div className="relative flex flex-col gap-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <div className="inline-flex rounded-full border border-slate-200/80 bg-white/80 px-3 py-1 text-[11px] font-medium tracking-[0.22em] text-slate-500">DAILY MARKET SNAPSHOT</div>
                <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl lg:text-5xl">每日数据更新</h1>
                <p className="mt-3 text-sm leading-6 text-slate-600 sm:text-base">更清爽的轻量看板视图，保留原有口径、标签和排序逻辑，只优化阅读体验。</p>
              </div>
              <div className="rounded-[1.4rem] border border-white/80 bg-white/80 px-4 py-3 text-sm text-slate-600 shadow-[0_10px_30px_rgba(15,23,42,0.05)]">更新时间：{data.updated_at}</div>
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

            <div className="rounded-[1.6rem] border border-slate-200/80 bg-white/65 px-4 py-3 text-sm text-slate-600">当前口径：<span className="font-medium text-slate-900">{adjustmentText[adjustment]}</span>，下方榜单与汇总数据已同步切换。</div>

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

        <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08, duration: 0.35 }} className="rounded-[2rem] border border-white/80 bg-white/78 p-5 shadow-[0_24px_60px_rgba(15,23,42,0.05)] backdrop-blur-sm sm:p-6">
          <div className="-mx-1 overflow-x-auto pb-1">
            <div className="flex min-w-max gap-2 px-1">
              {tabs.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setTab(item.id)}
                  className={`rounded-full border px-4 py-2.5 text-sm font-medium transition ${tab === item.id ? 'border-slate-300 bg-slate-900 text-white shadow-[0_10px_24px_rgba(15,23,42,0.12)]' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-5 rounded-[1.75rem] border border-slate-200/80 bg-[linear-gradient(180deg,#ffffff_0%,#faf7f2_100%)] p-4 sm:p-5">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold tracking-tight text-slate-950">{metricText[tab]}榜单</h2>
                <p className="mt-1 text-sm text-slate-600">当前展示基于 {adjustmentText[adjustment]} 口径排序</p>
              </div>
              <div className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-500">可视化榜单</div>
            </div>

            <div className="mt-5 overflow-x-auto rounded-[1.4rem] border border-slate-200/80 bg-white/85">
              <div className="min-w-[860px]">
                <div className="sticky top-0 z-10 grid grid-cols-[72px_1.5fr_0.85fr_0.85fr_1.1fr] gap-4 border-b border-slate-200 bg-[rgba(255,255,255,0.92)] px-4 py-3 text-xs font-medium tracking-[0.18em] text-slate-500 backdrop-blur">
                  <div>排名</div>
                  <div>股票</div>
                  <div className="text-right">收盘价</div>
                  <div className="text-right">今日 / YTD</div>
                  <div className="text-right">{metricText[tab]}</div>
                </div>

                <div className="space-y-4 px-3 py-4">
                  {groupedRows.map((group) => (
                    <div key={group.label} className="space-y-2">
                      <div className="flex items-center gap-3 px-1 pt-1">
                        <div className="text-xs font-medium tracking-[0.18em] text-slate-400">{group.label}</div>
                        <div className="h-px flex-1 bg-slate-200" />
                      </div>
                      {group.rows.length ? (
                        group.rows.map((row) => {
                          const index = rows.findIndex((item) => item.code === row.code) + 1
                          const metric = row[tab]
                          const width = `${(Math.abs(metric) / maxMetric) * 100}%`
                          return (
                            <div key={`${adjustment}-${group.label}-${row.code}`} className="grid grid-cols-[72px_1.5fr_0.85fr_0.85fr_1.1fr] gap-4 rounded-[1.3rem] border border-transparent bg-[#fcfbf8] px-4 py-4 transition hover:-translate-y-0.5 hover:border-slate-200 hover:bg-white hover:shadow-[0_14px_30px_rgba(15,23,42,0.05)]">
                              <div>
                                <p className="text-xs uppercase tracking-[0.16em] text-slate-400">Rank</p>
                                <p className="mt-1 text-2xl font-semibold text-slate-950">{index}</p>
                              </div>
                              <div className="flex items-center gap-3">
                                <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700">{row.code}</div>
                                <div className="min-w-0">
                                  <p className="truncate font-medium text-slate-900">{row.name}</p>
                                  <p className="mt-1 text-sm text-slate-500">当前展示项</p>
                                </div>
                              </div>
                              <div className="self-center text-right text-base font-medium text-slate-900">{row.close.toFixed(1)}</div>
                              <div className="self-center text-right text-sm">
                                <p className={row.today_return_pct >= 0 ? 'text-emerald-700' : 'text-rose-600'}>{formatPct(row.today_return_pct)}</p>
                                <p className={`mt-1 ${row.ytd_return_pct >= 0 ? 'text-emerald-700' : 'text-rose-600'}`}>{formatPct(row.ytd_return_pct)}</p>
                              </div>
                              <div className="self-center">
                                <div className="flex items-center justify-end gap-3 text-sm">
                                  <span className={`font-medium ${metric >= 0 ? 'text-emerald-700' : 'text-amber-700'}`}>{formatPct(metric)}</span>
                                </div>
                                <div className="mt-2 ml-auto h-2.5 w-full max-w-[200px] overflow-hidden rounded-full bg-slate-100">
                                  <div className={`h-full rounded-full ${metric >= 0 ? 'bg-emerald-500/85' : 'bg-amber-500/85'}`} style={{ width }} />
                                </div>
                              </div>
                            </div>
                          )
                        })
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
