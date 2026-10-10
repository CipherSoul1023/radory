import type { LucideIcon } from 'lucide-react'

type EmptyStateProps = {
  icon: LucideIcon
  title: string
  description: string
}

export function EmptyState({
  icon: Icon,
  title,
  description,
}: EmptyStateProps) {
  return (
    <div className="app-empty-state">
      <span className="app-empty-state-icon">
        <Icon aria-hidden="true" size={42} strokeWidth={1.35} />
      </span>
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  )
}
