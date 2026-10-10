import { Building2 } from 'lucide-react'
import { ProductEmptyPage } from '../components/app/ProductEmptyPage'

export function CompaniesPage() {
  return (
    <ProductEmptyPage
      title="Companies"
      introduction="Companies discovered and tracked by your brokerage radar will appear here."
      emptyTitle="No companies discovered yet"
      emptyDescription="Radory will build a company intelligence universe based on your brokerage profile once your radar is active."
      icon={Building2}
    />
  )
}
