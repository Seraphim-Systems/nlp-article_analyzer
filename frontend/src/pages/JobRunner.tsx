import { useState, useEffect, useCallback, useRef } from 'react'
import { api, Job } from '../api/client'
import { Play, Square, RefreshCw, Clock, CheckCircle, XCircle, Loader, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react'

// ── Job definitions ─────────────────────────────────────────────────────────

const JOBS = [
  {
    id:    'scrape',
    label: 'Scrape',
    desc:  'Collect articles from RSS feeds into raw_articles',
    color: 'var(--gold)',
    rgba:  'rgba(245,158,11,0.07)',
  },
  {
    id:    'clean',
    label: 'Clean',
    desc:  'Rank and enrich raw articles into clean_articles',
    color: 'var(--accent-hi)',
    rgba:  'rgba(96,165,250,0.07)',
  },
  {
    id:    'classify',
    label: 'Classify',
    desc:  'BERT NER extraction and build ner_preprocessed_text',
    color: 'var(--ner-org)',
    rgba:  'rgba(56,189,248,0.07)',
  },
  {
    id:    'ner',
    label: 'NER',
    desc:  'Entity tagging pipeline into ner_articles collection',
    color: 'var(--ner-loc)',
    rgba:  'rgba(52,211,153,0.07)',
  },
  {
    id:    'evaluate',
    label: 'Evaluate',
    desc:  'Compute model precision, recall, and F1 metrics',
    color: 'var(--ner-misc)',
    rgba:  'rgba(167,139,250,0.07)',
  },
]

type JobDef = (typeof JOBS)[number]

// ── Helpers ─────────────────────────────────────────────────────────────────

function loadStoredJobs(): Job[] {
  try {
    return JSON.parse(sessionStorage.getItem('nlp_jobs') ?? '[]')
  } catch {
    return []
  }
}

function saveJobs(jobs: Job[]) {
  try {
    sessionStorage.setItem('nlp_jobs', JSON.stringify(jobs))
  } catch {}
}

const TERMINAL = new Set<Job['status']>(['success', 'failed', 'cancelled'])

function mergeJobs(prev: Job[], incoming: Job[]): Job[] {
  const inMap = new Map(incoming.map(j => [j.job_id, j]))
  const merged = prev.map(j => {
    const fresh = inMap.get(j.job_id)
    if (!fresh) return j
    // Never revert a terminal state — local wins if server is still non-terminal
    if (TERMINAL.has(j.status) && !TERMINAL.has(fresh.status)) return j
    return fresh
  })
  const prevIds = new Set(prev.map(j => j.job_id))
  for (const j of incoming) {
    if (!prevIds.has(j.job_id)) merged.unshift(j)
  }
  return merged
}

function formatResult(result: Record<string, unknown>): string {
  const priority = ['new', 'processed', 'saved', 'total', 'skipped']
  const parts = priority
    .filter(k => result[k] != null)
    .map(k => `${k}: ${result[k]}`)
  if (parts.length) return parts.join('  ')
  return Object.entries(result)
    .filter(([k]) => !['status', 'error'].includes(k))
    .map(([k, v]) => `${k}: ${v}`)
    .join('  ')
    .slice(0, 120)
}

// ── Sub-components ──────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'queued':    return <Clock       size={13} style={{ color: 'var(--gold)' }} />
    case 'running':   return <Loader      size={13} style={{ color: 'var(--accent-hi)', animation: 'spin 0.8s linear infinite' }} />
    case 'success':   return <CheckCircle size={13} style={{ color: 'var(--success)' }} />
    case 'failed':    return <XCircle     size={13} style={{ color: 'var(--error)' }} />
    case 'cancelled': return <Square      size={13} style={{ color: 'var(--text-muted)' }} />
    default:          return null
  }
}

function ElapsedTimer({ startedAt }: { startedAt: string }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const start = new Date(startedAt).getTime()
    const update = () => setElapsed(Math.round((Date.now() - start) / 1000))
    update()
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [startedAt])

  const m = Math.floor(elapsed / 60)
  const s = elapsed % 60
  return <>{m > 0 ? `${m}m ` : ''}{s}s</>
}

