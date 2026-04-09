import { useState } from 'react'
import { useQuery } from '../hooks/useQuery'
import { api, SeparabilityData, EvalMetrics, EntityMetrics } from '../api/client'
import { TrendingDown, TrendingUp, Minus, FlaskConical, Activity } from 'lucide-react'
import { LoadingSpinner, ErrorMessage, PageHeader } from '../components'

// ── Constants ──────────────────────────────────────────────────────────────

const VERDICT = {
  improved: {
    color: 'var(--ner-loc)',
    bg:    'rgba(52, 211, 153, 0.06)',
    word:  'Separability Improved',
    note:  'NER entity substitution produces more discriminative document vectors — lower mean pairwise similarity indicates documents are more distinct in feature space.',
  },
  inconclusive: {
    color: 'var(--gold)',
    bg:    'rgba(245, 158, 11, 0.06)',
    word:  'Result Inconclusive',
    note:  'NER substitution shows marginal effect on mean pairwise similarity. Results may vary with larger samples or across different corpora.',
  },
  degraded: {
    color: 'var(--error)',
    bg:    'rgba(239, 68, 68, 0.06)',
    word:  'Hypothesis Not Supported',
    note:  'NER substitution did not reduce mean pairwise document similarity in this sample. Entity tokens may be increasing noise rather than discriminative signal.',
  },
}

const NER_COLOR: Record<string, string> = {
  PER: 'var(--ner-per)', ORG: 'var(--ner-org)', LOC: 'var(--ner-loc)', MISC: 'var(--ner-misc)',
}
const NER_FULL: Record<string, string> = {
  PER: 'Person', ORG: 'Organisation', LOC: 'Location', MISC: 'Miscellaneous',
}

// ── Sub-components ─────────────────────────────────────────────────────────

