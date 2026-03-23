import { useQuery } from '../hooks/useQuery'
import { api } from '../api/client'
import { Database, Layers, Cpu, AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie,
} from 'recharts'

function AnimatedNumber({ value }: { value: number }) {
  return (
    <span className="count-up" key={value}>
      {value.toLocaleString()}
    </span>
  )
}

function PipelineFlow({ counts }: { counts: { raw: number; clean: number; ner: number } }) {
  const max = Math.max(counts.raw, 1)
  const stages = [
    { label: 'Raw', key: 'raw',   value: counts.raw,   color: 'var(--text-muted)',  fill: 'var(--border-mid)' },
    { label: 'Clean', key: 'clean', value: counts.clean, color: 'var(--accent-hi)',  fill: 'var(--accent)' },
    { label: 'NER',   key: 'ner',   value: counts.ner,   color: 'var(--ner-loc)',    fill: 'var(--ner-loc)' },
  ]
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {stages.map((s, i) => (
        <div key={s.key} className="fade-up" style={{ animationDelay: `${i * 80}ms` }}>
          <div className="flex justify-between" style={{ marginBottom: 4 }}>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
              {s.label}
            </span>
            <span style={{ fontSize: 12, color: s.color, fontFamily: 'var(--font-mono)' }}>
              {s.value.toLocaleString()}
            </span>
          </div>
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{ width: `${(s.value / max) * 100}%`, background: s.fill }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

function RankDistribution({ rankData }: { rankData: Record<string, number> }) {
  const total = Object.values(rankData).reduce((a, b) => a + b, 0) || 1
  const items = [
    { rank: 'Rank 0', key: '0', color: 'var(--success)', label: 'Promoted to clean' },
    { rank: 'Rank 1', key: '1', color: 'var(--gold)',    label: 'Partial data' },
    { rank: 'Rank 2', key: '2', color: 'var(--error)',   label: 'Quarantined' },
    { rank: 'Unranked', key: 'null', color: 'var(--text-muted)', label: 'Pending rank' },
  ]
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {items.map(item => {
        const count = rankData[item.key] ?? 0
        const pct   = Math.round((count / total) * 100)
        return (
          <div key={item.key}>
            <div className="flex justify-between" style={{ marginBottom: 3 }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{item.label}</span>
              <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: item.color }}>
                {count.toLocaleString()} <span style={{ color: 'var(--text-muted)' }}>({pct}%)</span>
              </span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${pct}%`, background: item.color }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function Dashboard() {
  const { data: health, loading: hLoad, error: hErr } = useQuery(() => api.health(), [], { interval: 15_000 })
  const { data: stats,  loading: sLoad }               = useQuery(() => api.stats(),  [], { interval: 15_000 })

  const loading = hLoad || sLoad

  const pipelineProgress = stats
    ? Math.round(((stats.ner / Math.max(stats.clean, 1)) * 100))
    : 0

  return (
    <div className="fade-up">
      <div className="page-header">
        <h2>Observatory</h2>
        <p>Live pipeline health — collection sizes, quality distribution, and stack status</p>
      </div>

      {/* ── Top stats ── */}
      <div className="grid-4" style={{ marginBottom: 20 }}>
        {[
          { label: 'Raw Articles',     value: stats?.raw   ?? 0, cls: '',       sub: 'scraped & stored' },
          { label: 'Clean Articles',   value: stats?.clean ?? 0, cls: 'accent', sub: 'quality-verified' },
          { label: 'NER Enriched',     value: stats?.ner   ?? 0, cls: 'green',  sub: 'entities extracted' },
          { label: 'Quarantined',      value: stats?.quarantine ?? 0, cls: 'gold', sub: 'rank-2 / low quality' },
        ].map((s, i) => (
          <div className="stat-card fade-up" key={s.label} style={{ animationDelay: `${i * 60}ms` }}>
            <div className="stat-label">{s.label}</div>
            <div className={`stat-value ${s.cls}`}>
              {loading ? '—' : <AnimatedNumber value={s.value} />}
            </div>
            <div className="stat-sub">{s.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
        {/* ── Pipeline flow ── */}
        <div className="card">
          <div className="card-title"><Layers size={14} /> Pipeline Progress</div>
          {stats && <PipelineFlow counts={{ raw: stats.raw, clean: stats.clean, ner: stats.ner }} />}
          {loading && <div className="loading"><div className="spinner" /></div>}
          <div className="divider" />
          <div className="flex justify-between items-center">
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>NER coverage of clean corpus</span>
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--ner-loc)', fontSize: 13 }}>
              {pipelineProgress}%
            </span>
          </div>
          <div className="progress-track" style={{ marginTop: 6 }}>
            <div className="progress-fill green" style={{ width: `${pipelineProgress}%` }} />
          </div>
        </div>

        {/* ── Rank distribution ── */}
        <div className="card">
          <div className="card-title"><Database size={14} /> Raw Article Quality</div>
          {stats && <RankDistribution rankData={stats.raw_by_rank} />}
          {loading && <div className="loading"><div className="spinner" /></div>}
        </div>
      </div>

      <div className="grid-2" style={{ gap: 16 }}>
        {/* ── Stack health ── */}
        <div className="card">
          <div className="card-title"><Cpu size={14} /> Stack Health</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              { name: 'API Service',  ok: !hErr,                        detail: 'FastAPI / uvicorn' },
              { name: 'MongoDB',      ok: health?.mongodb === 'healthy', detail: health?.mongodb ?? '—' },
              { name: 'NER Model',    ok: (stats?.ner ?? 0) > 0,        detail: 'dslim/bert-base-NER' },
              { name: 'Clean Corpus', ok: (stats?.clean ?? 0) > 0,      detail: `${(stats?.clean ?? 0).toLocaleString()} documents` },
            ].map(row => (
              <div key={row.name} className="flex justify-between items-center" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                <div className="flex items-center gap-2">
                  {row.ok
                    ? <CheckCircle size={13} color="var(--success)" />
                    : <AlertTriangle size={13} color="var(--warning)" />}
                  <span style={{ fontSize: 13 }}>{row.name}</span>
                </div>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  {row.detail}
                </span>
              </div>
            ))}
          </div>
          {health && (
            <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              <Clock size={10} style={{ display: 'inline', marginRight: 4 }} />
              Last checked: {new Date(health.timestamp).toLocaleTimeString()}
            </div>
          )}
        </div>

        {/* ── About / thesis context ── */}
        <div className="card">
          <div className="card-title" style={{ fontFamily: 'var(--font-display)', fontSize: '1.1rem', color: 'var(--text-primary)' }}>
            Research Context
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
            This pipeline investigates the effect of <strong style={{ color: 'var(--accent-hi)' }}>Named Entity Recognition</strong> on{' '}
            <strong style={{ color: 'var(--gold)' }}>TF-IDF document representation</strong> for news article classification.
          </p>
          <div className="divider" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              { step: '01', label: 'Scrape', desc: 'RSS feed collection → raw_articles' },
              { step: '02', label: 'Clean',  desc: 'Rank, recover, enrich → clean_articles' },
              { step: '03', label: 'NER',    desc: 'BERT entity extraction → ner_articles' },
              { step: '04', label: 'Compare',desc: 'TF-IDF clean vs NER-enhanced corpus' },
            ].map(s => (
              <div key={s.step} className="flex items-center gap-3" style={{ padding: '6px 0' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--accent)', minWidth: 20 }}>{s.step}</span>
                <span style={{ fontSize: 13, color: 'var(--text-primary)', minWidth: 60 }}>{s.label}</span>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{s.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