function JobCard({
  job,
  onTrigger,
  isActive,
  activeStatus,
  anyRunning,
}: {
  job: JobDef
  onTrigger: (id: string) => void
  isActive: boolean
  activeStatus: 'queued' | 'running' | null
  anyRunning: boolean
}) {
  const canRun = !anyRunning

  return (
    <div className="card" style={{
      borderColor: isActive ? job.color : 'var(--border)',
      background:  isActive ? job.rgba   : 'var(--bg-surface)',
      transition:  'border-color 0.2s, background 0.2s',
    }}>
      <div className="flex justify-between items-center" style={{ marginBottom: isActive ? 10 : 0 }}>
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: '1.15rem', color: 'var(--text-primary)' }}>
            {job.label}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{job.desc}</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          {isActive && activeStatus && (
            <span style={{
              fontSize: 9,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: activeStatus === 'running' ? job.color : 'var(--gold)',
            }}>
              {activeStatus}
            </span>
          )}
          <button
            className="btn btn-primary"
            style={{
              background:    isActive ? 'var(--bg-elevated)' : job.color,
              border:        isActive ? '1px solid var(--border-mid)' : 'none',
              color:         isActive ? 'var(--text-muted)' : '#000',
              fontSize:      12,
              opacity:       !canRun && !isActive ? 0.4 : 1,
              cursor:        !canRun && !isActive ? 'not-allowed' : 'pointer',
            }}
            disabled={!canRun}
            onClick={() => onTrigger(job.id)}
          >
            <Play size={12} />
            {isActive ? 'Running' : 'Run'}
          </button>
        </div>
      </div>

      {isActive && activeStatus === 'running' && (
        <div className="progress-track">
          <div
            className="progress-fill"
            style={{ width: '100%', background: job.color, animation: 'progressPulse 1.5s ease-in-out infinite alternate' }}
          />
        </div>
      )}
      {isActive && activeStatus === 'queued' && (
        <div className="progress-track">
          <div
            className="progress-fill"
            style={{ width: '30%', background: 'var(--gold)', animation: 'progressPulse 1.5s ease-in-out infinite alternate' }}
          />
        </div>
      )}
    </div>
  )
}

