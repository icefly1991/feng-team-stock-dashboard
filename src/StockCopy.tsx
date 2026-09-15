import { createContext, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Check, CircleAlert, Copy, X } from 'lucide-react'
import { copyText } from './clipboard'

type CopyFeedback = {
  id: number
  target: string
  value: string
  status: 'success' | 'error'
}

const StockCopyContext = createContext<{
  feedback: CopyFeedback | null
  copy: (value: string, target: string) => Promise<void>
} | null>(null)

export function StockCopyProvider({ children }: { children: ReactNode }) {
  const [copyFeedback, setCopyFeedback] = useState<CopyFeedback | null>(null)
  const copyRequestRef = useRef(0)

  useEffect(() => () => { copyRequestRef.current += 1 }, [])

  useEffect(() => {
    if (copyFeedback?.status !== 'success') return
    const timer = window.setTimeout(() => {
      setCopyFeedback((current) => current?.id === copyFeedback.id ? null : current)
    }, 3000)
    return () => window.clearTimeout(timer)
  }, [copyFeedback])

  async function handleCopy(value: string, target: string) {
    const id = ++copyRequestRef.current
    setCopyFeedback(null)
    try {
      await copyText(value)
      if (id === copyRequestRef.current) setCopyFeedback({ id, target, value, status: 'success' })
    } catch {
      if (id === copyRequestRef.current) setCopyFeedback({ id, target, value, status: 'error' })
    }
  }

  return (
    <StockCopyContext.Provider value={{ feedback: copyFeedback, copy: handleCopy }}>
      {children}
      <div role="status" aria-live="polite" aria-atomic="true" className="pointer-events-none fixed inset-x-4 bottom-[max(1.5rem,env(safe-area-inset-bottom))] z-50 mx-auto w-fit max-w-[calc(100%-2rem)]">
        {copyFeedback ? (
          <div key={copyFeedback.id} className={`pointer-events-auto flex max-w-sm items-start gap-3 rounded-2xl border bg-white px-4 py-3 text-sm shadow-[0_12px_40px_rgba(15,23,42,0.14)] ${copyFeedback.status === 'success' ? 'border-emerald-200 text-slate-700' : 'border-amber-200 text-slate-700'}`}>
            {copyFeedback.status === 'success' ? <Check size={18} className="mt-0.5 shrink-0 text-emerald-600" aria-hidden="true" /> : <CircleAlert size={18} className="mt-0.5 shrink-0 text-amber-600" aria-hidden="true" />}
            <div className="min-w-0 flex-1">
              {copyFeedback.status === 'success' ? (
                <p className="break-words">已复制 <span className="font-semibold text-slate-950">{copyFeedback.value}</span>，可以粘贴了</p>
              ) : (
                <>
                  <p>复制失败，请手动复制下方内容</p>
                  <input aria-label="手动复制内容" readOnly value={copyFeedback.value} onFocus={(event) => event.currentTarget.select()} onClick={(event) => event.currentTarget.select()} className="mt-2 w-full rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-base text-slate-900 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100" />
                </>
              )}
            </div>
            <button type="button" aria-label="关闭复制提示" onClick={() => setCopyFeedback(null)} className="-mr-1 -mt-0.5 flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-600 focus-visible:outline-2 focus-visible:outline-sky-500"><X size={14} aria-hidden="true" /></button>
          </div>
        ) : null}
      </div>
    </StockCopyContext.Provider>
  )
}

export function CopyStockButton({ value, label, target, secondary = false, textClassName }: {
  value: string
  label: string
  target: string
  secondary?: boolean
  textClassName?: string
}) {
  const context = useContext(StockCopyContext)
  if (!context) throw new Error('CopyStockButton requires StockCopyProvider')
  const copied = context.feedback?.status === 'success' && context.feedback.target === target
  const textStyle = textClassName ?? (secondary ? 'text-xs tracking-[0.08em] text-slate-400' : 'font-medium text-slate-900')

  return (
    <button
      type="button"
      onClick={() => context.copy(value, target)}
      title={`点击复制${label}：${value}`}
      aria-label={`复制${label}：${value}`}
      className={`group/copy -ml-1 flex min-h-6 max-w-full cursor-pointer items-center gap-1.5 rounded-md px-1 py-0.5 text-left transition-colors hover:bg-sky-50 hover:text-sky-700 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-sky-500 active:bg-sky-100 motion-reduce:transition-none ${secondary ? 'mt-0.5' : ''} ${textStyle}`}
    >
      <span className="min-w-0 truncate">{value}</span>
      {copied ? <Check size={12} className="shrink-0 text-emerald-600" aria-hidden="true" /> : <Copy size={12} className="shrink-0 text-slate-300 group-hover/copy:text-sky-500 group-focus-visible/copy:text-sky-500" aria-hidden="true" />}
    </button>
  )
}
