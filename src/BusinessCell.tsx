import type { SectorData } from './useStockSectors'
import { businessSectors } from './sectorDisplay'

export default function BusinessCell({ text, keywords = [], sectors = null, code = '', onSelect }: {
  text: string; keywords?: string[]; sectors?: SectorData | null; code?: string; onSelect?: (value: string) => void
}) {
  const related = businessSectors(sectors, code, keywords)
  if (!text) return <div className="text-xs text-slate-400">—</div>
  return <div className="min-w-0 text-xs leading-5 text-slate-600">
    <div className="flex flex-wrap gap-1">{keywords.map(word => <span key={word} className="rounded-md border border-slate-200 bg-white px-1.5 py-0.5">{word}</span>)}</div>
    {related.length > 0 && <div className="mt-2"><p className="text-[10px] text-slate-400">业务相关板块</p><div className="mt-1 flex flex-wrap gap-1">{related.map(tag => <button type="button" key={`${tag.kind}:${tag.name}`} onClick={() => onSelect?.(`${tag.kind}:${tag.name}`)} title="已有板块与业务词组匹配，点击筛选" className="rounded border border-sky-100 bg-sky-50 px-1.5 py-0.5 text-sky-800">{tag.name}</button>)}</div></div>}
    <details className="mt-1"><summary className="cursor-pointer py-1 text-[11px] text-sky-700">{keywords.length ? '业务原文' : '查看业务（词组待整理）'}</summary><p className="mt-2 whitespace-pre-wrap break-words">{text}</p></details>
  </div>
}
