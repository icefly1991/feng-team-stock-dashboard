import events from '../config/listing-risk-events.json' with { type: 'json' }
import { createContext, createElement, useContext, useEffect, useState, type ReactNode } from 'react'

type Stock = { code?: string; ts_code?: string; name: string; list_status?: string; listing_status?: string; delist_date?: string }
type Decision = { published_at: string; status: string; title: string; source?: { title: string; url: string } }
type Snapshot = { as_of: string; stocks: Record<string, Stock> }
const ListingContext = createContext<Snapshot | null>(null)
export function ListingStatusProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${import.meta.env.BASE_URL}data/listing-status.json`, { signal: controller.signal }).then(r => {
      if (!r.ok) throw new Error('上市状态暂不可用')
      return r.json()
    }).then((data: Snapshot) => {
      if (!/^\d{8}$/.test(data.as_of) || !data.stocks) return
      setSnapshot({ ...data, stocks: Object.fromEntries(Object.entries(data.stocks).map(([key, value]) => [key.split('.')[0], value])) })
    }).catch(() => { /* Verified decisions and name safeguards remain active. */ })
    return () => controller.abort()
  }, [])
  return createElement(ListingContext.Provider, { value: snapshot }, children)
}
export const useListingStatus = () => useContext(ListingContext)
export function listingRisk(stock: Stock, asOf = '99999999', snapshot: Snapshot | null = null): Decision | null {
  const code = stock.ts_code?.split('.')[0] || stock.code
  const known = Object.entries(events).find(([key]) => key.split('.')[0] === code)?.[1]
  if (known && known.published_at <= asOf) return known
  if (snapshot && snapshot.as_of <= asOf && code) stock = { ...stock, ...snapshot.stocks[code] }
  if ((stock.list_status === 'D' && (!stock.delist_date || stock.delist_date <= asOf)) || (stock.delist_date && stock.delist_date <= asOf))
    return { published_at: stock.delist_date || asOf, status: 'delisted', title: '证券基础信息标记已退市' }
  if (stock.name.trim().endsWith('退') || stock.name.trim().startsWith('退市'))
    return { published_at: asOf, status: 'delisting', title: '证券简称包含退市整理标识' }
  if (['termination_decided', 'delisting', 'delisted'].includes(stock.listing_status || ''))
    return { published_at: asOf, status: stock.listing_status!, title: '已确认终止上市或退市状态' }
  return null
}
