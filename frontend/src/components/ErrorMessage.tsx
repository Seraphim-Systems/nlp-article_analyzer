import { AlertCircle, RefreshCw } from 'lucide-react'

interface ErrorMessageProps {
  message: string
  onRetry?: () => void
  hint?: string
}

export function ErrorMessage({ message, onRetry, hint }: ErrorMessageProps) {
  const displayMessage = hint
    ? hint
    : message.includes('503')
      ? 'NER job not yet complete -- run the NER job first.'
      : message

  return (
    <div
      role="alert"
      className="card"
      style={{
        borderColor: 'var(--error)',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}
    >
      <AlertCircle size={16} color="var(--error)" style={{ flexShrink: 0 }} />
      <span style={{ fontSize: 13, color: 'var(--error)', flex: 1 }}>{displayMessage}</span>
      {onRetry && (
        <button className="btn btn-ghost" style={{ fontSize: 11, padding: '4px 10px', flexShrink: 0 }} onClick={onRetry}>
          <RefreshCw size={12} /> Retry
        </button>
      )}
    </div>
  )
}
