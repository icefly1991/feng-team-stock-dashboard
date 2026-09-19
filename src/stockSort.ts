// Weak price performance first: signed percentage values sort numerically.
// Market cap also defaults to smaller first, but is not a performance measure.
export function compareStockValues(
  a: { code: string }, b: { code: string },
  aValue: number | null | undefined, bValue: number | null | undefined,
  ascending = true,
) {
  const aValid = typeof aValue === 'number' && Number.isFinite(aValue)
  const bValid = typeof bValue === 'number' && Number.isFinite(bValue)
  if (aValid !== bValid) return aValid ? -1 : 1
  const difference = aValid && bValid ? (aValue - bValue) * (ascending ? 1 : -1) : 0
  return difference || a.code.localeCompare(b.code)
}
