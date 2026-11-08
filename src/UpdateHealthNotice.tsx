import { useEffect, useState } from 'react'

type ReleaseHealth = {
  trade_date: string
  generated_at: string
  calendar: { days: Record<string, string> }
  warnings?: string[]
}

export default function UpdateHealthNotice() {
  const [health, setHealth] = useState<ReleaseHealth | null>(null)
  const [unavailable, setUnavailable] = useState(false)
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const controller = new AbortController()
    const refresh = () => {
      setNow(new Date())
      fetch(`${import.meta.env.BASE_URL}data/update-health.json?health=${Date.now()}`, { signal: controller.signal, cache: 'no-store' })
        .then(response => {
          if (!response.ok) throw new Error('Health unavailable')
          return response.json() as Promise<ReleaseHealth>
        })
        .then(data => {
          if (!data.trade_date || !data.generated_at || !data.calendar?.days) throw new Error('Invalid health')
          setHealth(data)
          setUnavailable(false)
        })
        .catch(() => { if (!controller.signal.aborted) setUnavailable(true) })
    }
    refresh()
    const interval = window.setInterval(refresh, 5 * 60 * 1000)
    return () => { controller.abort(); window.clearInterval(interval) }
  }, [])

  const beijing = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai', dateStyle: 'short', timeStyle: 'short', hour12: false }).format(now)
  const [date, clock] = beijing.split(' ')
  // Before 08:00 allow the preceding overnight update window to finish.
  const cutoff = new Date(`${date}T00:00:00Z`)
  cutoff.setUTCDate(cutoff.getUTCDate() - (clock >= '08:00' ? 1 : 2))
  const cutoffKey = cutoff.toISOString().slice(0, 10).replaceAll('-', '')
  const days = health?.calendar.days
  const expected = days && Object.keys(days).filter(day => day <= cutoffKey && days[day] === '1').sort().at(-1)
  let message = ''
  if (unavailable || (health && (!days?.[cutoffKey] || !expected))) {
    message = '暂时无法确认数据更新状态，请核对各页面行情日期。'
  } else if (health && expected && health.trade_date < expected) {
    message = `数据更新延迟：当前行情日期 ${health.trade_date}，应更新至 ${expected}。请谨慎使用旧数据。`
  } else if (health?.warnings?.length) {
    message = `行情已更新至 ${health.trade_date}，部分数据暂缺（${health.warnings.length}项），请核对表内缺失标记。`
  }
  if (!message) return null
  return <aside role="status" style={{ margin: '12px auto', maxWidth: 1280, padding: '12px 16px', background: '#fff7ed', color: '#9a3412', border: '1px solid #fed7aa', borderRadius: 12, overflowWrap: 'anywhere' }}>{message}</aside>
}