function SimBar({
  value, std, maxVal, color, label,
}: {
  value: number; std: number; maxVal: number; color: string; label: string
}) {
  const pct = Math.min((value / maxVal) * 100, 100)
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color }}>
          {value.toFixed(4)}
          <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 4 }}>
            +/-{std.toFixed(3)}
          </span>
        </span>
      </div>
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${pct}%`, background: color, transition: 'width 0.8s ease' }}
        />
      </div>
    </div>
  )
}

function MetricRow({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 0' }}>
      <span style={{ fontSize: 12, color: 'var(--text-secondary)', minWidth: 70 }}>{label}</span>
      <div style={{ flex: 1, height: 5, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${value * 100}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.8s ease' }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color, minWidth: 36, textAlign: 'right' }}>
        {(value * 100).toFixed(1)}
      </span>
    </div>
  )
}

// ── Cards ──────────────────────────────────────────────────────────────────

function VerdictCard({ data, evalF1 }: { data: SeparabilityData; evalF1: number | null }) {
  const v = VERDICT[data.verdict]
  const ImprovIcon = data.improvement_pct > 0 ? TrendingDown : data.improvement_pct < 0 ? TrendingUp : Minus
  const improvLabel = data.improvement_pct > 0
    ? 'avg. similarity reduced'
    : data.improvement_pct < 0
    ? 'avg. similarity increased'
    : 'no change'

  return (
    <div className="card" style={{
      borderLeft: `4px solid ${v.color}`,
      background: v.bg,
      marginBottom: 20,
      display: 'grid',
      gridTemplateColumns: '1fr auto',
      gap: 32,
      alignItems: 'center',
    }}>
      <div>
        <div style={{
          fontSize: 9,
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.18em',
          textTransform: 'uppercase',
          color: 'var(--text-muted)',
          marginBottom: 10,
        }}>
          Research Verdict — {data.sample_size.toLocaleString()} documents
        </div>
        <h3 style={{
          fontFamily: 'var(--font-display)',
          fontSize: '1.9rem',
          fontStyle: 'italic',
          color: v.color,
          lineHeight: 1.15,
          marginBottom: 10,
          fontWeight: 500,
        }}>
          {v.word}
        </h3>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8, maxWidth: 560 }}>
          {v.note}
          {evalF1 != null && (
            <span style={{ color: 'var(--text-muted)' }}>
              {' '}Model classification F1: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--gold)' }}>{(evalF1 * 100).toFixed(1)}%</span>.
            </span>
          )}
        </p>
      </div>
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 4,
        padding: '8px 16px',
        borderLeft: '1px solid var(--border)',
        minWidth: 120,
      }}>
        <ImprovIcon size={20} color={v.color} />
        <div style={{
          fontSize: '2.2rem',
          fontFamily: 'var(--font-mono)',
          fontWeight: 700,
          color: v.color,
          lineHeight: 1,
          letterSpacing: '-0.03em',
        }}>
          {data.improvement_pct > 0 ? '-' : data.improvement_pct < 0 ? '+' : ''}{Math.abs(data.improvement_pct).toFixed(1)}%
        </div>
        <div style={{
          fontSize: 9,
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
          textAlign: 'center',
        }}>
          {improvLabel}
        </div>
      </div>
    </div>
  )
}

function DocumentSpreadCard({ data }: { data: SeparabilityData }) {
  const maxVal = Math.max(data.clean_avg_similarity, data.ner_avg_similarity) * 1.2 || 0.5
  const delta = data.ner_avg_similarity - data.clean_avg_similarity
  const betterLabel = data.ner_avg_similarity < data.clean_avg_similarity ? 'lower' : 'higher'
  const betterColor = data.ner_avg_similarity < data.clean_avg_similarity ? 'var(--ner-loc)' : 'var(--error)'

  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          color: 'var(--accent)',
          letterSpacing: '0.1em',
        }}>
          01
        </span>
        <span className="card-title" style={{ margin: 0 }}>Document Spread</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
        <SimBar
          label="Clean TF-IDF"
          value={data.clean_avg_similarity}
          std={data.clean_std}
          maxVal={maxVal}
          color="var(--accent)"
        />
        <SimBar
          label="NER-Enhanced"
          value={data.ner_avg_similarity}
          std={data.ner_std}
          maxVal={maxVal}
          color="var(--ner-loc)"
        />
      </div>

      <div className="divider" />

      <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.7 }}>
        Mean pairwise cosine similarity across all document pairs. NER-enhanced vectors are{' '}
        <span style={{ fontFamily: 'var(--font-mono)', color: betterColor }}>
          {betterLabel} by {Math.abs(delta).toFixed(4)}
        </span>{' '}
        — {data.ner_avg_similarity < data.clean_avg_similarity
          ? 'documents are more distinct, supporting better separability'
          : 'documents cluster more tightly, suggesting less discriminative features'}.
      </p>
    </div>
  )
}

function VocabShiftCard({ data }: { data: SeparabilityData }) {
  const overlapPct = Math.round(data.top25_jaccard * 100)
  const uniqueToNer = 25 - data.top25_overlap_count

  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--accent)', letterSpacing: '0.1em' }}>
          02
        </span>
        <span className="card-title" style={{ margin: 0 }}>Vocabulary Shift</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
        {[
          { label: 'Shared terms', value: data.top25_overlap_count, of: 25, color: 'var(--text-secondary)', sub: 'in both top-25' },
          { label: 'Unique to NER', value: uniqueToNer, of: 25, color: 'var(--ner-loc)', sub: 'new features' },
          { label: 'Entity tokens', value: data.ner_specific_terms, of: 25, color: 'var(--ner-per)', sub: 'typed entities in top-25' },
          { label: 'Jaccard overlap', value: `${overlapPct}%`, of: null, color: overlapPct < 40 ? 'var(--ner-loc)' : 'var(--text-secondary)', sub: 'top-25 similarity' },
        ].map(s => (
          <div key={s.label} style={{
            background: 'var(--bg-elevated)',
            borderRadius: 'var(--radius)',
            padding: '10px 12px',
            border: '1px solid var(--border)',
          }}>
            <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>
              {s.label}
            </div>
            <div style={{ fontSize: '1.3rem', fontFamily: 'var(--font-mono)', color: s.color, lineHeight: 1, letterSpacing: '-0.02em', marginBottom: 2 }}>
              {typeof s.value === 'number' ? s.value : s.value}
              {s.of != null && <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}> / {s.of}</span>}
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{s.sub}</div>
          </div>
        ))}
      </div>

      <div className="divider" />

      <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.7 }}>
        {uniqueToNer} of the top-25 NER terms are absent from the clean baseline, introducing{' '}
        {data.ner_specific_terms > 0
          ? `${data.ner_specific_terms} typed entity token${data.ner_specific_terms > 1 ? 's' : ''} as new discriminative features`
          : 'entity-specific feature dimensions'}.
        {' '}Low Jaccard ({overlapPct}%) confirms significant vocabulary divergence.
      </p>
    </div>
  )
}

function ClassificationCard({ evalData, loading }: { evalData: EvalMetrics | null; loading: boolean }) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--accent)', letterSpacing: '0.1em' }}>
          03
        </span>
        <span className="card-title" style={{ margin: 0 }}>
          <Activity size={13} style={{ display: 'inline', marginRight: 6 }} />
          Classification Signal
        </span>
      </div>

      {loading && <LoadingSpinner size="sm" />}

      {!loading && (!evalData?.f1) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 0' }}>
          <FlaskConical size={14} color="var(--text-muted)" />
          <p style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>
            No evaluation run yet. Trigger the <strong style={{ color: 'var(--text-secondary)' }}>evaluate</strong> job in Job Runner to add classification evidence.
          </p>
        </div>
      )}

      {!loading && evalData?.f1 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {/* Overall metrics */}
          <div>
            <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 10 }}>
              Overall Performance
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <MetricRow label="Precision" value={evalData.precision!} color="var(--accent-hi)" />
              <MetricRow label="Recall"    value={evalData.recall!}    color="var(--ner-loc)" />
              <MetricRow label="F1 Score"  value={evalData.f1!}        color="var(--gold)" />
            </div>
          </div>

          {/* Per-entity breakdown */}
          {evalData.per_entity && (
            <div>
              <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 10 }}>
                Per-entity F1
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {(['PER', 'ORG', 'LOC', 'MISC'] as const).map(label => {
                  const m: EntityMetrics | undefined = evalData.per_entity?.[label]
                  if (!m) return null
                  return (
                    <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className={`badge badge-${label}`} style={{ fontSize: 9, minWidth: 36 }}>{label}</span>
                      <div style={{ flex: 1, height: 5, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{ width: `${m.f1 * 100}%`, height: '100%', background: NER_COLOR[label], borderRadius: 3, transition: 'width 0.8s ease' }} />
                      </div>
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: NER_COLOR[label], minWidth: 32, textAlign: 'right' }}>
                        {(m.f1 * 100).toFixed(0)}
                      </span>
                      <span style={{ fontSize: 10, color: 'var(--text-muted)', minWidth: 50, textAlign: 'right' }}>
                        n={m.support}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function MethodologyNote({ sampleSize }: { sampleSize: number }) {
  return (
    <div style={{
      padding: '14px 18px',
      background: 'var(--bg-surface)',
      borderRadius: 'var(--radius)',
      border: '1px solid var(--border)',
    }}>
      <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 8 }}>
        Methodology
      </div>
      <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.8 }}>
        Both TF-IDF models use identical hyperparameters: bigrams, min_df=3, sublinear_tf=True, uncapped vocabulary.
        Clean model preprocesses via spaCy lemmatization and stopword removal.
        NER-enhanced model replaces entity spans with typed tokens (e.g. <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--ner-loc-bg)', color: 'var(--ner-loc)', padding: '1px 4px', borderRadius: 3 }}>LOC_New_York</code>) before the same preprocessing pipeline.
        Separability is measured as mean pairwise cosine similarity across all {sampleSize.toLocaleString()} document pairs — lower values indicate more distinct document representations.
        Vocabulary shift uses top-25 term Jaccard similarity. Classification evidence uses silver-label evaluation against BERT NER (dslim/bert-base-NER).
      </p>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function Findings() {
  const [sampleSize, setSampleSize] = useState(200)

  const { data, loading, error, reload } = useQuery(
    () => api.separability(sampleSize),
    [sampleSize],
  )
  const { data: evalData, loading: evalLoading } = useQuery(
    () => api.metrics(),
    [],
    { interval: 60_000 },
  )

  return (
    <div className="fade-up">
      <PageHeader title="Analysis" description="Does NER-enhanced TF-IDF improve document separability for classification?" />

      <div className="flex items-center gap-3" style={{ marginBottom: 20 }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Sample size:</span>
        {[100, 200, 500].map(n => (
          <button
            key={n}
            className={`btn ${sampleSize === n ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: 12, padding: '5px 14px' }}
            onClick={() => setSampleSize(n)}
          >
            {n}
          </button>
        ))}
        <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={reload}>
          Refresh
        </button>
      </div>

      {loading && <LoadingSpinner message="Computing pairwise similarity..." />}

      {error && <ErrorMessage message={error} onRetry={reload} />}

      {data && !loading && (
        <>
          <VerdictCard data={data} evalF1={evalData?.f1 ?? null} />

          <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
            <DocumentSpreadCard data={data} />
            <VocabShiftCard data={data} />
          </div>

          <ClassificationCard evalData={evalData ?? null} loading={evalLoading} />

          <MethodologyNote sampleSize={data.sample_size} />
        </>
      )}
    </div>
  )
}
