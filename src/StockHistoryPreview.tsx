import { createContext, lazy, Suspense, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { ChartCandlestick, X } from 'lucide-react'

const HistoryChart = lazy(() => import('./StockHistoryChart'))
type Stock = { code: string; name: string; tradeDate: string; adjustment?: 'qfq' | 'none'; source?: 'growth' | 'watchlist' }
type Preview = Stock & { left: number; top: number; pinned: boolean; trigger: HTMLElement }
const PreviewContext = createContext<{
  open: (stock: Stock, anchor: HTMLElement, pinned: boolean) => void
  leave: () => void
  cancel: () => void
} | null>(null)

export function StockHistoryProvider({ children }: { children: ReactNode }) {
  const [preview, setPreview] = useState<Preview | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const panel = useRef<HTMLDivElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  const cancel = () => clearTimeout(timer.current)
  const close = () => {
    cancel()
    if (preview?.pinned && preview.trigger.isConnected) preview.trigger.focus()
    setPreview(null)
  }

  useEffect(() => () => clearTimeout(timer.current), [])
  useEffect(() => {
    if (!preview) return
    if (preview.pinned) closeButton.current?.focus({ preventScroll: true })
    const dismiss = () => {
      clearTimeout(timer.current)
      if (preview.pinned && preview.trigger.isConnected) preview.trigger.focus({ preventScroll: true })
      setPreview(null)
    }
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') dismiss() }
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !panel.current?.contains(event.target) && !preview.trigger.contains(event.target)) dismiss()
    }
    window.addEventListener('keydown', key)
    window.addEventListener('pointerdown', outside)
    window.addEventListener('resize', dismiss)
    if (!preview.pinned) window.addEventListener('scroll', dismiss)
    return () => {
      window.removeEventListener('keydown', key)
      window.removeEventListener('pointerdown', outside)
      window.removeEventListener('resize', dismiss)
      window.removeEventListener('scroll', dismiss)
    }
  }, [preview])

  const open = (stock: Stock, anchor: HTMLElement, pinned: boolean) => {
    cancel()
    if (!pinned && preview?.pinned) return
    const show = () => {
      const rect = anchor.getBoundingClientRect()
      const width = Math.min(640, window.innerWidth - 24)
      const left = rect.right + width + 12 <= window.innerWidth - 12 ? rect.right + 12
        : Math.max(12, Math.min(rect.left - width - 12, window.innerWidth - width - 12))
      const top = Math.max(12, Math.min(rect.top - 70, window.innerHeight - 560))
      setPreview({ ...stock, left, top, pinned, trigger: anchor })
    }
    if (pinned) show()
    else timer.current = setTimeout(show, 300)
  }
  const leave = () => {
    cancel()
    if (!preview?.pinned) timer.current = setTimeout(() => setPreview(null), 240)
  }

  return <PreviewContext.Provider value={{ open, leave, cancel }}>
    {children}
    {preview && createPortal(
      <div ref={panel} role="dialog" aria-label={`${preview.name}历史K线`} onPointerEnter={cancel} onPointerLeave={leave}
        className="fixed z-[60] w-[640px] max-w-[calc(100vw-24px)] overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-[0_20px_80px_rgba(15,23,42,0.25)]"
        style={{ left: preview.left, top: preview.top, maxHeight: `calc(100dvh - ${preview.top + 12}px)` }}>
        <div className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-100 bg-white px-4 py-3">
          <div><span className="font-semibold text-slate-900">{preview.name}</span><span className="ml-2 text-xs tabular-nums text-slate-400">{preview.code}</span><p className="mt-0.5 text-[11px] text-slate-500">历史走势 · {preview.adjustment === 'none' ? '不复权（除权）' : '前复权'} · {preview.pinned ? '已固定，可按 Esc 关闭' : '移入查看，点击图表按钮可固定'}</p></div>
          <button ref={closeButton} type="button" aria-label="关闭K线预览" onClick={close} className="flex size-9 shrink-0 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-sky-500"><X size={18} /></button>
        </div>
        <Suspense fallback={<div className="p-10 text-center text-sm text-slate-500">正在加载图表…</div>}>
          <HistoryChart key={`${preview.source}:${preview.adjustment}:${preview.code}:${preview.tradeDate}`} code={preview.code} tradeDate={preview.tradeDate} adjustment={preview.adjustment} source={preview.source} />
        </Suspense>
      </div>, document.body)}
  </PreviewContext.Provider>
}

export function StockHistoryCode({ code, name, tradeDate, adjustment = 'qfq', source = 'growth', children }: Stock & { children: ReactNode }) {
  const context = useContext(PreviewContext)
  if (!context) throw new Error('StockHistoryCode requires StockHistoryProvider')
  return <div className="flex items-center gap-1">
    <div className="w-20 shrink-0" onPointerEnter={(event) => { if (event.pointerType === 'mouse') context.open({ code, name, tradeDate, adjustment, source }, event.currentTarget, false) }} onPointerLeave={context.leave}>{children}</div>
    <button type="button" aria-label={`查看${name}历史K线`} title="查看五年K线" onClick={(event) => context.open({ code, name, tradeDate, adjustment, source }, event.currentTarget, true)}
      className="flex min-h-8 min-w-6 shrink-0 cursor-pointer items-center justify-center rounded-md text-sky-600 hover:bg-sky-50 focus-visible:outline-2 focus-visible:outline-sky-500"><ChartCandlestick size={15} aria-hidden="true" /></button>
  </div>
}
