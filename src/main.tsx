import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './StockTable.css'
import App from './App.tsx'
import { RiskProvider } from './RiskWatch'
import { ListingStatusProvider } from './listingStatus'
import BackToTop from './BackToTop'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ListingStatusProvider><RiskProvider><App /><BackToTop /></RiskProvider></ListingStatusProvider>
  </StrictMode>,
)
