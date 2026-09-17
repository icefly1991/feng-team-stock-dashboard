import { useEffect, useRef, useState } from 'react'
import { CandlestickSeries, ColorType, createChart, createSeriesMarkers, HistogramSeries, isBusinessDay } from 'lightweight-charts'
import type { Time } from 'lightweight-charts'

type Bar = { time: string; open: number; high: number; low: number; close: number; volume: number }
type History = {
  code: string; trade_date: string; adjustment: string; actual_start: string; actual_end: string; requested_start: string
  daily: Bar[]; weekly: Bar[]
  metrics: { position_pct: number | null; distance_high_pct: number; high: number; low: number; close: number }
}
const cache = new Map<string, Promise<History>>()
const pct = (value: number | null) => value === null ? '—' : `${value.toFixed(1)}%`
function loadHistory(code: string, tradeDate: string, adjustment: 'qfq' | 'none', source: 'growth' | 'watchlist') {
  if (!/^\d{8}$/.test(tradeDate)) return Promise.reject(new Error('榜单缺少交易日，请更新数据后重试'))
  const key = `${source}:${adjustment}:${code}:${tradeDate}`
  if (!cache.has(key)) {
    const directory = source === 'watchlist' ? `watchlist-history/${adjustment}` : 'growth-history'
    const request = fetch(`${import.meta.env.BASE_URL}data/${directory}/${code}.json?v=${tradeDate}`)
      .then(async (response) => {
        if (!response.ok) throw new Error('该股票历史数据暂不可用，请稍后重试')
        const data: History = await response.json()
        if (data.code !== code || data.trade_date !== tradeDate || data.adjustment !== adjustment) throw new Error('历史数据日期或复权口径与榜单不一致')
        if (!data.metrics || ![data.metrics.high, data.metrics.low, data.metrics.close, data.metrics.distance_high_pct].every(Number.isFinite) ||
          (data.metrics.position_pct !== null && !Number.isFinite(data.metrics.position_pct))) throw new Error('历史指标不完整，请更新数据后重试')
        for (const bars of [data.daily, data.weekly]) {
          if (!Array.isArray(bars) || !bars.length || bars.some((bar, i) =>
            !/^\d{4}-\d{2}-\d{2}$/.test(bar.time) || (i > 0 && bar.time <= bars[i - 1].time) ||
            ![bar.open, bar.high, bar.low, bar.close, bar.volume].every(Number.isFinite) ||
            bar.low <= 0 || bar.volume < 0 || bar.high < Math.max(bar.open, bar.close, bar.low) || bar.low > Math.min(bar.open, bar.close))) {
            throw new Error('历史行情不完整，请更新数据后重试')
          }
        }
        return data
      }).catch((error: unknown) => { cache.delete(key); throw error })
    cache.set(key, request)
  }
  return cache.get(key)!
}

export default function StockHistoryChart({ code, tradeDate, adjustment = 'qfq', source = 'growth' }: { code: string; tradeDate: string; adjustment?: 'qfq' | 'none'; source?: 'growth' | 'watchlist' }) {
  const [history, setHistory] = useState<History | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [mode, setMode] = useState<'weekly' | 'daily'>('weekly')
  useEffect(() => {
    let active = true
    loadHistory(code, tradeDate, adjustment, source).then((data) => { if (active) setHistory(data) })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : '无法加载历史行情') })
    return () => { active = false }
  }, [code, tradeDate, adjustment, source, attempt])

  if (error) return <div className="p-8 text-center text-sm text-slate-500"><p role="alert">{error}</p><button className="mt-3 rounded-lg border border-slate-200 px-4 py-2 text-sky-700" onClick={() => { setError(''); setAttempt((value) => value + 1) }}>重试</button></div>
  if (!history) return <div role="status" className="p-12 text-center text-sm text-slate-500">正在加载五年行情…</div>
  const shorter = new Date(history.actual_start).getTime() - new Date(history.requested_start).getTime() > 14 * 86400000
  const date = `${tradeDate.slice(0, 4)}-${tradeDate.slice(4, 6)}-${tradeDate.slice(6, 8)}`
  return <div className="px-3 pb-3 sm:px-4">
    <div className="mt-3 grid grid-cols-3 gap-2">
      <Metric label={shorter ? '可用历史区间位置' : '五年区间位置'} value={pct(history.metrics.position_pct)} />
      <Metric label="距区间高点" value={pct(history.metrics.distance_high_pct)} />
      <Metric label={`最新收盘（${adjustment === 'none' ? '不复权' : '前复权'}）`} value={history.metrics.close.toFixed(2)} />
    </div>
    <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
      <div className="flex rounded-lg bg-slate-100 p-0.5">
        {(['weekly', 'daily'] as const).map((value) => <button key={value} type="button" aria-pressed={mode === value} onClick={() => setMode(value)} className={`min-h-8 rounded-md px-3 text-xs font-medium ${mode === value ? 'bg-white text-sky-700 shadow-sm' : 'text-slate-500'}`}>{value === 'weekly' ? '五年 · 周K' : '近一年 · 日K'}</button>)}
      </div>
      <span className="text-[10px] text-slate-400">红涨绿跌 · 下方为成交量（手）</span>
    </div>
    <CandleChart history={history} mode={mode} />
    <p className="mt-1 text-[10px] leading-4 text-slate-500">{history.actual_start} 至 {history.actual_end}{shorter ? ' · 历史不足五年，按可用区间展示' : ''}{history.actual_end !== date ? ` · 榜单截至 ${date}，该股最后行情为 ${history.actual_end}` : ''}。周K按周内交易日聚合，末周可能尚未结束。</p>
    <div className="mt-1 flex flex-wrap justify-between gap-1 text-[10px] text-slate-400"><span>Tushare 行情 · 区间位置不代表估值高低</span><a href="https://www.tradingview.com/" target="_blank" rel="noreferrer" className="hover:text-sky-700">TradingView Lightweight Charts™ © 2025 TradingView, Inc.</a></div>
  </div>
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-slate-50 px-2.5 py-2"><p className="text-[10px] text-slate-500">{label}</p><p className="mt-1 text-lg font-semibold tabular-nums text-slate-900">{value}</p></div>
}

