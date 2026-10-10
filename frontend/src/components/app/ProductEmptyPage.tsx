import type { LucideIcon } from 'lucide-react'
import { EmptyState } from './EmptyState'

type ProductEmptyPageProps = {
  title: string
  introduction: string
  emptyTitle: string
  emptyDescription: string
  icon: LucideIcon
}

export function ProductEmptyPage({
  title,
  introduction,
  emptyTitle,
  emptyDescription,
  icon,
}: ProductEmptyPageProps) {
  return (
    <section className="app-content-page">
      <header className="app-page-heading">
        <p className="app-page-eyebrow">Workspace intelligence</p>
        <h1>{title}</h1>
        <p>{introduction}</p>
      </header>
      <EmptyState
        icon={icon}
        title={emptyTitle}
        description={emptyDescription}
      />
    </section>
  )
}
