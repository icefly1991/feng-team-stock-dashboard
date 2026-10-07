import { readableRiskEvidence } from './riskEvidence'
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { chineseRiskText, riskDate, riskHighest, riskLevel, riskMetricLabels, riskMetricText, riskMissingLabels, riskScoreText, type RiskRow, type RiskSource } from './riskDisplay'
import './RiskWatch.css'
import { listingRisk, useListingStatus } from './listingStatus'

type RiskData = {
  schema_version: number; updated_at: string; as_of: string; rules: { weights_enabled: boolean; version: string }
  stocks: Record<string, RiskRow>; unavailable: Record<string, string>; coverage_note: string
}
type Selection = { row?: RiskRow; code: string; name: string; reason?: string }
const RiskContext = createContext<{ data: RiskData | null; error: string; show: (selection: Selection) => void }>({ data: null, error: '', show: () => {} })

function SourceLink({ source }: { source: RiskSource }) {
  const url = source.url.startsWith('data/') ? `${import.meta.env.BASE_URL}${source.url}` : source.url
  const title = source.title.replace(/ · (income|balancesheet|cashflow|fina_indicator)\b/g, '')
  return <a href={url} target="_blank" rel="noreferrer">{chineseRiskText(title)} ↗</a>
}
function RiskDetails({ row }: { row: RiskRow }) {
  const risk = row.risk
  const highest = chineseRiskText(riskHighest(risk))
  const reasons = [...new Set([...risk.floors.map(f => f.title), ...[...risk.triggers].sort((a, b) => b.points - a.points).map(t => t.title)])]
  const sources = [...risk.floors.map(f => f.source), ...risk.triggers.map(t => t.source), ...row.events.map(e => e.source)].filter(readableRiskEvidence)
  const evidence = [...new Map(sources.map(s => [s.url, s])).values()]
  return <div className="risk-detail">
    <div className={`risk-verdict ${risk.score >= 60 ? 'risk-verdict-danger' : ''}`}>
      <div className="risk-dialog-score"><strong>{!risk.complete && risk.score < 100 ? '≥' : ''}{riskScoreText(risk.score)}<small>/100分</small></strong><span>{riskLevel(risk)}</span></div>
      <p className="risk-dialog-highest">{highest}</p>
      <p className="risk-dialog-meta">最新风险日期 {riskDate(risk.latest_warning)} · 信息截至 {riskDate(row.as_of)}</p>
    </div>
    {!risk.complete && <p className="risk-summary-note">公告核查尚不完整，低分不能作为安全结论。</p>}
    {reasons.length > 0 && <><h3>主要风险</h3><ul className="risk-main-reasons">{reasons.slice(0, 3).map(reason => <li key={reason}>{chineseRiskText(reason)}</li>)}</ul></>}
    {evidence.length > 0 && <><h3>相关公告与报道</h3><ul className="risk-evidence">{evidence.map(source => <li key={source.url}><SourceLink source={source} /></li>)}</ul></>}
    <details className="risk-diagnostics">
      <summary>评分依据与指标</summary>
      <div className="risk-formula">风险项 {risk.raw_score} + 组合加分 {risk.combination_points}，最低分 {risk.floor}，最终 {riskScoreText(risk.score)}分。四个模块不加权。</div>
      <div className="risk-module-grid">{risk.modules.map(m => <div key={m.key}><span>{m.label}</span><b>{m.score}</b></div>)}</div>
      <h3>全部触发项</h3><ul>{risk.triggers.map((item, i) => <li key={i}>+{item.points} {chineseRiskText(item.title)}</li>)}</ul>
      {risk.combinations.length > 0 && <><h3>组合加分</h3><ul>{risk.combinations.map(c => <li key={c.title}>+{c.points} {chineseRiskText(c.title)}</li>)}</ul></>}
      {risk.floors.length > 0 && <><h3>最低风险分</h3><ul>{risk.floors.map((f, i) => <li key={i}>至少{f.score}分 · {chineseRiskText(f.title)}</li>)}</ul></>}
      <p className="risk-dialog-meta">财报期 {riskDate(row.context.period)} · 披露 {riskDate(row.context.ann_date)}</p>
      <details className="risk-indicators"><summary>查看详细指标</summary><dl>{Object.entries(riskMetricLabels).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{riskMetricText(key, row.metrics[key])}</dd></div>)}</dl></details>
      {!risk.complete && <details className="risk-missing"><summary>待核查项目</summary><ul>{risk.missing.map(key => <li key={key}>{riskMissingLabels[key] || '相关数据待核实'}</li>)}</ul></details>}
    </details>
  </div>
}
function RiskDialog({ selection, onClose }: { selection: Selection; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const element = dialog.current!
    element.showModal()
    closeButton.current?.focus()
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const closeOnNavigation = () => element.close()
    window.addEventListener('hashchange', closeOnNavigation)
    return () => {
      window.removeEventListener('hashchange', closeOnNavigation)
      document.body.style.overflow = previous
      if (element.open) element.close()
    }
  }, [])
  return createPortal(<dialog ref={dialog} className="risk-dialog" aria-labelledby="risk-dialog-title" onClose={e => { if (!e.currentTarget.open) onClose() }}
    onClick={e => { if (e.target === e.currentTarget) e.currentTarget.close() }}>
    <div className="risk-dialog-shell">
      <header className="risk-dialog-header"><div><h2 id="risk-dialog-title">{selection.name} · 风险评分详情</h2><p>{selection.code}</p></div><button ref={closeButton} type="button" className="risk-dialog-close" aria-label="关闭风险评分详情" onClick={() => dialog.current?.close()}>关闭 ×</button></header>
      <div className="risk-dialog-body">{selection.row ? <RiskDetails row={selection.row} /> : <div className="risk-dialog-notice"><h3>暂未取得可用评分</h3><p>{selection.reason || '这只股票的风险数据尚未完成核查，不能按零风险处理。'}</p></div>}</div>
    </div>
  </dialog>, document.body)
}
export function RiskProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<RiskData | null>(null)
  const [error, setError] = useState('')
  const [selection, setSelection] = useState<Selection | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${import.meta.env.BASE_URL}data/risk-dashboard.json`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('风险评分数据暂不可用')
      const value: RiskData = await response.json()
      if (value.schema_version !== 1 || value.rules?.weights_enabled !== false || !value.stocks ||
        !/^\d{8}$/.test(value.as_of) || Object.values(value.stocks).some(r => !Number.isFinite(r.risk.score) || r.risk.score < 0 || r.risk.score > 100 || r.as_of !== value.as_of)) throw new Error('风险评分数据版本或日期无效')
      setData(value)
    }).catch((e: unknown) => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : '风险评分加载失败') })
    return () => controller.abort()
  }, [])
  return <RiskContext.Provider value={{ data, error, show: setSelection }}>{children}{selection && <RiskDialog key={selection.row?.id || selection.code} selection={selection} onClose={() => setSelection(null)} />}</RiskContext.Provider>
}
export function RiskScoreCell({ code, name, row, compact = false }: { code?: string; name?: string; row?: RiskRow; compact?: boolean }) {
  const context = useContext(RiskContext)
  const listing = useListingStatus()
  const original = row || context.data?.stocks[code || '']
  const terminal = listingRisk({ code: code || row?.ts_code.split('.')[0], name: original?.historical ? '' : name || original?.name || '' }, row?.as_of || context.data?.as_of, listing)
  const record = original && terminal ? { ...original, risk: { ...original.risk, score: 100, level: 'HARD AVOID', floor: 100,
    floors: [{ score: 100, title: terminal.title, source: terminal.source || null }, ...original.risk.floors],
    latest_warning: terminal.published_at > (original.risk.latest_warning || '') ? terminal.published_at : original.risk.latest_warning } } : original
  const stockCode = code || row?.ts_code.split('.')[0] || ''
  const stockName = name || row?.name || stockCode
  if (!record) return <button type="button" className="risk-cell risk-unavailable" onClick={() => context.show({ code: stockCode, name: stockName, reason: context.data?.unavailable[stockCode] || context.error || '这只股票的评分尚未完成核查。' })} aria-label={`查看${stockName}的风险核查状态`}>待核实<span>查看原因</span></button>
  const risk = record.risk
  const tone = risk.score >= 90 ? 'hard' : risk.score >= 60 ? 'severe' : risk.score >= 40 ? 'high' : risk.score >= 20 ? 'watch' : 'low'
  const highest = chineseRiskText(riskHighest(risk))
  return <button type="button" className={`risk-cell risk-${tone}${compact ? ' risk-cell-compact' : ''}`} aria-haspopup="dialog"
    aria-label={`查看${stockName}的风险评分详情`} title={`${highest}；信息截至${riskDate(record.as_of)}`}
    onClick={() => context.show({ row: record, code: stockCode, name: stockName })}>
    <span className="risk-score-line"><strong>{risk.complete || risk.score === 100 ? '' : '≥'}{riskScoreText(risk.score)}<small>/100</small></strong><span className="risk-level">{riskLevel(risk)}</span>{!compact && <span className="risk-expand">查看详情 ↗</span>}</span>
    <span className="risk-cell-reason">{highest}</span><span className="risk-meta">{riskDate(risk.latest_warning)}{compact ? ' · 详情' : ` · ${risk.complete ? '核查完成' : '已知风险下限'}`}</span>
  </button>
}
export function RiskCoverageNote() {
  const { data, error } = useContext(RiskContext)
  return <p className="risk-coverage-note">风险评分信息截至 {riskDate(data?.as_of || null)}{data && ` · 初版 ${data.rules.version} · 已计算 ${Object.keys(data.stocks).length} 只${Object.keys(data.unavailable).length ? `，另有 ${Object.keys(data.unavailable).length} 只财报待核实` : ''}`}：{error || data?.coverage_note || '正在读取风险数据，未取得评分的股票显示待核实。'} 点击评分查看详情。<a href="#risk-test">历史案例</a></p>
}
