import { useState, useCallback } from 'react'
import { useQuery } from '../hooks/useQuery'
import { api, EvalMetrics, EntityMetrics, SeparabilityMetrics } from '../api/client'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  FlaskConical, Clock, Copy, Check, RefreshCw,
  TrendingDown, TrendingUp, Minus,
} from 'lucide-react'

// ── Constants ────────────────────────────────────────────────────────────────

const NER_COLOR: Record<string, string> = {
  PER: 'var(--ner-per)', ORG: 'var(--ner-org)', LOC: 'var(--ner-loc)', MISC: 'var(--ner-misc)',
}
const NER_FULL: Record<string, string> = {
  PER: 'Person', ORG: 'Organisation', LOC: 'Location', MISC: 'Miscellaneous',
}

const PCT = (value: number) => `${(value * 100).toFixed(1)}%`

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="card" style={{ padding: '16px 16px 10px 16px' }}>
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          {title}
        </div>
        {subtitle && (
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            {subtitle}
          </div>
        )}
      </div>
      {children}
    </div>
  )
}

function OverallQualityRadar({ data }: { data: EvalMetrics }) {
  const radarData = [
    { metric: 'Precision', value: data.precision ?? 0 },
    { metric: 'Recall', value: data.recall ?? 0 },
    { metric: 'F1', value: data.f1 ?? 0 },
  ]

  return (
    <ChartCard title="Quality Shape" subtitle="Balanced model quality across precision, recall and F1">
      <div style={{ width: '100%', height: 250 }}>
        <ResponsiveContainer>
          <RadarChart data={radarData} outerRadius="72%">
            <PolarGrid stroke="var(--border-mid)" />
            <PolarAngleAxis dataKey="metric" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
            <Tooltip
              formatter={(value: number) => PCT(value)}
              contentStyle={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-mid)',
                borderRadius: 8,
                color: 'var(--text-primary)',
              }}
            />
            <Radar
              dataKey="value"
              stroke="var(--accent-hi)"
              fill="var(--accent)"
              fillOpacity={0.32}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}

