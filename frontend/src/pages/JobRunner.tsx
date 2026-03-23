import { useState, useEffect, useRef } from 'react'
import { api, Job } from '../api/client'
import { Play, RefreshCw, Clock, CheckCircle, XCircle, Loader } from 'lucide-react'

const JOBS = [
  {
    id: 'scrape',
    label: 'Scrape',
    desc: 'Collect articles from RSS feeds → raw_articles',
    color: 'var(--gold)',
  },
  {
    id: 'clean',
    label: 'Clean',
    desc: 'Rank + enrich raw articles → clean_articles',
    color: 'var(--accent-hi)',
  },
  {
    id: 'ner',
    label: 'NER',
    desc: 'BERT entity extraction → ner_articles',
    color: 'var(--ner-loc)',
  },
  {
    id: 'evaluate',
    label: 'Evaluate',
    desc: 'Compute model performance metrics',
    color: 'var(--ner-misc)',
  },
]

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'queued':  return <Clock     size={14} className="job-queued"  />
    case 'running': return <Loader    size={14} className="job-running" style={{ animation: 'spin 0.8s linear infinite' }} />
    case 'success': return <CheckCircle size={14} className="job-success" />
    case 'failed':  return <XCircle  size={14} className="job-failed"  />
    default:        return null
  }
}

function JobCard({
  job,
  onTrigger,
  activeId,
}: {
  job: (typeof JOBS)[number]
  onTrigger: (id: string) => void
  activeId: string | null
}) {
  const isActive = activeId === job.id

  return (
    <div
      className="card"
      style={{
        borderColor: isActive ? job.color : 'var(--border)',
        background: isActive ? `rgba(${hexToRgb(job.color)}, 0.05)` : 'var(--bg-surface)',
        transition: 'all 0.2s ease',
      }}
    >
      <div className="flex justify-between items-center" style={{ marginBottom: 10 }}>
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: '1.2rem', color: 'var(--text-primary)' }}>
            {job.label}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{job.desc}</div>
        </div>
        <button
          className="btn btn-primary"
          style={{ background: isActive ? 'var(--text-muted)' : job.color, border: 'none', color: '#000', fontSize: 12 }}
          disabled={isActive}
          onClick={() => onTrigger(job.id)}
        >
          <Play size={12} />
          {isActive ? 'Running…' : 'Run'}
        </button>
      </div>

      {isActive && (
        <div className="progress-track">
          <div
            className="progress-fill"
            style={{
              width: '100%',
              background: job.color,
              animation: 'progressAnim 1.5s ease-in-out infinite alternate',
            }}
          />
        </div>
      )}
    </div>
  )
}

// Rough conversion for dynamic rgba — not a real hex parser, just for CSS vars
function hexToRgb(_color: string) { return '59, 130, 246' }

function JobHistoryRow({ job }: { job: Job }) {
  const elapsed = job.finished_at
    ? Math.round((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000)
    : null

  return (
    <tr>
      <td className="mono">{job.job_id}</td>
      <td className="primary">{job.job_name}</td>
      <td>
        <span className={`badge ${
          job.status === 'success' ? 'badge-success' :
          job.status === 'failed'  ? 'badge-error'   :
          job.status === 'running' ? 'badge-info'    : 'badge-warn'
        }`}>
          <StatusIcon status={job.status} />
          <span style={{ marginLeft: 4 }}>{job.status}</span>
        </span>
      </td>
      <td className="mono" style={{ fontSize: 11 }}>
        {new Date(job.started_at).toLocaleTimeString()}
      </td>
      <td className="mono" style={{ fontSize: 11 }}>
        {elapsed != null ? `${elapsed}s` : '—'}
      </td>
      <td style={{ fontSize: 11, color: 'var(--text-muted)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {job.result
          ? Object.entries(job.result)
              .filter(([k]) => !['errors', 'status'].includes(k))
              .map(([k, v]) => `${k}: ${v}`)
              .join(' | ')
          : '—'}
      </td>
    </tr>
  )
}

export default function JobRunner() {
  const [jobs, setJobs]         = useState<Job[]>([])
  const [activeJob, setActive]  = useState<string | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const pollRef                 = useRef<ReturnType<typeof setInterval>>()

  // Load history
  const loadHistory = async () => {
    try {
      const res = await api.jobs()
      setJobs(res.jobs)
    } catch { /* ignore */ }
  }

  useEffect(() => {
    loadHistory()
    const id = setInterval(loadHistory, 5000)
    return () => clearInterval(id)
  }, [])

  // Poll active job
  useEffect(() => {
    if (!activeId) return
    pollRef.current = setInterval(async () => {
      try {
        const job = await api.jobById(activeId)
        setJobs(prev => {
          const existing = prev.findIndex(j => j.job_id === activeId)
          if (existing >= 0) {
            const updated = [...prev]
            updated[existing] = job
            return updated
          }
          return [job, ...prev]
        })
        if (job.status !== 'queued' && job.status !== 'running') {
          clearInterval(pollRef.current)
          setActive(null)
          setActiveId(null)
        }
      } catch { /* ignore */ }
    }, 2000)
    return () => clearInterval(pollRef.current)
  }, [activeId])

  const trigger = async (jobName: string) => {
    setActive(jobName)
    try {
      const res = await api.triggerJob(jobName)
      setActiveId(res.job_id)
    } catch (e) {
      setActive(null)
    }
  }

  const currentJob = activeId ? jobs.find(j => j.job_id === activeId) : null

  return (
    <div className="fade-up">
      <div className="page-header flex justify-between items-center">
        <div>
          <h2>Job Runner</h2>
          <p>Trigger pipeline jobs and monitor their status</p>
        </div>
        <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={loadHistory}>
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {/* ── Job cards ── */}
      <div className="grid-2" style={{ marginBottom: 24 }}>
        {JOBS.map(job => (
          <JobCard key={job.id} job={job} onTrigger={trigger} activeId={activeJob} />
        ))}
      </div>

      {/* ── Current job status ── */}
      {currentJob && (
        <div className="card" style={{ marginBottom: 20, borderColor: 'var(--accent)', background: 'var(--accent-glow)' }}>
          <div className="flex items-center gap-3">
            <StatusIcon status={currentJob.status} />
            <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>
              <strong>{currentJob.job_name}</strong> — {currentJob.status}
            </span>
            <span style={{ marginLeft: 'auto', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              id: {currentJob.job_id}
            </span>
          </div>
          {currentJob.status === 'running' && (
            <div className="progress-track" style={{ marginTop: 10 }}>
              <div className="progress-fill" style={{ width: '100%', animation: 'progressAnim 1.5s ease-in-out infinite alternate' }} />
            </div>
          )}
          {currentJob.result && (
            <div style={{ marginTop: 10, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)', padding: '8px 12px', background: 'var(--bg-base)', borderRadius: 'var(--radius)' }}>
              {JSON.stringify(currentJob.result, null, 2).slice(0, 400)}
            </div>
          )}
        </div>
      )}

      {/* ── History table ── */}
      <div className="card card-sm">
        <div className="card-title">Job History</div>
        {jobs.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
            No jobs run yet in this session
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
              {jobs.map(j => <JobHistoryRow key={j.job_id} job={j} />)}
            </tbody>
          </table>
        )}
      </div>

      <style>{`
        @keyframes progressAnim {
          from { opacity: 0.5; }
          to   { opacity: 1; }
        }
      `}</style>
    </div>
  )
}
