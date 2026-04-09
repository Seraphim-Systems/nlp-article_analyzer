import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  description?: string
  actions?: ReactNode
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="page-header" style={actions ? { display: 'flex', justifyContent: 'space-between', alignItems: 'center' } : undefined}>
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {actions}
    </div>
  )
}
