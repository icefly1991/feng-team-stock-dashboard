import type { SectorData } from './useStockSectors'

const generalConcepts = new Set(['小盘', '低价', '融资融券', '转融券', '沪股通', '深股通', '北证50', '次新股', '注册制次新股', 'ST板块', '准ST股', '业绩预升', '业绩预降', '基金重仓', '社保重仓', 'QFII重仓', '信托重仓', '央企50', '含H股', '股权激励', '送转潜力', '本月解禁', '整体上市', '分拆上市'])

export function conceptDisplay(data: SectorData, concepts: string[]) {
  const heat = data.heat?.status === 'ok' ? data.heat.concepts : {}
  const ordered = [...concepts].sort((a, b) => (heat[a]?.rank ?? Infinity) - (heat[b]?.rank ?? Infinity) || a.localeCompare(b, 'zh-CN'))
  const visible = ordered.filter(tag => heat[tag]?.hot && !generalConcepts.has(tag)).slice(0, 2)
  return { visible, hidden: ordered.filter(tag => !visible.includes(tag)) }
}

export function businessSectors(data: SectorData | null, code: string, keywords: string[]) {
  const stock = data?.stocks[code]
  if (!stock || stock.status === 'unavailable') return []
  const matchesBusiness = (tag: string) => {
    const subject = tag.replace(/概念$/, '')
    return subject.length >= 2 && keywords.some(keyword => keyword.includes(subject))
  }
  const concepts = stock.concepts.filter(tag => !generalConcepts.has(tag) && matchesBusiness(tag))
  return [...stock.industry.filter(matchesBusiness).map(name => ({ name, kind: 'industry' as const })),
    ...concepts.map(name => ({ name, kind: 'concepts' as const }))]
}
