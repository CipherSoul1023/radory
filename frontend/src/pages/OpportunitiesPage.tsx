import { Target } from 'lucide-react'
import { ProductEmptyPage } from '../components/app/ProductEmptyPage'

export function OpportunitiesPage() {
  return (
    <ProductEmptyPage
      title="Opportunities"
      introduction="Companies that match your brokerage profile and may be approaching a commercial property decision will appear here."
      emptyTitle="No opportunities yet"
      emptyDescription="Once your radar is active, Radory will rank relevant tenant-representation opportunities for your brokerage."
      icon={Target}
    />
  )
}
