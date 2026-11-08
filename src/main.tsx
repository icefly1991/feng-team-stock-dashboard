import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './StockTable.css'
import App from './App.tsx'
import { RiskProvider } from './RiskWatch'
import { ListingStatusProvider } from './listingStatus'
import BackToTop from './BackToTop'
import UpdateHealthNotice from './UpdateHealthNotice'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ListingStatusProvider><RiskProvider><UpdateHealthNotice /><App /><BackToTop /></RiskProvider></ListingStatusProvider>
  </StrictMode>,
)
