import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowUpRight,
  BarChart3,
  Clock3,
  LineChart,
  TrendingUp,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

type Row = {
  code: string
  name: string
  distance_ma250_pct?: number
  ytd_return_pct?: number
  volume_ratio?: number
}

type Tab = {
  id: string
  title: string
  metric: keyof Row
  rows: Row[]
}

type DashboardData = {
  updated_at: string
  summary: {
    total: number
    near_ma250_count: number
    positive_ytd_count: number
  }
  tabs: Tab[]
}

const cardConfig = [
  {
    key: 'total',
    label: 'Tracked Stocks',
    icon: LineChart,
    accent: 'from-white/20 to-white/5',
    valueSuffix: '',
  },
  {
    key: 'near_ma250_count',
    label: 'Near MA250',
    icon: BarChart3,
    accent: 'from-cyan-400/20 to-cyan-400/5',
    valueSuffix: '',
  },
  {
    key: 'positive_ytd_count',
    label: 'Positive YTD',
    icon: TrendingUp,
    accent: 'from-emerald-400/20 to-emerald-400/5',
    valueSuffix: '',
  },
] as const

function formatMetricLabel(metric: string) {
  return metric
    .replace(/_/g, ' ')
    .replace(/pct/g, '%')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function formatMetricValue(value: number | undefined, metric: string) {
  if (typeof value !== 'number') return '--'
  return metric.includes('pct') ? `${value.toFixed(1)}%` : value.toFixed(2)
}

function App() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [activeTabId, setActiveTabId] = useState<string>('')
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    let isMounted = true

    async function loadDashboard() {
      try {
        const response = await fetch('/data/dashboard.json')
        if (!response.ok) throw new Error('Failed to load dashboard data')
        const json: DashboardData = await response.json()

        if (!isMounted) return
        setData(json)
        setActiveTabId(json.tabs[0]?.id ?? '')
        setStatus('ready')
      } catch {
        if (!isMounted) return
        setStatus('error')
      }
    }

    loadDashboard()

    return () => {
      isMounted = false
    }
  }, [])

  const activeTab = useMemo(
    () => data?.tabs.find((tab) => tab.id === activeTabId) ?? data?.tabs[0],
    [activeTabId, data],
  )

  if (status === 'loading') {
    return (
      <main className="min-h-screen bg-[#030303] text-white">
        <div className="mx-auto flex min-h-screen max-w-7xl items-center justify-center px-6">
          <div className="rounded-3xl border border-white/10 bg-white/5 px-6 py-5 text-sm text-white/70 backdrop-blur-xl">
            Loading dashboard...
          </div>
        </div>
      </main>
    )
  }

  if (status === 'error' || !data || !activeTab) {
    return (
      <main className="min-h-screen bg-[#030303] text-white">
        <div className="mx-auto flex min-h-screen max-w-7xl items-center justify-center px-6">
          <div className="rounded-3xl border border-red-400/20 bg-red-400/10 px-6 py-5 text-sm text-red-100 backdrop-blur-xl">
            Unable to load `/data/dashboard.json`.
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen overflow-hidden bg-[#030303] text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(120,119,198,0.16),_transparent_28%),radial-gradient(circle_at_80%_20%,_rgba(56,189,248,0.12),_transparent_22%),linear-gradient(180deg,_rgba(255,255,255,0.05),_transparent_30%)]" />

      <div className="relative mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <motion.section
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="rounded-[2rem] border border-white/10 bg-white/6 p-6 shadow-2xl shadow-black/30 backdrop-blur-2xl sm:p-8"
        >
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs tracking-[0.24em] text-white/55 uppercase">
                <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_18px_rgba(74,222,128,0.8)]" />
                Market Pulse
              </div>
              <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-5xl">
                Premium stock dashboard with a calm, high-contrast night mode.
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-white/60 sm:text-base">
                Monitor headline breadth, rotate through signal tabs, and scan
                the strongest names without leaving the overview.
              </p>
            </div>

            <div className="flex items-center gap-3 self-start rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white/70">
              <Clock3 className="h-4 w-4 text-white/45" />
              <span>Updated {data.updated_at}</span>
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {cardConfig.map((card, index) => {
              const Icon = card.icon
              const value = data.summary[card.key]

              return (
                <motion.article
                  key={card.key}
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.45, delay: 0.1 + index * 0.08 }}
                  className="group relative overflow-hidden rounded-[1.75rem] border border-white/10 bg-white/[0.045] p-5"
                >
                  <div
                    className={`absolute inset-0 bg-gradient-to-br ${card.accent} opacity-80 transition-opacity duration-300 group-hover:opacity-100`}
                  />
                  <div className="relative flex items-start justify-between">
                    <div>
                      <p className="text-sm text-white/55">{card.label}</p>
                      <p className="mt-4 text-3xl font-semibold tracking-tight text-white">
                        {value}
                        {card.valueSuffix}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-black/20 p-3 text-white/80">
                      <Icon className="h-5 w-5" />
                    </div>
                  </div>
                  <div className="relative mt-6 flex items-center gap-2 text-xs text-white/45">
                    <ArrowUpRight className="h-4 w-4" />
                    Live breadth snapshot
                  </div>
                </motion.article>
              )
            })}
          </div>
        </motion.section>

        <section className="mt-6 grid gap-6 xl:grid-cols-[1.45fr_1fr]">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.2 }}
            className="rounded-[2rem] border border-white/10 bg-white/[0.045] p-4 shadow-xl shadow-black/20 backdrop-blur-2xl sm:p-6"
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold tracking-tight text-white">
                  Signal tabs
                </h2>
                <p className="mt-1 text-sm text-white/55">
                  Switch views to compare ranking metrics across the same watch
                  list.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                {data.tabs.map((tab) => {
                  const active = tab.id === activeTab.id
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveTabId(tab.id)}
                      className={`rounded-full border px-4 py-2 text-sm transition ${
                        active
                          ? 'border-white/20 bg-white text-black shadow-lg shadow-white/10'
                          : 'border-white/10 bg-white/5 text-white/65 hover:bg-white/10 hover:text-white'
                      }`}
                    >
                      {tab.title}
                    </button>
                  )
                })}
              </div>
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab.id}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -14 }}
                transition={{ duration: 0.28 }}
                className="mt-6"
              >
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-medium text-white">
                      {activeTab.title}
                    </h3>
                    <p className="mt-1 text-sm text-white/50">
                      Bar chart by {formatMetricLabel(String(activeTab.metric))}
                    </p>
                  </div>
                </div>

                <div className="h-80 rounded-[1.5rem] border border-white/8 bg-black/25 p-3 sm:p-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={activeTab.rows}>
                      <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                      <XAxis
                        dataKey="code"
                        tick={{ fill: 'rgba(255,255,255,0.55)', fontSize: 12 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fill: 'rgba(255,255,255,0.55)', fontSize: 12 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                        contentStyle={{
                          background: 'rgba(10, 10, 10, 0.92)',
                          border: '1px solid rgba(255,255,255,0.08)',
                          borderRadius: '16px',
                          color: '#fff',
                        }}
                      />
                      <Bar
                        dataKey={activeTab.metric}
                        radius={[10, 10, 0, 0]}
                        fill="url(#barGlow)"
                      />
                      <defs>
                        <linearGradient id="barGlow" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#d4d4d8" />
                          <stop offset="100%" stopColor="#38bdf8" />
                        </linearGradient>
                      </defs>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            </AnimatePresence>
          </motion.div>

          <motion.aside
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.28 }}
            className="rounded-[2rem] border border-white/10 bg-white/[0.045] p-4 shadow-xl shadow-black/20 backdrop-blur-2xl sm:p-6"
          >
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold tracking-tight text-white">
                  Top names
                </h2>
                <p className="mt-1 text-sm text-white/55">
                  Simple ranked table for the active signal.
                </p>
              </div>
            </div>

            <div className="mt-5 overflow-hidden rounded-[1.5rem] border border-white/8 bg-black/25">
              <div className="grid grid-cols-[0.9fr_1.6fr_1fr_1fr] gap-3 border-b border-white/8 px-4 py-3 text-xs uppercase tracking-[0.2em] text-white/35">
                <span>Code</span>
                <span>Name</span>
                <span>{formatMetricLabel(String(activeTab.metric))}</span>
                <span>YTD</span>
              </div>

              <div className="divide-y divide-white/6">
                {activeTab.rows.map((row) => {
                  const rawMetricValue = row[activeTab.metric]
                  const metricValue =
                    typeof rawMetricValue === 'number' ? rawMetricValue : undefined
                  const ytdValue = row.ytd_return_pct
                  return (
                    <div
                      key={row.code}
                      className="grid grid-cols-[0.9fr_1.6fr_1fr_1fr] gap-3 px-4 py-4 text-sm text-white/78"
                    >
                      <span className="font-medium text-white">{row.code}</span>
                      <span className="truncate">{row.name}</span>
                      <span>{formatMetricValue(metricValue, String(activeTab.metric))}</span>
                      <span
                        className={
                          typeof ytdValue === 'number' && ytdValue >= 0
                            ? 'text-emerald-300'
                            : 'text-rose-300'
                        }
                      >
                        {formatMetricValue(ytdValue, 'ytd_return_pct')}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          </motion.aside>
        </section>
      </div>
    </main>
  )
}

export default App