function LogPane({ logs, isRunning }: { logs: string[]; isRunning: boolean }) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs.length])

  if (!logs.length) {
    return (
      <div style={{ padding: '10px 0', fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>
        {isRunning ? 'Waiting for first log entry...' : 'No log entries.'}
      </div>
    )
  }

  return (
    <div style={{
      marginTop: 8,
      maxHeight: 220,
      overflowY: 'auto',
      background: 'var(--bg-base)',
      borderRadius: 'var(--radius)',
      padding: '10px 12px',
      border: '1px solid var(--border)',
    }}>
      {logs.map((line, i) => (
        <div key={i} style={{
          display: 'flex',
          gap: 10,
          padding: '2px 0',
          borderBottom: i < logs.length - 1 ? '1px solid var(--border)' : undefined,
        }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', minWidth: 28, textAlign: 'right', flexShrink: 0 }}>
            {i + 1}
          </span>
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {line}
          </span>
        </div>
      ))}
      {isRunning && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0', marginTop: 2 }}>
          <Loader size={10} style={{ color: 'var(--accent-hi)', animation: 'spin 0.8s linear infinite' }} />
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--accent-hi)' }}>running</span>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}

function HistoryRow({ job, isActive, onCancel }: { job: Job; isActive: boolean; onCancel: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  const elapsed = job.finished_at
    ? Math.round((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000)
    : null
  const isRunning = job.status === 'running' || job.status === 'queued'
  const hasDetail = (job.logs && job.logs.length > 0) || job.result

  return (
    <>
      <tr
        style={{ background: isActive ? 'rgba(96,165,250,0.04)' : undefined, cursor: hasDetail ? 'pointer' : undefined }}
        onClick={() => hasDetail && setExpanded(e => !e)}
      >
        <td>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            {hasDetail
              ? (expanded ? <ChevronDown size={11} color="var(--text-muted)" /> : <ChevronRight size={11} color="var(--text-muted)" />)
              : <span style={{ width: 11 }} />}
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{job.job_id}</span>
          </span>
        </td>
        <td style={{ color: 'var(--text-primary)', fontSize: 13 }}>{job.job_name}</td>
        <td>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11,
              fontFamily: 'var(--font-mono)', padding: '2px 8px', borderRadius: 'var(--radius-sm)',
              background: job.status === 'success' ? 'rgba(34,197,94,0.1)' : job.status === 'failed' ? 'rgba(239,68,68,0.1)' : job.status === 'running' ? 'rgba(96,165,250,0.1)' : job.status === 'cancelled' ? 'rgba(100,116,139,0.1)' : 'rgba(245,158,11,0.1)',
              color: job.status === 'success' ? 'var(--success)' : job.status === 'failed' ? 'var(--error)' : job.status === 'running' ? 'var(--accent-hi)' : job.status === 'cancelled' ? 'var(--text-muted)' : 'var(--gold)',
              border: '1px solid',
              borderColor: job.status === 'success' ? 'rgba(34,197,94,0.25)' : job.status === 'failed' ? 'rgba(239,68,68,0.25)' : job.status === 'running' ? 'rgba(96,165,250,0.25)' : job.status === 'cancelled' ? 'rgba(100,116,139,0.25)' : 'rgba(245,158,11,0.25)',
            }}>
              <StatusIcon status={job.status} />
              {job.status}
            </span>
            {(job.status === 'running' || job.status === 'queued') && (
              <button
                title="Stop job"
                style={{ background: 'none', border: 'none', padding: 2, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', color: 'rgba(239,68,68,0.65)', transition: 'color 0.15s, filter 0.15s' }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'rgb(239,68,68)'; (e.currentTarget as HTMLButtonElement).style.filter = 'drop-shadow(0 0 4px rgba(239,68,68,0.5))' }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'rgba(239,68,68,0.65)'; (e.currentTarget as HTMLButtonElement).style.filter = 'none' }}
                onClick={e => { e.stopPropagation(); onCancel(job.job_id) }}
              >
                <Square size={15} fill="currentColor" strokeWidth={0} />
              </button>
            )}
          </span>
        </td>
        <td style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          {new Date(job.started_at).toLocaleTimeString()}
        </td>
        <td style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          {isRunning ? <ElapsedTimer startedAt={job.started_at} /> : elapsed != null ? `${elapsed}s` : '-'}
        </td>
        <td style={{ fontSize: 11, color: 'var(--text-muted)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {job.result ? formatResult(job.result as Record<string, unknown>) : '-'}
        </td>
      </tr>
      {expanded && (
        <tr style={{ background: 'var(--bg-base)' }}>
          <td colSpan={6} style={{ padding: '0 12px 12px 36px' }}>
            {job.logs && job.logs.length > 0 && (
              <LogPane logs={job.logs} isRunning={isRunning} />
            )}
            {job.result && (
              <div style={{ marginTop: job.logs?.length ? 8 : 0, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)', background: 'var(--bg-elevated)', borderRadius: 'var(--radius)', padding: '8px 12px', lineHeight: 1.8 }}>
                {Object.entries(job.result as Record<string, unknown>).filter(([k]) => k !== 'status').map(([k, v]) => (
                  <div key={k}><span style={{ color: 'var(--text-muted)' }}>{k}:</span> {String(v)}</div>
                ))}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function JobRunner() {
  const [jobs, setJobs]         = useState<Job[]>(loadStoredJobs)
  const [running, setRunning]   = useState<{ id: string; name: string } | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)

  const loadHistory = useCallback(async () => {
    try {
      const res = await api.jobs()
      setJobs(prev => {
        const merged = mergeJobs(prev, res.jobs)
        saveJobs(merged)
        return merged
      })
      setApiError(null)
    } catch (e) {
      setApiError(e instanceof Error ? e.message : 'API unreachable')
    }
  }, [])

  // History poll: every 5s
  useEffect(() => {
    loadHistory()
    const id = setInterval(loadHistory, 5000)
    return () => clearInterval(id)
  }, [loadHistory])

  // Active job fast-poll: every 2s while running
  useEffect(() => {
    if (!running) return
    const poll = setInterval(async () => {
      try {
        const job = await api.jobById(running.id)
        setJobs(prev => {
          const idx = prev.findIndex(j => j.job_id === running.id)
          const next = idx >= 0
            ? prev.map((j, i) => i === idx ? job : j)
            : [job, ...prev]
          saveJobs(next)
          return next
        })
        if (job.status !== 'queued' && job.status !== 'running') {
          setRunning(null)
        }
      } catch {}
    }, 2000)
    return () => clearInterval(poll)
  }, [running])

  const trigger = async (jobName: string) => {
    try {
      const res = await api.triggerJob(jobName)
      setRunning({ id: res.job_id, name: jobName })
      setApiError(null)
    } catch (e) {
      setApiError(e instanceof Error ? e.message : 'Failed to trigger job')
    }
  }

  const cancelJob = async (jobId: string) => {
    try {
      await api.cancelJob(jobId)
    } catch (e) {
      // 404 means the server no longer knows this job (e.g. after restart) — treat as already done
      if (!(e instanceof Error && e.message.startsWith('404'))) {
        setApiError(e instanceof Error ? e.message : 'Failed to cancel job')
        return
      }
    }
    setJobs(prev => {
      const next = prev.map(j => j.job_id === jobId ? { ...j, status: 'cancelled' as const, finished_at: new Date().toISOString() } : j)
      saveJobs(next)
      return next
    })
    if (running?.id === jobId) setRunning(null)
  }

  const activeJob = running ? JOBS.find(j => j.id === running.name) ?? null : null
  const activeJobRecord = running ? jobs.find(j => j.job_id === running.id) ?? null : null

  return (
    <div className="fade-up">
      <div className="page-header flex justify-between items-center">
        <div>
          <h2>Job Runner</h2>
          <p>Trigger pipeline jobs and monitor live status</p>
        </div>
        <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={loadHistory}>
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {apiError && (
        <div className="card" style={{ marginBottom: 16, borderColor: 'var(--error)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <AlertCircle size={14} color="var(--error)" />
          <span style={{ fontSize: 13, color: 'var(--error)' }}>{apiError}</span>
        </div>
      )}

      {/* ── Job cards ── */}
      <div className="grid-2" style={{ marginBottom: 20 }}>
        {JOBS.map(job => (
          <JobCard
            key={job.id}
            job={job}
            onTrigger={trigger}
            isActive={running?.name === job.id}
            activeStatus={
              running?.name === job.id
                ? (activeJobRecord?.status === 'running' ? 'running' : 'queued')
                : null
            }
            anyRunning={running !== null}
          />
        ))}
      </div>

      {/* ── Active job panel ── */}
      {running && activeJobRecord && (
        <div className="card" style={{
          marginBottom: 20,
          borderColor: activeJob?.color ?? 'var(--accent)',
          background: activeJob?.rgba ?? 'var(--accent-glow)',
        }}>
          <div className="flex items-center gap-3" style={{ marginBottom: activeJobRecord.status === 'running' ? 10 : 0 }}>
            <StatusIcon status={activeJobRecord.status} />
            <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>
              <strong>{activeJobRecord.job_name}</strong>
              <span style={{ color: 'var(--text-muted)', marginLeft: 8 }}>{activeJobRecord.status}</span>
            </span>
            <span style={{ marginLeft: 'auto', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              <ElapsedTimer startedAt={activeJobRecord.started_at} /> elapsed
            </span>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              #{activeJobRecord.job_id}
            </span>
            {(activeJobRecord.status === 'running' || activeJobRecord.status === 'queued') && (
              <button
                title="Stop job"
                style={{ background: 'none', border: 'none', padding: 4, cursor: 'pointer', display: 'flex', alignItems: 'center', color: 'rgba(239,68,68,0.7)', transition: 'color 0.15s, filter 0.15s' }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'rgb(239,68,68)'; (e.currentTarget as HTMLButtonElement).style.filter = 'drop-shadow(0 0 5px rgba(239,68,68,0.5))' }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'rgba(239,68,68,0.7)'; (e.currentTarget as HTMLButtonElement).style.filter = 'none' }}
                onClick={() => cancelJob(activeJobRecord.job_id)}
              >
                <Square size={17} fill="currentColor" strokeWidth={0} />
              </button>
            )}
          </div>
          {activeJobRecord.status === 'running' && (
            <div className="progress-track">
              <div
                className="progress-fill"
                style={{ width: '100%', background: activeJob?.color ?? 'var(--accent)', animation: 'progressPulse 1.5s ease-in-out infinite alternate' }}
              />
            </div>
          )}
          <LogPane
            logs={activeJobRecord.logs ?? []}
            isRunning={activeJobRecord.status === 'running' || activeJobRecord.status === 'queued'}
          />
        </div>
      )}

      {/* ── History table ── */}
      <div className="card card-sm">
        <div className="card-title" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>Job History</span>
          {jobs.length > 0 && (
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontWeight: 400 }}>
              {jobs.length} jobs — session only
            </span>
          )}
        </div>
        {jobs.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
            No jobs run in this session
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Job</th>
                <th>Status</th>
                <th>Started</th>
                <th>Duration</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map(j => (
                <HistoryRow
                  key={j.job_id}
                  job={j}
                  isActive={j.job_id === running?.id}
                  onCancel={cancelJob}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      <style>{`
        @keyframes progressPulse {
          from { opacity: 0.4; }
          to   { opacity: 1; }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