function PerEntityQualityBars({ perEntity }: { perEntity: Record<string, EntityMetrics> }) {
  const chartData = Object.entries(perEntity)
    .map(([label, m]) => ({
      label,
      name: NER_FULL[label] ?? label,
      precision: m.precision,
      recall: m.recall,
      f1: m.f1,
    }))
    .sort((a, b) => b.f1 - a.f1)

  return (
    <ChartCard title="Per-Entity Quality" subtitle="Precision, recall and F1 by entity type">
      <div style={{ width: '100%', height: 280 }}>
        <ResponsiveContainer>
          <BarChart data={chartData} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="label" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
            <YAxis
              domain={[0, 1]}
              tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
              tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
            />
            <Tooltip
              formatter={(value: number, name: string) => [PCT(value), name]}
              labelFormatter={(label: string) => `${label} (${NER_FULL[label] ?? label})`}
              contentStyle={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-mid)',
                borderRadius: 8,
                color: 'var(--text-primary)',
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="precision" fill="var(--accent-hi)" radius={[4, 4, 0, 0]} />
            <Bar dataKey="recall" fill="var(--ner-loc)" radius={[4, 4, 0, 0]} />
            <Bar dataKey="f1" fill="var(--gold)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}

function EntitySupportBars({ perEntity }: { perEntity: Record<string, EntityMetrics> }) {
  const chartData = Object.entries(perEntity)
    .map(([label, m]) => ({
      label,
      support: m.support,
      color: NER_COLOR[label] ?? 'var(--text-secondary)',
    }))
    .sort((a, b) => b.support - a.support)

  return (
    <ChartCard title="Entity Distribution" subtitle="How much each entity type contributes to the benchmark">
      <div style={{ width: '100%', height: 280 }}>
        <ResponsiveContainer>
          <BarChart data={chartData} layout="vertical" margin={{ top: 6, right: 12, left: 10, bottom: 6 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
            <YAxis type="category" dataKey="label" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} width={38} />
            <Tooltip
              formatter={(value: number) => [value.toLocaleString(), 'Support']}
              labelFormatter={(label: string) => `${label} (${NER_FULL[label] ?? label})`}
              contentStyle={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-mid)',
                borderRadius: 8,
                color: 'var(--text-primary)',
              }}
            />
            <Bar dataKey="support" radius={[0, 4, 4, 0]}>
              {chartData.map((entry) => (
                <Cell key={`support-${entry.label}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}

function SeparabilityBars({ data }: { data: SeparabilityMetrics }) {
  const chartData = [
    { name: 'Baseline TF-IDF', similarity: data.clean_avg_similarity, std: data.clean_std },
    { name: 'NER-Enhanced', similarity: data.ner_avg_similarity, std: data.ner_std },
  ]

  return (
    <ChartCard title="Separability Core Metric" subtitle="Lower cosine similarity indicates better document separability">
      <div style={{ width: '100%', height: 250 }}>
        <ResponsiveContainer>
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="name" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
            <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
            <Tooltip
              formatter={(value: number, key: string) => [value.toFixed(4), key === 'similarity' ? 'Mean similarity' : 'Std dev']}
              contentStyle={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-mid)',
                borderRadius: 8,
                color: 'var(--text-primary)',
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="similarity" fill="var(--accent)" radius={[4, 4, 0, 0]} />
            <Bar dataKey="std" fill="var(--text-secondary)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}

function VocabularyShiftPie({ data }: { data: SeparabilityMetrics }) {
  const overlap = Math.max(data.top25_overlap_count, 0)
  const unique = Math.max(25 - data.top25_overlap_count, 0)
  const nerSpecificInsideTop25 = Math.min(Math.max(data.ner_specific_terms, 0), 25)
  const pieData = [
    { name: 'Shared top terms', value: overlap, color: 'var(--accent-hi)' },
    { name: 'NER-unique top terms', value: unique, color: 'var(--ner-loc)' },
    { name: 'Entity terms in top-25', value: nerSpecificInsideTop25, color: 'var(--ner-per)' },
  ]

  return (
    <ChartCard title="Vocabulary Shift Mix" subtitle="How term composition changes after NER enrichment">
      <div style={{ width: '100%', height: 250 }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={pieData}
              dataKey="value"
              nameKey="name"
              innerRadius={52}
              outerRadius={82}
              paddingAngle={2}
            >
              {pieData.map((entry) => (
                <Cell key={`pie-${entry.name}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number) => [value, 'Count']}
              contentStyle={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-mid)',
                borderRadius: 8,
                color: 'var(--text-primary)',
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}

const VERDICT_STYLE = {
  improved:     { color: 'var(--ner-loc)',  bg: 'rgba(52, 211, 153, 0.06)', word: 'Separability Improved' },
  inconclusive: { color: 'var(--gold)',     bg: 'rgba(245, 158, 11, 0.06)', word: 'Result Inconclusive' },
  degraded:     { color: 'var(--error)',    bg: 'rgba(239, 68, 68, 0.06)',  word: 'Hypothesis Not Supported' },
}

// ── Shared components ────────────────────────────────────────────────────────

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

// ── Separability section ─────────────────────────────────────────────────────

function SeparabilitySection({ data }: { data: SeparabilityMetrics }) {
  const v = VERDICT_STYLE[data.verdict]
  const ImprovIcon = data.improvement_pct > 0 ? TrendingDown : data.improvement_pct < 0 ? TrendingUp : Minus
  const maxVal = Math.max(data.clean_avg_similarity, data.ner_avg_similarity) * 1.2 || 0.5

  return (
    <div>
      {/* Verdict banner */}
      <div className="card" style={{
        borderLeft: `4px solid ${v.color}`,
        background: v.bg,
        display: 'grid',
        gridTemplateColumns: '1fr auto',
        gap: 32,
        alignItems: 'center',
        marginBottom: 16,
      }}>
        <div>
          <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 8 }}>
            Research Verdict — {data.sample_size.toLocaleString()} documents
          </div>
          <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.7rem', fontStyle: 'italic', color: v.color, lineHeight: 1.15, marginBottom: 0, fontWeight: 500 }}>
            {v.word}
          </h3>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '8px 16px', borderLeft: '1px solid var(--border)', minWidth: 110 }}>
          <ImprovIcon size={18} color={v.color} />
          <div style={{ fontSize: '2rem', fontFamily: 'var(--font-mono)', fontWeight: 700, color: v.color, lineHeight: 1, letterSpacing: '-0.03em' }}>
            {data.improvement_pct > 0 ? '-' : data.improvement_pct < 0 ? '+' : ''}{Math.abs(data.improvement_pct).toFixed(1)}%
          </div>
          <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', textAlign: 'center' }}>
            avg. similarity
          </div>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid-2" style={{ marginBottom: 16 }}>
        <SeparabilityBars data={data} />
        <VocabularyShiftPie data={data} />
      </div>

      <div className="grid-2" style={{ gap: 16 }}>
        {/* Similarity bars */}
        <div className="card">
          <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 14 }}>
            Mean Pairwise Cosine Similarity
          </div>
          {[
            { label: 'Baseline TF-IDF',  value: data.clean_avg_similarity, std: data.clean_std, color: 'var(--accent)' },
            { label: 'NER-Enhanced',     value: data.ner_avg_similarity,   std: data.ner_std,   color: 'var(--ner-loc)' },
          ].map(row => (
            <div key={row.label} style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{row.label}</span>
                <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: row.color }}>
                  {row.value.toFixed(4)}
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 4 }}>±{row.std.toFixed(3)}</span>
                </span>
              </div>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${Math.min((row.value / maxVal) * 100, 100)}%`, background: row.color, transition: 'width 0.8s ease' }} />
              </div>
            </div>
          ))}
        </div>

        {/* Vocabulary shift */}
        <div className="card">
          <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 14 }}>
            Vocabulary Shift
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            {[
              { label: 'Jaccard overlap',  value: `${Math.round(data.top25_jaccard * 100)}%`,  color: 'var(--text-secondary)', sub: 'top-25 similarity' },
              { label: 'Shared terms',     value: data.top25_overlap_count,                     color: 'var(--text-secondary)', sub: `of 25` },
              { label: 'Entity tokens',    value: data.ner_specific_terms,                       color: 'var(--ner-per)',         sub: 'typed in top-25' },
              { label: 'NER-unique terms', value: 25 - data.top25_overlap_count,                color: 'var(--ner-loc)',          sub: 'new features' },
            ].map(s => (
              <div key={s.label} style={{ background: 'var(--bg-elevated)', borderRadius: 'var(--radius)', padding: '10px 12px', border: '1px solid var(--border)' }}>
                <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>{s.label}</div>
                <div style={{ fontSize: '1.2rem', fontFamily: 'var(--font-mono)', color: s.color, lineHeight: 1, marginBottom: 2 }}>{s.value}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{s.sub}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── CoNLL-2003 section ────────────────────────────────────────────────────────

function ConllSection({ data, benchmark }: { data: EvalMetrics; benchmark: string | null }) {
  return (
    <div>
      <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 14 }}>
        Benchmark: {benchmark ?? 'CoNLL-2003'} — strict entity-level matching (seqeval)
        {data.sample_size && <span style={{ marginLeft: 12 }}>n={data.sample_size.toLocaleString()} sentences</span>}
      </div>

      {/* Overall P / R / F1 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Precision', value: data.precision!, color: 'var(--accent-hi)' },
          { label: 'Recall',    value: data.recall!,    color: 'var(--ner-loc)' },
          { label: 'F1 Score',  value: data.f1!,        color: 'var(--gold)' },
        ].map(m => (
          <div key={m.label} style={{ background: 'var(--bg-elevated)', borderRadius: 'var(--radius)', padding: '16px 20px', border: '1px solid var(--border-mid)' }}>
            <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 10 }}>
              {m.label}
            </div>
            <div style={{ fontSize: '2rem', fontFamily: 'var(--font-mono)', color: m.color, lineHeight: 1, letterSpacing: '-0.02em', marginBottom: 10 }}>
              {(m.value * 100).toFixed(1)}<span style={{ fontSize: '1rem', opacity: 0.6 }}>%</span>
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
          <div className="grid-2" style={{ marginBottom: 16 }}>
            <OverallQualityRadar data={data} />
            <EntitySupportBars perEntity={data.per_entity} />
          </div>

          <PerEntityQualityBars perEntity={data.per_entity} />

          <div className="card" style={{ marginTop: 16 }}>
            <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 14 }}>
              Per-entity numeric breakdown
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr 1fr 1fr auto', alignItems: 'center', gap: '8px 14px' }}>
              {['', 'Precision', 'Recall', 'F1', 'Support'].map(h => (
                <div key={h} style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', paddingBottom: 6, borderBottom: '1px solid var(--border)' }}>
                  {h}
                </div>
              ))}
              {Object.entries(data.per_entity).map(([label, m]: [string, EntityMetrics]) => {
                const color = NER_COLOR[label] ?? 'var(--text-secondary)'
                return [
                  <div key={`${label}-name`} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className={`badge badge-${label}`} style={{ fontSize: 9 }}>{label}</span>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{NER_FULL[label] ?? label}</span>
                  </div>,
                  <MetricBar key={`${label}-p`} value={m.precision} color={color} />,
                  <MetricBar key={`${label}-r`} value={m.recall} color={color} />,
                  <MetricBar key={`${label}-f`} value={m.f1} color={color} />,
                  <span key={`${label}-s`} style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textAlign: 'right' }}>
                    {m.support}
                  </span>,
                ]
              })}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ── Evaluation tab ────────────────────────────────────────────────────────────

function EvaluationTab() {
  const { data, loading, error, reload } = useQuery(
    () => api.metrics(),
    [],
    { interval: 30_000 },
  )

  return (
    <div>
      <div className="flex items-center gap-3" style={{ marginBottom: 20 }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Auto-refreshes every 30s</span>
        <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={reload}>
          <RefreshCw size={12} style={{ display: 'inline', marginRight: 5 }} />
          Refresh
        </button>
        {data?.last_updated && (
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            <Clock size={10} style={{ display: 'inline', marginRight: 4 }} />
            {new Date(data.last_updated).toLocaleString()}
          </span>
        )}
      </div>

      {loading && <div className="loading"><div className="spinner" /></div>}
      {error && (
        <div className="card" style={{ borderColor: 'var(--error)', color: 'var(--error)', fontSize: 13 }}>
          {error}
        </div>
      )}

      {!loading && !data?.separability && !data?.f1 && (
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '20px 24px' }}>
          <FlaskConical size={18} color="var(--text-muted)" />
          <p style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>
            No evaluation run yet. Trigger the{' '}
            <strong style={{ color: 'var(--text-secondary)' }}>evaluate</strong>{' '}
            job in Job Runner to compute metrics.
          </p>
        </div>
      )}

      {!loading && data && (
        <>
          {/* Primary: separability */}
          {data.separability && (
            <section style={{ marginBottom: 32 }}>
              <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 12 }}>
                01 — Primary Evaluation: Document Separability
              </div>
              <SeparabilitySection data={data.separability} />
            </section>
          )}

          {/* Secondary: CoNLL-2003 NER quality */}
          {data.f1 != null && (
            <section>
              <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 12 }}>
                02 — Secondary: NER Model Quality ({data.model_version ?? 'BERT'})
              </div>
              <ConllSection data={data} benchmark={data.benchmark} />
            </section>
          )}
        </>
      )}
    </div>
  )
}

// ── Prometheus tab ────────────────────────────────────────────────────────────

function PrometheusTab() {
  const [copied, setCopied] = useState(false)
  const [lastFetched, setLastFetched] = useState<Date | null>(null)

  const fetchFn = useCallback(() => api.prometheusMetrics(), [])
  const { data, loading, error, reload } = useQuery(fetchFn, [], { interval: 15_000 })

  if (data && !lastFetched) setLastFetched(new Date())

  const handleCopy = () => {
    if (!data) return
    navigator.clipboard.writeText(data).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const handleRefresh = () => {
    setLastFetched(new Date())
    reload()
  }

  function colourLine(line: string, i: number) {
    if (line.startsWith('# HELP') || line.startsWith('# TYPE')) {
      return <span key={i} style={{ color: 'var(--text-muted)' }}>{line}{'\n'}</span>
    }
    if (line.trim() === '') return <span key={i}>{'\n'}</span>
    const lastSpace = line.lastIndexOf(' ')
    if (lastSpace === -1) return <span key={i} style={{ color: 'var(--text-primary)' }}>{line}{'\n'}</span>
    return (
      <span key={i}>
        <span style={{ color: 'var(--text-secondary)' }}>{line.slice(0, lastSpace)}</span>
        {' '}
        <span style={{ color: 'var(--accent-hi)', fontWeight: 600 }}>{line.slice(lastSpace + 1)}</span>
        {'\n'}
      </span>
    )
  }

  return (
    <div>
      <div className="flex items-center gap-3" style={{ marginBottom: 16 }}>
        <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          Content-Type: text/plain; version=0.0.4
        </span>
        <span style={{ color: 'var(--border-mid)' }}>·</span>
        <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          <Clock size={10} style={{ display: 'inline', marginRight: 4 }} />
          {lastFetched ? `Last fetched: ${lastFetched.toLocaleTimeString()}` : 'Auto-refreshes every 15s'}
        </span>
        <div style={{ flex: 1 }} />
        <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={handleRefresh}>
          <RefreshCw size={12} style={{ display: 'inline', marginRight: 5 }} />
          Refresh
        </button>
        <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={handleCopy} disabled={!data}>
          {copied
            ? <><Check size={12} style={{ display: 'inline', marginRight: 5 }} />Copied</>
            : <><Copy size={12} style={{ display: 'inline', marginRight: 5 }} />Copy</>}
        </button>
      </div>

      {loading && !data && <div className="loading"><div className="spinner" /></div>}
      {error && (
        <div className="card" style={{ borderColor: 'var(--error)', color: 'var(--error)', fontSize: 13 }}>
          {error}
        </div>
      )}
      {data && (
        <pre style={{
          background: 'var(--bg-base)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          padding: '16px 20px',
          overflowX: 'auto',
          overflowY: 'auto',
          maxHeight: '60vh',
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
          lineHeight: 1.7,
          margin: 0,
          whiteSpace: 'pre',
        }}>
          {data.split('\n').map((line, i) => colourLine(line, i))}
        </pre>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = 'evaluation' | 'prometheus'

export default function AdminMetrics() {
  const [tab, setTab] = useState<Tab>('evaluation')

  return (
    <div className="fade-up">
      <div className="page-header">
        <h2>Evaluation</h2>
        <p>Evaluation metrics and raw Prometheus scrape output</p>
      </div>

      <div style={{ display: 'flex', gap: 4, marginBottom: 24, borderBottom: '1px solid var(--border)' }}>
        {([
          { id: 'evaluation' as Tab, label: 'Evaluation Metrics' },
          { id: 'prometheus' as Tab, label: 'Prometheus Raw' },
        ]).map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: tab === t.id ? '2px solid var(--accent-hi)' : '2px solid transparent',
              padding: '8px 16px',
              fontSize: 13,
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
              color: tab === t.id ? 'var(--text-primary)' : 'var(--text-muted)',
              transition: 'color 0.15s, border-color 0.15s',
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'evaluation' && <EvaluationTab />}
      {tab === 'prometheus' && <PrometheusTab />}
    </div>
  )
}