function CandleChart({ history, mode }: { history: History; mode: 'weekly' | 'daily' }) {
  const container = useRef<HTMLDivElement>(null)
  const legend = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!container.current) return
    const cutoff = new Date(`${history.trade_date.slice(0, 4)}-${history.trade_date.slice(4, 6)}-${history.trade_date.slice(6, 8)}T00:00:00Z`)
    cutoff.setUTCFullYear(cutoff.getUTCFullYear() - 1)
    const bars = mode === 'weekly' ? history.weekly : history.daily.filter((bar) => bar.time >= cutoff.toISOString().slice(0, 10))
    const chart = createChart(container.current, {
      autoSize: true, height: 270,
      layout: { background: { type: ColorType.Solid, color: '#ffffff' }, textColor: '#64748b', fontSize: 10, attributionLogo: true },
      grid: { vertLines: { visible: false }, horzLines: { color: '#f1f5f9' } },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.12, bottom: 0.1 } }, timeScale: { borderVisible: false, rightOffset: 3 },
      handleScroll: false, handleScale: false,
      localization: { locale: 'zh-CN', dateFormat: 'yyyy-MM-dd' },
    })
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: '#ef4444', downColor: '#10b981', wickUpColor: '#ef4444', wickDownColor: '#10b981', borderVisible: false,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    })
    candles.setData(bars.map((bar) => ({ ...bar, time: bar.time as Time })))
    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, lastValueVisible: false, priceLineVisible: false }, 1)
    volume.setData(bars.map((bar) => ({ time: bar.time as Time, value: bar.volume, color: bar.close >= bar.open ? '#fca5a5' : '#6ee7b7' })))
    chart.panes()[1].setHeight(58)
    if (bars.length) {
      const high = bars.reduce((a, b) => a.high >= b.high ? a : b)
      const low = bars.reduce((a, b) => a.low <= b.low ? a : b)
      createSeriesMarkers(candles, [
        { time: high.time as Time, position: 'aboveBar' as const, color: '#64748b', shape: 'circle' as const, text: `高 ${high.high.toFixed(2)}`, size: 0 },
        { time: low.time as Time, position: 'belowBar' as const, color: '#64748b', shape: 'circle' as const, text: `低 ${low.low.toFixed(2)}`, size: 0 },
      ].sort((a, b) => String(a.time).localeCompare(String(b.time))))
    }
    const updateLegend = (bar?: Bar) => {
      if (legend.current) legend.current.textContent = bar ? `${bar.time} · 开 ${bar.open.toFixed(2)} · 高 ${bar.high.toFixed(2)} · 低 ${bar.low.toFixed(2)} · 收 ${bar.close.toFixed(2)} · 量 ${bar.volume.toLocaleString('zh-CN')} 手` : '该时段暂无交易数据'
    }
    updateLegend(bars.at(-1))
    const byTime = new Map(bars.map((bar) => [bar.time, bar]))
    chart.subscribeCrosshairMove((event) => {
      const time = event.time
      const key = time && isBusinessDay(time) ? `${time.year}-${String(time.month).padStart(2, '0')}-${String(time.day).padStart(2, '0')}` : String(time)
      updateLegend(time ? byTime.get(key) : bars.at(-1))
    })
    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [history, mode])
  return <><div ref={legend} className="mt-2 min-h-8 text-[10px] leading-4 tabular-nums text-slate-500" /><div ref={container} className="h-[270px] w-full" aria-label={`${mode === 'weekly' ? '五年周K线' : '近一年日K线'}及成交量（${history.adjustment === 'none' ? '不复权' : '前复权'}）`} /></>
}
