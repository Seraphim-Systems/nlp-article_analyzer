import { CheckCircle, Clock, Loader, XCircle, Square } from 'lucide-react'

type Status = 'queued' | 'running' | 'success' | 'failed' | 'cancelled'

const STATUS_CONFIG: Record<Status, { color: string; bg: string; border: string }> = {
  queued:    { color: 'var(--gold)',      bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.25)' },
  running:   { color: 'var(--accent-hi)', bg: 'rgba(96,165,250,0.1)',  border: 'rgba(96,165,250,0.25)' },
  success:   { color: 'var(--success)',   bg: 'rgba(34,197,94,0.1)',   border: 'rgba(34,197,94,0.25)' },
  failed:    { color: 'var(--error)',     bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.25)' },
  cancelled: { color: 'var(--text-muted)',bg: 'rgba(100,116,139,0.1)', border: 'rgba(100,116,139,0.25)' },
}

export function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'queued':    return <Clock       size={13} style={{ color: 'var(--gold)' }} />
    case 'running':   return <Loader      size={13} style={{ color: 'var(--accent-hi)', animation: 'spin 0.8s linear infinite' }} />
    case 'success':   return <CheckCircle size={13} style={{ color: 'var(--success)' }} />
    case 'failed':    return <XCircle     size={13} style={{ color: 'var(--error)' }} />
    case 'cancelled': return <Square      size={13} style={{ color: 'var(--text-muted)' }} />
    default:          return null
  }
}

export function StatusBadge({ status }: { status: Status }) {
  const cfg = STATUS_CONFIG[status]

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontSize: 11,
        fontFamily: 'var(--font-mono)',
        padding: '2px 8px',
        borderRadius: 'var(--radius-sm)',
        background: cfg.bg,
        color: cfg.color,
        border: `1px solid ${cfg.border}`,
      }}
    >
      <StatusIcon status={status} />
      {status}
    </span>
  )
}
