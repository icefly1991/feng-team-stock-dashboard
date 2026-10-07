import type { SectorData } from './useStockSectors'
import { businessSectors } from './sectorDisplay'

export default function BusinessCell({ text, keywords = [], sectors = null, code = '', onSelect }: {
  text: string; keywords?: string[]; sectors?: SectorData | null; code?: string; onSelect?: (value: string) => void
}) {
  const related = businessSectors(sectors, code, keywords)
  if (!keywords.length) return <div className="text-xs text-slate-400">{text ? '业务词组待整理' : '—'}</div>
  return <div className="min-w-0 text-xs leading-5 text-slate-600">
    <p className="business-phrases">{keywords.join('、')}</p>
    {related.length > 0 && <div className="mt-2"><p className="text-[10px] text-slate-400">业务相关板块</p><div className="mt-1">{related.map((tag, i) => <span key={`${tag.kind}:${tag.name}`}>{i > 0 && '、'}<button type="button" onClick={() => onSelect?.(`${tag.kind}:${tag.name}`)} title="已有板块与业务词组匹配，点击筛选" className="text-sky-800 underline decoration-sky-200 underline-offset-2">{tag.name}</button></span>)}</div></div>}
  </div>
}
