interface LoadingSpinnerProps {
  message?: string
  size?: 'sm' | 'md'
}

export function LoadingSpinner({ message, size = 'md' }: LoadingSpinnerProps) {
  const px = size === 'sm' ? 12 : 16

  return (
    <div className="loading" style={size === 'sm' ? { padding: '20px 0' } : undefined}>
      <div className="spinner" style={{ width: px, height: px }} />
      {message && <span>{message}</span>}
    </div>
  )
}
