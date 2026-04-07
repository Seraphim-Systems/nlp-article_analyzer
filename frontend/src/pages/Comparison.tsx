import { useState, useMemo } from 'react'
import { useQuery } from '../hooks/useQuery'
import { api, TFIDFTerm } from '../api/client'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Legend,
} from 'recharts'
import { Info, TrendingUp, TrendingDown, Minus } from 'lucide-react'

const NER_LABEL_COLOR: Record<string, string> = {
  PER: 'var(--ner-per)', ORG: 'var(--ner-org)', LOC: 'var(--ner-loc)', MISC: 'var(--ner-misc)',
}
const ENTITY_FULL: Record<string, string> = {
  PER: 'Person', ORG: 'Organisation', LOC: 'Location', MISC: 'Miscellaneous',
}

// ── Helpers ────────────────────────────────────────────────────────────────

function getEntityLabel(term: string): string | null {
  return term.match(/^(PER|ORG|LOC|MISC)_/)?.[1] ?? null
}

function cleanTerm(term: string): string {
  const label = getEntityLabel(term)
  return label ? term.slice(label.length + 1).replace(/_/g, ' ') : term
}

// ── TermBar ────────────────────────────────────────────────────────────────

function TermBar({
  term, score, maxScore, rank,
  delta, isNew, isDropped,
}: {
  term: string; score: number; maxScore: number; rank: number
  delta?: number; isNew?: boolean; isDropped?: boolean
}) {
  const pct    = (score / maxScore) * 100
  const label  = getEntityLabel(term)
  const text   = cleanTerm(term)
  const color  = label ? NER_LABEL_COLOR[label] : 'var(--accent)'
  const dimmed = isDropped

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '20px 130px 1fr 52px 56px',
      alignItems: 'center',
      gap: 8,
      padding: '3px 0',
      opacity: dimmed ? 0.45 : 1,
      transition: 'opacity 0.2s',
    }}>
      {/* rank */}
      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textAlign: 'right' }}>
        {rank}
      </span>

      {/* term label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, overflow: 'hidden' }}>
        {label && (
          <span className={`badge badge-${label}`} style={{ fontSize: 9, flexShrink: 0 }}>{label}</span>
        )}
        <span style={{
          fontSize: 12,
          fontFamily: 'var(--font-mono)',
          color: label ? 'var(--text-primary)' : 'var(--text-secondary)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {text}
        </span>
      </div>

      {/* bar */}
      <div style={{ height: 5, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`, height: '100%', background: color, borderRadius: 3,
          transition: 'width 0.7s ease',
          boxShadow: label ? `0 0 6px ${color}55` : undefined,
        }} />
      </div>

      {/* score */}
      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textAlign: 'right' }}>
        {score.toFixed(4)}
      </span>

      {/* delta / status indicator */}
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        {isNew && (
          <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--success)', background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 4, padding: '1px 5px', letterSpacing: '0.04em' }}>
            NEW
          </span>
        )}
        {isDropped && (
          <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--error)', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 4, padding: '1px 5px' }}>
            OUT
          </span>
        )}
        {!isNew && !isDropped && delta != null && Math.abs(delta) > 0.0001 && (
          <span style={{
            fontSize: 10, fontFamily: 'var(--font-mono)',
            color: delta > 0 ? 'var(--success)' : 'var(--error)',
            display: 'flex', alignItems: 'center', gap: 2,
          }}>
            {delta > 0
              ? <TrendingUp size={10} />
              : <TrendingDown size={10} />}
            {Math.abs(delta * 100).toFixed(2)}
          </span>
        )}
        {!isNew && !isDropped && (delta == null || Math.abs(delta) <= 0.0001) && (
          <Minus size={10} color="var(--text-muted)" />
        )}
      </div>
    </div>
  )
}

// ── EntityPie ──────────────────────────────────────────────────────────────

function EntityPie({ dist }: { dist: Record<string, number> }) {
  const total = Object.values(dist).reduce((a, b) => a + b, 0) || 1
  const data  = Object.entries(dist).map(([label, count]) => ({
    label,
    value: count,
    pct:   Math.round((count / total) * 100),
    fill:  NER_LABEL_COLOR[label] ?? 'var(--text-muted)',
  }))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {data.map(d => (
        <div key={d.label}>
          <div className="flex justify-between" style={{ marginBottom: 3 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className={`badge badge-${d.label}`} style={{ fontSize: 9 }}>{d.label}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{ENTITY_FULL[d.label]}</span>
            </span>
            <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: d.fill }}>
              {d.value.toLocaleString()} <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>({d.pct}%)</span>
            </span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${d.pct}%`, background: d.fill }} />
          </div>
        </div>
      ))}
    </div>
  )
}

