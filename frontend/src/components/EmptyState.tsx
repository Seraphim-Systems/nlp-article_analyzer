import type { ReactNode } from 'react'

interface EmptyStateProps {
  icon: ReactNode
  title: string
  description?: string
}

export function EmptyState({ icon, title, description }: EmptyStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 10,
        padding: '48px 24px',
        color: 'var(--text-muted)',
      }}
    >
      <div style={{ opacity: 0.25 }}>{icon}</div>
      <p style={{ fontSize: 13 }}>{title}</p>
      {description && (
        <p style={{ fontSize: 11, opacity: 0.6 }}>{description}</p>
      )}
    </div>
  )
}
