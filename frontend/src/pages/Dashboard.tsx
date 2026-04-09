import { useQuery } from '../hooks/useQuery'
import { api, EntityMetrics } from '../api/client'
import { Database, Layers, Cpu, AlertTriangle, CheckCircle, Clock, Activity } from 'lucide-react'
import { LoadingSpinner, ErrorMessage, MetricCard, PageHeader } from '../components'

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

const NER_LABEL_COLOR: Record<string, string> = {
  PER: 'var(--ner-per)', ORG: 'var(--ner-org)', LOC: 'var(--ner-loc)', MISC: 'var(--ner-misc)',
}
const ENTITY_FULL: Record<string, string> = {
  PER: 'Person', ORG: 'Organisation', LOC: 'Location', MISC: 'Miscellaneous',
}

function MetricBar({ value, color }: { value: number; color: string }) {
  return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 5, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${value * 100}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.8s ease' }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color, minWidth: 36, textAlign: 'right' }}>
        {(value * 100).toFixed(1)}
      </span>
    </div>
  )
}

function ModelPerformance() {
  const { data, loading, error } = useQuery(() => api.metrics(), [], { interval: 15_000 })

  const hasData = data?.f1 != null

  return (
    <div className="card" style={{ marginTop: 16, gridColumn: '1 / -1' }}>
      <div className="card-title"><Activity size={14} /> Model Performance — BERT NER</div>

      {loading && <LoadingSpinner size="sm" />}
      {error && <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Could not load metrics.</p>}

      {!loading && !hasData && (
        <p style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>
          No evaluation run yet — trigger the <strong style={{ color: 'var(--text-secondary)' }}>evaluate</strong> job in Job Runner to compute metrics.
        </p>
      )}

      {!loading && hasData && data && (
        <>
          {/* Overall P / R / F1 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
            {[
              { label: 'Precision', value: data.precision!, color: 'var(--accent-hi)' },
              { label: 'Recall',    value: data.recall!,    color: 'var(--ner-loc)' },
              { label: 'F1 Score',  value: data.f1!,        color: 'var(--gold)' },
            ].map(m => (
              <div key={m.label} style={{ background: 'var(--bg-elevated)', borderRadius: 'var(--radius)', padding: '14px 16px', border: '1px solid var(--border-mid)' }}>
                <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 8 }}>
                  {m.label}
                </div>
                <div style={{ fontSize: '1.6rem', fontFamily: 'var(--font-mono)', color: m.color, lineHeight: 1, letterSpacing: '-0.02em', marginBottom: 8 }}>
                  {(m.value * 100).toFixed(1)}<span style={{ fontSize: '0.9rem', opacity: 0.6 }}>%</span>
                </div>
                <div style={{ height: 4, background: 'var(--bg-base)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: `${m.value * 100}%`, height: '100%', background: m.color, borderRadius: 2, transition: 'width 0.8s ease' }} />
                </div>
              </div>
            ))}
          </div>

          {/* Per-entity breakdown */}
          {data.per_entity && (
            <>
              <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 10 }}>
                Per-entity breakdown
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr 1fr 1fr auto', alignItems: 'center', gap: '6px 12px' }}>
                {/* Header */}
                {['', 'Precision', 'Recall', 'F1', 'Support'].map(h => (
                  <div key={h} style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', paddingBottom: 4, borderBottom: '1px solid var(--border)' }}>
                    {h}
                  </div>
                ))}
                {/* Rows */}
                {(['PER', 'ORG', 'LOC', 'MISC'] as const).map(label => {
                  const m: EntityMetrics | undefined = data.per_entity?.[label]
                  if (!m) return null
                  const color = NER_LABEL_COLOR[label]
                  return [
                    <div key={`${label}-name`} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span className={`badge badge-${label}`} style={{ fontSize: 9 }}>{label}</span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{ENTITY_FULL[label]}</span>
                    </div>,
                    <MetricBar key={`${label}-p`} value={m.precision} color={color} />,
                    <MetricBar key={`${label}-r`} value={m.recall}    color={color} />,
                    <MetricBar key={`${label}-f`} value={m.f1}        color={color} />,
                    <span key={`${label}-s`} style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textAlign: 'right' }}>
                      {m.support}
                    </span>,
                  ]
                })}
              </div>
            </>
          )}

          <div style={{ marginTop: 14, fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', display: 'flex', gap: 20 }}>
            <span><Clock size={10} style={{ display: 'inline', marginRight: 4 }} />
              Last run: {data.last_updated ? new Date(data.last_updated).toLocaleString() : '—'}
            </span>
            {data.sample_size && <span>Sample: {data.sample_size.toLocaleString()} articles</span>}
            {data.model_version && <span>Model: {data.model_version}</span>}
          </div>
        </>
      )}
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
      <PageHeader title="Observatory" description="Live pipeline health -- collection sizes, quality distribution, and stack status" />

      {hErr && <ErrorMessage message={hErr} onRetry={() => window.location.reload()} />}

      {/* ── Top stats ── */}
      <div className="grid-4" style={{ marginBottom: 20 }}>
        {[
          { label: 'Raw Articles',     value: stats?.raw   ?? 0, cls: '',       sub: 'scraped & stored' },
          { label: 'Clean Articles',   value: stats?.clean ?? 0, cls: 'accent', sub: 'quality-verified' },
          { label: 'NER Enriched',     value: stats?.ner   ?? 0, cls: 'green',  sub: 'entities extracted' },
          { label: 'Quarantined',      value: stats?.quarantine ?? 0, cls: 'gold', sub: 'rank-2 / low quality' },
        ].map((s, i) => (
          <MetricCard
            key={s.label}
            label={s.label}
            value={loading ? '\u2014' : s.value}
            colorClass={s.cls}
            sub={s.sub}
            animationDelay={i * 60}
          />
        ))}
      </div>

      <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
        {/* ── Pipeline flow ── */}
        <div className="card">
          <div className="card-title"><Layers size={14} /> Pipeline Progress</div>
          {stats && <PipelineFlow counts={{ raw: stats.raw, clean: stats.clean, ner: stats.ner }} />}
          {loading && <LoadingSpinner size="sm" />}
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
          {loading && <LoadingSpinner size="sm" />}
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
        <div className="card" style={{ gridColumn: '2 / 3' }}>
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

      {/* ── Model performance ── */}
      <ModelPerformance />
    </div>
  )
}
