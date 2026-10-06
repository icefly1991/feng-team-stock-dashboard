type Stock = { ts_code?: string; market: string; loss_status: string }

export function isBeijingStock(stock: Stock) {
  return stock.ts_code ? stock.ts_code.endsWith('.BJ') : stock.market === '北交所'
}

export function smallCapVisible(stock: Stock, showLosses: boolean, showBeijing: boolean) {
  return (showLosses || stock.loss_status !== 'loss') && (showBeijing || !isBeijingStock(stock))
}
