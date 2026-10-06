import { useEffect, useState } from 'react'

type StockSectors = { industry: string[]; concepts: string[]; status: 'ok' | 'partial' | 'unavailable'; source_url: string }
export type ConceptHeat = { rank: number; return_pct: number; amount_yi: number; hot: boolean }
export type SectorData = { schema_version: number; source: string; updated_at: string; stocks: Record<string, StockSectors>;
  heat?: { status: 'ok' | 'unavailable'; trade_date?: string; source_url: string; method?: string; concepts: Record<string, ConceptHeat> } }
let request: Promise<SectorData> | undefined

export function useStockSectors() {
  const [data, setSectorData] = useState<SectorData | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    let live = true
    request ??= fetch(`${import.meta.env.BASE_URL}data/stock-sectors.json`).then(async response => {
      if (!response.ok) throw new Error('板块数据未就绪')
      const result: SectorData = await response.json()
      if (result.schema_version !== 1 || !result.stocks || Object.values(result.stocks).some(value =>
        !Array.isArray(value.industry) || !Array.isArray(value.concepts) ||
        [...value.industry, ...value.concepts].some(tag => typeof tag !== 'string') ||
        !['ok', 'partial', 'unavailable'].includes(value.status))) throw new Error('板块数据格式异常')
      return result
    }).catch(e => { request = undefined; throw e })
    request.then(value => { if (live) setSectorData(value) }).catch(() => { if (live) setError(true) })
    return () => { live = false }
  }, [])
  return { data, error }
}

export function matchesSector(data: SectorData | null, code: string, selected: string) {
  if (!selected) return true
  const value = data?.stocks[code]
  if (selected === 'unknown') return !value || value.status === 'unavailable'
  if (!value || value.status === 'unavailable') return false
  const [kind, ...name] = selected.split(':')
  return (kind === 'industry' ? value.industry : value.concepts).includes(name.join(':'))
}
