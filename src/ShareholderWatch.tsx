import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'

type Holder = { name: string; shares: number; float_ratio_pct: number | null }
type Snapshot = { period: string; ann_date: string; complete: boolean; holders: Holder[] }
type Match = { name: string; state: 'new' | 'exit' | 'continuing' | 'unknown'; current: Holder | null; previous: Holder | null }
type Stock = { name: string; status: 'ok' | 'partial' | 'unavailable'; reason?: string; current?: Snapshot; previous?: Snapshot; matches: Match[] }
type Data = {
  schema_version: number; as_of: string; updated_at: string; source_url: string
  roster: { reviewed_at: string; selection: string; investors: { name: string; sources: string[] }[]; sources: Record<string, { title: string; date: string; url: string }> }
  stocks: Record<string, Stock>
}
const Context = createContext<{ data: Data | null; error: boolean; open: (code: string | null) => void }>({ data: null, error: false, open: () => {} })
const labels = { new: '新进名单', exit: '退出名单', continuing: '连续在列', unknown: '上期不足，变化未知' }
const date = (value: string) => `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`
const shares = (value: number | undefined) => value === undefined ? '—' : `${(value / 10000).toLocaleString('zh-CN', { maximumFractionDigits: 2 })} 万股`

export function ShareholderProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState(false)
  const [selection, setSelection] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${import.meta.env.BASE_URL}data/shareholder-watch.json`, { signal: controller.signal, cache: 'no-cache' })
      .then((response) => { if (!response.ok) throw new Error('Unavailable'); return response.json() })
      .then((json: Data) => {
        if (json.schema_version !== 1 || !/^\d{8}$/.test(json.as_of) || !json.stocks || !Array.isArray(json.roster?.investors)) throw new Error('Invalid data')
        setData(json)
        setError(false)
      }).catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [retry])
  const open = (code: string | null) => { setSelection(code); dialog.current?.showModal() }
  const stock = selection ? data?.stocks[selection] : null
  return <Context.Provider value={{ data, error, open }}>
    {children}
    <dialog ref={dialog} aria-labelledby="shareholder-title" className="fixed inset-0 m-auto max-h-[85dvh] w-[calc(100%-24px)] max-w-2xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-0 text-slate-800 shadow-xl backdrop:bg-slate-900/30" onClick={(event) => { if (event.target === event.currentTarget) dialog.current?.close() }}>
      <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-100 bg-white px-5 py-4">
        <h2 id="shareholder-title" className="font-semibold">{selection ? `${stock?.name ?? selection} · 股东观察` : '代表性牛散观察名单'}</h2>
        <button type="button" autoFocus onClick={() => dialog.current?.close()} className="min-h-11 shrink-0 rounded-lg border border-slate-200 px-3 text-sm">关闭</button>
      </div>
      <div className="space-y-4 p-5 text-sm leading-6">
        {!data ? <div role="status">{error ? '股东数据加载失败' : '正在加载股东数据…'}{error && <button className="ml-3 text-sky-700 underline" onClick={() => setRetry(retry + 1)}>重试</button>}</div> : <>
          <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-900">仅按披露姓名匹配，不能排除同名。新进／退出指前十大流通股东名单变化，不代表实时买入或清仓。</p>
          <p className="text-xs text-slate-500">股东查询截至 {date(data.as_of)}（北京时间）；持仓时点以各股报告期为准。名单核对：{data.roster.reviewed_at}。</p>
          {selection ? !stock || stock.status === 'unavailable' ? <p>{stock?.reason ?? '该股票暂未取得股东数据，请等待更新。'}</p> : <>
            <div className="rounded-xl bg-slate-50 p-3">
              <p>最新报告期 {date(stock.current!.period)} · 披露 {date(stock.current!.ann_date)}</p>
              <p>对比报告期 {stock.previous ? `${date(stock.previous.period)} · 披露 ${date(stock.previous.ann_date)}` : '暂无上期数据'}</p>
              {(stock.status === 'partial' || (stock.previous && !stock.previous.complete)) && <p className="text-amber-800">股东快照数量非标准十名，完整性待核实，部分变化无法判断。</p>}
            </div>
            {stock.matches.length ? <div className="space-y-3">{stock.matches.map((match) => <div key={match.name} className="rounded-xl border border-slate-200 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2"><strong>{match.name}</strong><span className={`rounded px-2 text-xs ${match.state === 'new' ? 'bg-sky-50 text-sky-700' : match.state === 'exit' ? 'bg-amber-50 text-amber-800' : 'bg-slate-100 text-slate-600'}`}>{labels[match.state]}</span></div>
              <p className="mt-1">本期 {shares(match.current?.shares)} · 上期 {shares(match.previous?.shares)}</p>
              <p className="text-xs text-slate-500">本期占流通股 {match.current?.float_ratio_pct == null ? '—' : `${match.current.float_ratio_pct.toFixed(2)}%`} · 姓名匹配，身份待核实</p>
            </div>)}</div> : <p>{stock.status === 'partial' ? '已取得的股东数据中暂无名单姓名匹配。' : '已取得的最新及上期流通股东中，暂无观察名单姓名匹配。'}未匹配不代表未持有。</p>}
            <details><summary className="min-h-11 cursor-pointer py-2 text-sky-700">查看最新披露的流通股东（{stock.current!.holders.length} 名）</summary><ul className="divide-y divide-slate-100">{stock.current!.holders.map((holder) => <li key={holder.name} className="flex flex-wrap justify-between gap-x-4 py-2"><span className="min-w-0 break-all">{holder.name}</span><span className="text-slate-500">{shares(holder.shares)}</span></li>)}</ul></details>
            <a href={data.source_url} target="_blank" rel="noreferrer" className="text-xs text-sky-700 underline">股东数据来源与字段说明：Tushare</a>
            <button className="block min-h-11 text-sky-700" onClick={() => setSelection(null)}>查看观察名单与入选依据 →</button>
          </> : <>
            <p>{data.roster.selection}</p>
            <div className="grid gap-3 sm:grid-cols-2">{data.roster.investors.map((investor) => <article key={investor.name} className="rounded-xl border border-slate-200 p-3"><h3 className="font-semibold">{investor.name}</h3>{investor.sources.map((id) => { const source = data.roster.sources[id]; return <a key={id} href={source.url} target="_blank" rel="noreferrer" className="mt-2 block text-xs leading-5 text-sky-700 hover:underline">{source.title}<span className="block text-slate-400">{source.date}</span></a> })}</article>)}</div>
          </>}
        </>}
      </div>
    </dialog>
  </Context.Provider>
}

export function ShareholderRoster() {
  const { data, error, open } = useContext(Context)
  return <div className="rounded-2xl border border-sky-100 bg-white/90 px-4 py-3 text-sm">
    <button type="button" onClick={() => open(null)} className="min-h-11 font-medium text-sky-800">牛散观察 · {data ? `${data.roster.investors.length} 位` : error ? '加载失败，点击查看' : '加载中'} · 查看名单与来源 →</button>
    <p className="text-xs leading-5 text-slate-500">股票下方点击“股东”查看匹配及新进／退出；按最新披露的前十大流通股东姓名匹配，可能同名。{data && ` 查询截至 ${date(data.as_of)}。`}</p>
  </div>
}

export function ShareholderBadge({ code }: { code: string }) {
  const { data, error, open } = useContext(Context)
  const stock = data?.stocks[code]
  const names = stock?.matches ?? []
  const suffix = !data ? error ? '加载失败' : '加载中' : !stock || stock.status === 'unavailable' ? '待更新' : names.length ? `${names.length} 匹配${names.some(m => m.state === 'new') ? ' · 新进' : ''}${names.some(m => m.state === 'exit') ? ' · 退出' : ''}` : stock.status === 'partial' ? '完整性待核' : '未匹配'
  return <button type="button" onClick={() => open(code)} aria-label={`${code} 股东 ${suffix}`} className={`mt-1 min-h-8 max-w-full rounded px-1 text-left text-[10px] leading-4 ${names.length ? 'bg-sky-50 text-sky-800' : 'text-slate-400 hover:text-sky-700'}`}>股东 · {suffix}</button>
}