// ── NerTypeBreakdown ───────────────────────────────────────────────────────

function NerTypeBreakdown({ terms }: { terms: TFIDFTerm[] }) {
  const nerTerms = terms.filter(t => t.is_ner)
  const counts: Record<string, number> = {}
  for (const t of nerTerms) {
    const lbl = getEntityLabel(t.term)
    if (lbl) counts[lbl] = (counts[lbl] ?? 0) + 1
  }
  if (nerTerms.length === 0) return <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</span>
  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {(['PER', 'ORG', 'LOC', 'MISC'] as const).filter(l => counts[l]).map(l => (
        <span key={l} className={`badge badge-${l}`} style={{ fontSize: 10 }}>
          {l} ×{counts[l]}
        </span>
      ))}
    </div>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────

export default function Comparison() {
  const [sampleSize, setSampleSize] = useState(200)
  const { data, loading, error, reload } = useQuery(
    () => api.tfidf(sampleSize),
    [sampleSize],
  )

  // Compute diff sets
  const { cleanWithDiff, nerWithDiff, movedCount, newCount } = useMemo(() => {
    if (!data) return { cleanWithDiff: [], nerWithDiff: [], movedCount: 0, newCount: 0 }

    const cleanMap = new Map(data.clean_top_terms.map(t => [t.term, t.score]))
    const nerMap   = new Map(data.ner_top_terms.map(t => [t.term, t.score]))
    const cleanSet = new Set(cleanMap.keys())
    const nerSet   = new Set(nerMap.keys())

    const cleanWithDiff = data.clean_top_terms.map(t => ({
      ...t,
      isDropped: !nerSet.has(t.term),
      delta: nerMap.has(t.term) ? (nerMap.get(t.term)! - t.score) : undefined,
    }))

    const nerWithDiff = data.ner_top_terms.map(t => ({
      ...t,
      isNew:  !cleanSet.has(t.term),
      delta:  cleanMap.has(t.term) ? (t.score - cleanMap.get(t.term)!) : undefined,
    }))

    const newCount   = nerWithDiff.filter(t => t.isNew).length
    const movedCount = nerWithDiff.filter(t => !t.isNew && t.delta != null && Math.abs(t.delta) > 0.0001).length

    return { cleanWithDiff, nerWithDiff, movedCount, newCount }
  }, [data])

  const cleanMax = data?.clean_top_terms[0]?.score ?? 1
  const nerMax   = data?.ner_top_terms[0]?.score   ?? 1

  // Radar data: clean vs NER entity distribution as % of top-25
  const radarData = useMemo(() => {
    if (!data) return []
    const nerTerms = data.ner_top_terms
    const dist = data.entity_distribution
    const corpusTotal = Object.values(dist).reduce((a, b) => a + b, 0) || 1
    const nerTotal = nerTerms.length || 1
    return (['PER', 'ORG', 'LOC', 'MISC'] as const).map(label => ({
      label: ENTITY_FULL[label],
      'Corpus %': Math.round((dist[label] ?? 0) / corpusTotal * 100),
      'Top-25 %': Math.round(nerTerms.filter(t => getEntityLabel(t.term) === label).length / nerTotal * 100),
    }))
  }, [data])

  return (
    <div className="fade-up">
      <div className="page-header">
        <h2>TF-IDF Comparison</h2>
        <p>How Named Entity Recognition reshapes document term importance</p>
      </div>

      {/* ── Thesis explainer ── */}
      <div className="card" style={{ marginBottom: 20, background: 'var(--bg-elevated)', borderColor: 'var(--border-mid)' }}>
        <div className="flex items-center gap-2" style={{ marginBottom: 10, color: 'var(--accent-hi)' }}>
          <Info size={14} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            Research Hypothesis
          </span>
        </div>
        <p style={{ fontSize: 13, lineHeight: 1.8, color: 'var(--text-secondary)' }}>
          Standard TF-IDF treats multi-word entity mentions (e.g.{' '}
          <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--bg-base)', padding: '1px 5px', borderRadius: 3 }}>"new york"</code>)
          as separate low-weight tokens. NER-enhanced TF-IDF replaces spans with typed tokens
          (e.g.{' '}
          <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--ner-loc-bg)', color: 'var(--ner-loc)', padding: '1px 5px', borderRadius: 3 }}>LOC_New_York</code>){' '}
          making entity mentions <strong style={{ color: 'var(--text-primary)' }}>single discriminative features</strong>,
          improving document separability for downstream classification.
        </p>
      </div>

      {/* ── Controls ── */}
      <div className="flex items-center gap-3" style={{ marginBottom: 20 }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Sample size:</span>
        {[100, 200, 500, 1000].map(n => (
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

      {loading && <div className="loading"><div className="spinner" /> Computing TF-IDF…</div>}

      {error && (
        <div className="card" style={{ borderColor: 'var(--error)', color: 'var(--error)', fontSize: 13 }}>
          {error.includes('503') ? 'NER job not yet complete — run the NER job first.' : error}
        </div>
      )}

      {data && !loading && (
        <>
          {/* ── Summary metrics ── */}
          <div className="grid-4" style={{ marginBottom: 20 }}>
            {[
              { label: 'Sample articles',    value: data.sample_size,      cls: '',      sub: 'documents analysed' },
              { label: 'New NER terms',      value: newCount,              cls: 'green', sub: `of 25 unique to NER` },
              { label: 'Rank shifts',        value: movedCount,            cls: 'accent',sub: 'terms that moved' },
              { label: 'NER token ratio',    value: `${Math.round(data.ner_token_ratio * 100)}%`, cls: 'gold', sub: 'of top-25 are NER' },
            ].map(s => (
              <div className="stat-card" key={s.label}>
                <div className="stat-label">{s.label}</div>
                <div className={`stat-value ${s.cls}`} style={{ fontSize: '1.4rem' }}>
                  {s.value.toLocaleString()}
                </div>
                <div className="stat-sub">{s.sub}</div>
              </div>
            ))}
          </div>

          {/* ── NER type breakdown in top-25 ── */}
          <div className="card" style={{ marginBottom: 20, padding: '14px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                Entity types in NER top-25
              </span>
              <NerTypeBreakdown terms={data.ner_top_terms} />
            </div>
          </div>

          {/* ── Term comparison ── */}
          <div className="compare-split" style={{ marginBottom: 20 }}>
            <div className="compare-pane">
              <div className="compare-pane-title">
                <span style={{ color: 'var(--text-muted)' }}>A —</span>
                <span style={{ color: 'var(--text-primary)' }}>Clean TF-IDF</span>
                <span className="badge badge-info" style={{ marginLeft: 'auto', fontSize: 10 }}>Baseline</span>
              </div>
              {/* column headers */}
              <div style={{ display: 'grid', gridTemplateColumns: '20px 130px 1fr 52px 56px', gap: 8, marginBottom: 6 }}>
                {['#', 'Term', '', 'Score', 'Δ NER'].map(h => (
                  <span key={h} style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', textAlign: h === 'Score' || h === 'Δ NER' ? 'right' : undefined }}>
                    {h}
                  </span>
                ))}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {cleanWithDiff.map((t, i) => (
                  <TermBar
                    key={t.term}
                    term={t.term}
                    score={t.score}
                    maxScore={cleanMax}
                    rank={i + 1}
                    delta={t.delta}
                    isDropped={t.isDropped}
                  />
                ))}
              </div>
            </div>

            <div className="compare-pane">
              <div className="compare-pane-title">
                <span style={{ color: 'var(--text-muted)' }}>B —</span>
                <span style={{ color: 'var(--accent-hi)' }}>NER-Enhanced TF-IDF</span>
                <span className="badge badge-success" style={{ marginLeft: 'auto', fontSize: 10 }}>
                  {newCount} new terms
                </span>
              </div>
              {/* column headers */}
              <div style={{ display: 'grid', gridTemplateColumns: '20px 130px 1fr 52px 56px', gap: 8, marginBottom: 6 }}>
                {['#', 'Term', '', 'Score', 'Δ'].map(h => (
                  <span key={h} style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', textAlign: h === 'Score' || h === 'Δ' ? 'right' : undefined }}>
                    {h}
                  </span>
                ))}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {nerWithDiff.map((t, i) => (
                  <TermBar
                    key={t.term}
                    term={t.term}
                    score={t.score}
                    maxScore={nerMax}
                    rank={i + 1}
                    delta={t.delta}
                    isNew={t.isNew}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* ── Bottom analytics ── */}
          <div className="grid-2" style={{ gap: 16 }}>
            <div className="card">
              <div className="card-title">Entity Distribution in Sample</div>
              <EntityPie dist={data.entity_distribution} />
            </div>

            <div className="card">
              <div className="card-title">Entity Representation — Corpus vs Top-25</div>
              <ResponsiveContainer width="100%" height={200}>
                <RadarChart data={radarData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
                  <PolarGrid stroke="var(--border-mid)" />
                  <PolarAngleAxis dataKey="label" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                  <PolarRadiusAxis tick={{ fill: 'var(--text-muted)', fontSize: 9 }} axisLine={false} tickCount={3} />
                  <Radar name="Corpus %" dataKey="Corpus %" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.12} />
                  <Radar name="Top-25 %" dataKey="Top-25 %" stroke="var(--ner-loc)" fill="var(--ner-loc)" fillOpacity={0.18} />
                  <Legend wrapperStyle={{ fontSize: 11, color: 'var(--text-muted)' }} />
                  <Tooltip
                    contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
                    labelStyle={{ color: 'var(--text-secondary)' }}
                  />
                </RadarChart>
              </ResponsiveContainer>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.7, marginTop: 4 }}>
                Radar shows whether entity types are over- or under-represented in the top-25 NER terms relative to their corpus frequency.
              </p>
            </div>

            <div className="card" style={{ gridColumn: '1 / -1' }}>
              <div className="card-title">Vocabulary Size — Clean vs NER-Enhanced</div>
              <div style={{ display: 'flex', gap: 32, alignItems: 'center' }}>
                <ResponsiveContainer width="50%" height={160}>
                  <BarChart
                    data={[
                      { name: 'Clean', value: data.clean_vocab_size },
                      { name: 'NER-Enhanced', value: data.ner_vocab_size },
                    ]}
                    margin={{ top: 10, right: 10, bottom: 10, left: 10 }}
                  >
                    <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
                      labelStyle={{ color: 'var(--text-secondary)' }}
                      cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                    />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      <Cell fill="var(--accent)" />
                      <Cell fill="var(--ner-loc)" />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {[
                    { label: 'Clean vocab', value: data.clean_vocab_size, color: 'var(--accent)' },
                    { label: 'NER-enhanced vocab', value: data.ner_vocab_size, color: 'var(--ner-loc)' },
                  ].map(v => (
                    <div key={v.label}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{v.label}</span>
                        <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: v.color }}>{v.value.toLocaleString()}</span>
                      </div>
                      <div className="progress-track">
                        <div className="progress-fill" style={{ width: `${(v.value / Math.max(data.clean_vocab_size, data.ner_vocab_size)) * 100}%`, background: v.color }} />
                      </div>
                    </div>
                  ))}
                  {(() => {
                    const delta = ((data.ner_vocab_size - data.clean_vocab_size) / data.clean_vocab_size) * 100
                    const sign = delta >= 0 ? '+' : ''
                    const note = delta >= 0
                      ? 'entity tokens expand the vocabulary with typed features'
                      : 'entity substitution consolidates multi-word mentions into single tokens, shrinking the vocabulary'
                    return (
                      <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.7, marginTop: 4 }}>
                        NER-enhanced vocab is <span style={{ color: delta >= 0 ? 'var(--success)' : 'var(--gold)', fontFamily: 'var(--font-mono)' }}>{sign}{delta.toFixed(1)}%</span> vs clean — {note}.
                      </p>
                    )
                  })()}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
