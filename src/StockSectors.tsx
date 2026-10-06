import { useMemo } from 'react'
import type { SectorData } from './useStockSectors'
import { conceptDisplay } from './sectorDisplay'

export function SectorFilter({ data, error, codes, value, onChange }: {
  data: SectorData | null; error: boolean; codes: string[]; value: string; onChange: (value: string) => void
}) {
  const options = useMemo(() => {
    const industry = new Set<string>(), concepts = new Set<string>()
    for (const code of codes) {
      const stock = data?.stocks[code]
      if (stock && stock.status !== 'unavailable') { stock.industry.forEach(tag => industry.add(tag)); stock.concepts.forEach(tag => concepts.add(tag)) }
    }
    return { industry: [...industry].sort((a, b) => a.localeCompare(b, 'zh-CN')), concepts: [...concepts].sort((a, b) => a.localeCompare(b, 'zh-CN')) }
  }, [data, codes])
  return <div className="flex flex-wrap items-center gap-3 py-3">
    <label className="flex items-center gap-2 text-sm text-slate-600">板块筛选
      <select aria-label="板块筛选" value={value} disabled={!data} onChange={event => onChange(event.target.value)} className="min-h-11 max-w-[230px] rounded-xl border border-slate-200 bg-white px-3 text-sm disabled:opacity-50">
        <option value="">全部板块</option>
        <optgroup label="行业">{options.industry.map(tag => <option key={tag} value={`industry:${tag}`}>{tag}</option>)}</optgroup>
        <optgroup label="概念">{options.concepts.map(tag => <option key={tag} value={`concepts:${tag}`}>{tag}</option>)}</optgroup>
        <option value="unknown">板块暂无数据</option>
      </select>
    </label>
    {value && <button type="button" onClick={() => onChange('')} className="min-h-11 px-2 text-xs text-sky-700">清除板块筛选</button>}
    <p className="text-xs text-slate-400">{error ? '板块数据暂不可用' : data ? `${data.source} · 采集 ${data.updated_at}（北京时间）` : '正在加载板块…'}</p>
    {data && <details className="w-full text-xs leading-5 text-slate-500"><summary className="cursor-pointer text-sky-700">板块排序与更新说明</summary>
      <p className="mt-2">行业单独显示；主题概念优先展示最新交易日涨幅位于前20%且上涨的板块，最多两个，其余折叠。“小盘、低价、融资融券”等通用属性始终折叠。同涨幅按成交额排序。这里只在股票已有概念中选择，不表示公司公告确认参与该热点。</p>
      <p>{data.heat?.status === 'ok' ? `市场行情参考日 ${data.heat.trade_date}；没有行情覆盖的概念保留在折叠列表，不推测热度。` : '板块行情暂不可用，概念全部保留在折叠列表，不推测热度。'}{data.heat?.source_url && <a href={data.heat.source_url} target="_blank" rel="noreferrer" className="ml-1 text-sky-700 underline">行情来源</a>}</p>
      <p>每个工作日北京时间16:13自动更新，假期行情日期沿用最近交易日；以页面采集时间为准。更新完成后刷新页面即可查看。</p>
    </details>}
  </div>
}

export function SectorCell({ data, code, onSelect }: { data: SectorData | null; code: string; onSelect: (value: string) => void }) {
  const stock = data?.stocks[code]
  if (!stock || stock.status === 'unavailable') return <div className="text-xs text-slate-400">{data ? '板块暂无数据' : '板块加载中'}</div>
  const concepts = conceptDisplay(data!, stock.concepts)
  return <div className="space-y-1 text-xs leading-5">
    <div className="flex flex-wrap gap-1">{stock.industry.map(tag => <button type="button" key={tag} onClick={() => onSelect(`industry:${tag}`)} className="rounded border border-sky-100 bg-sky-50 px-1.5 py-1 text-sky-800" title={`筛选行业：${tag}`}>{tag}</button>)}</div>
    {stock.concepts.length > 0 ? <>{concepts.visible.length > 0 && <><p className="text-[10px] text-amber-700">强势概念 · {data!.heat!.trade_date?.slice(5)}</p><div className="flex flex-wrap gap-1">{concepts.visible.map(tag => <Tag key={tag} tag={tag} onSelect={onSelect} heat={data!.heat!.concepts[tag]} />)}</div></>}{concepts.hidden.length > 0 && <details><summary className="cursor-pointer py-1 text-sky-700">其他概念（{concepts.hidden.length}）</summary><div className="mt-1 flex flex-wrap gap-1">{concepts.hidden.map(tag => <Tag key={tag} tag={tag} onSelect={onSelect} />)}</div></details>}</> : <p className="text-slate-400">暂无概念标签</p>}
    {stock.status === 'partial' && <p className="text-amber-700">分类不完整</p>}
    <a className="block text-[10px] text-slate-400 underline" href={stock.source_url} target="_blank" rel="noreferrer">来源</a>
  </div>
}

function Tag({ tag, onSelect, heat }: { tag: string; onSelect: (value: string) => void; heat?: { rank: number; return_pct: number } }) {
  return <button type="button" onClick={() => onSelect(`concepts:${tag}`)} title={`筛选概念：${tag}${heat ? ` · 板块涨幅 ${heat.return_pct.toFixed(2)}% · 第${heat.rank}名` : ''}`} className={`rounded border px-1.5 py-1 ${heat ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-slate-200 bg-slate-50 text-slate-600'} hover:border-sky-300`}>{tag}</button>
}
