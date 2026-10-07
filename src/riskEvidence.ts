import type { RiskSource } from './riskDisplay'

export function readableRiskEvidence(source: RiskSource | null | undefined): source is RiskSource {
  if (!source) return false
  try {
    const url = new URL(source.url)
    return ['https:', 'http:'].includes(url.protocol) && !/(^|\.)tushare\.(pro|com)$/.test(url.hostname) &&
      !/\.(json|csv|xlsx?)(?:$|\/)/i.test(url.pathname) && !!source.title.trim()
  } catch { return false }
}
