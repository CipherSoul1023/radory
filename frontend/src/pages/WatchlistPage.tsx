import { Star } from 'lucide-react'
import { ProductEmptyPage } from '../components/app/ProductEmptyPage'

export function WatchlistPage() {
  return (
    <ProductEmptyPage
      title="Watchlist"
      introduction="Keep track of companies your team wants to follow closely."
      emptyTitle="Your watchlist is empty"
      emptyDescription="Companies you choose to follow will appear here along with their latest signals and updates."
      icon={Star}
    />
  )
}
