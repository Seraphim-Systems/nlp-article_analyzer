interface MetricCardProps {
  label: string
  value: string | number
  sub?: string
  colorClass?: string
  animationDelay?: number
}

export function MetricCard({ label, value, sub, colorClass = '', animationDelay }: MetricCardProps) {
  return (
    <div
      className="stat-card fade-up"
      style={animationDelay != null ? { animationDelay: `${animationDelay}ms` } : undefined}
    >
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${colorClass}`}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}
