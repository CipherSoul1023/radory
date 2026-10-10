import { Activity } from 'lucide-react'
import { ProductEmptyPage } from '../components/app/ProductEmptyPage'

export function MarketActivityPage() {
  return (
    <ProductEmptyPage
      title="Market Activity"
      introduction="See activity across the markets, industries and occupiers relevant to your brokerage."
      emptyTitle="No market activity yet"
      emptyDescription="Once Radory begins monitoring your market, aggregated company and opportunity activity will appear here."
      icon={Activity}
    />
  )
}
