import { useEffect, useMemo, useState } from 'react'
import { RiskScoreCell } from './RiskWatch'
import { riskDate as date, type RiskRow } from './riskDisplay'
import './RiskTestPage.css'

type Data = {
  schema_version: number; updated_at: string; as_of: string; sample_note: string; coverage_note: string
  rules: { version: string; formula: string; weights_enabled: boolean; pending_rules: string[] }
  rows: RiskRow[]; errors: { ts_code: string; stage: string; error: string }[]
}
export default function RiskTestPage() {
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<'history' | 'current'>('history')
  const [descending, setDescending] = useState(true)
  useEffect(() => {
    document.title = '风险预警 · 算法测试页'
    const controller = new AbortController()
    fetch(`${import.meta.env.BASE_URL}data/risk-test.json`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('测试数据未就绪')
      const value: Data = await response.json()
      if (value.schema_version !== 1 || value.rules.weights_enabled !== false || !Array.isArray(value.rows) ||
        value.rows.some(r => !Number.isFinite(r.risk.score) || r.risk.score < 0 || r.risk.score > 100)) throw new Error('测试数据版本或评分无效')
      setData(value)
    }).catch((e: unknown) => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : '加载失败') })
    return () => controller.abort()
  }, [])
  const rows = useMemo(() => (data?.rows || []).filter(r => r.historical === (mode === 'history') &&
    `${r.name} ${r.ts_code}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) =>
      (descending ? b.risk.score - a.risk.score : a.risk.score - b.risk.score) || a.ts_code.localeCompare(b.ts_code) || a.as_of.localeCompare(b.as_of)), [data, mode, query, descending])
  return <main className="risk-page">
    <nav><a href="#small-cap-market">← 小市值双榜</a><span>独立测试页</span></nav>
    <header><div className="risk-eyebrow">风险预警 · 算法测试</div><h1>风险预警评分</h1><p>按你确认的规则直接累加；保留组合加分与风险最低分。</p></header>
    {error ? <div role="alert" className="risk-notice">{error}</div> : !data ? <p role="status">正在加载测试数据…</p> : <>
      <div className="risk-notice"><b>当前为样本测试</b><p>{data.coverage_note}</p><p>低分不能作为安全结论；已核实的终止上市事实单独按最高风险标记。退市案例仅保留用于验证，不进入股票榜。</p></div>
      <div className="risk-toolbar"><div className="risk-tabs"><button aria-pressed={mode === 'history'} onClick={() => setMode('history')}>早期案例截面</button><button aria-pressed={mode === 'current'} onClick={() => setMode('current')}>当前股票样本</button></div><input aria-label="搜索测试股票" placeholder="搜索名称 / 代码" value={query} onChange={e => setQuery(e.target.value)} /></div>
      <p className="risk-data-time">{mode === 'history' ? '按每行截止日已披露的信息计算，不回填后来的立案或审计事件。' : data.sample_note} · 生成 {new Date(data.updated_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })} 北京时间</p>
      <div className="risk-table-wrap"><table className="risk-table"><thead><tr><th scope="col">股票 / 信息截止日</th><th scope="col" aria-sort={descending ? 'descending' : 'ascending'}><button onClick={() => setDescending(v => !v)}>风险评分 {descending ? '↓' : '↑'}</button></th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><th scope="row"><strong>{row.name}</strong><span>{row.ts_code}</span><small>{row.market} · {date(row.as_of)}</small>{row.historical && <em>历史截面</em>}</th><td><RiskScoreCell row={row} /></td></tr>)}</tbody></table>{!rows.length && <p className="risk-empty">没有匹配的测试记录</p>}</div>
      <footer><details><summary>计算口径与待确认规则</summary><p>风险项累加与组合加分相加，应用风险最低分后封顶100；不加权。分档取较高档，不将同一指标的两个档位叠加。三年现金转化率取三年累计经营现金流 / 累计归母净利；分母≤0时不计算。应收与营收增长均比较去年同期；收入接近阈值使用年度或近十二个月，不拿半年营收直接比年度线。普通及严重问询互斥，二次问询及组合分独立叠加。</p><p>已跌破收入线且亏损的+35分使用正式年度数据或已核实业绩预告；扣除后营业收入缺失且原始收入未低于线时标记待核实。历史供应商数据可能被后续更正，不能代替原始披露档案。</p><ul>{data.rules.pending_rules.map(r => <li key={r}>{r}</li>)}</ul><p>当前没有历史评分基线，暂不生成趋势箭头。测试页不执行自动剔除。</p></details>{data.errors.length > 0 && <p className="risk-source-errors">来源异常：{data.errors.map(e => `${e.ts_code} ${e.stage}：${e.error}`).join('；')}</p>}</footer>
    </>}
  </main>
}
