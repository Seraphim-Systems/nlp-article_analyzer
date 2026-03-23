import { useState } from 'react'
import { useQuery } from '../hooks/useQuery'
import { api, TFIDFTerm } from '../api/client'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, Legend,
} from 'recharts'
import { Info } from 'lucide-react'

const NER_LABEL_COLOR: Record<string, string> = {
  PER: 'var(--ner-per)', ORG: 'var(--ner-org)', LOC: 'var(--ner-loc)', MISC: 'var(--ner-misc)',
}

function TermBar({ term, score, maxScore, isNer }: { term: string; score: number; maxScore: number; isNer: boolean }) {
  const pct     = (score / maxScore) * 100
  const prefix  = term.match(/^(PER|ORG|LOC|MISC)_/)
  const label   = prefix ? prefix[1] : null
  const cleaned = prefix ? term.slice(prefix[0].length).replace(/_/g, ' ') : term
  const color   = label ? NER_LABEL_COLOR[label] : 'var(--accent)'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 0' }}>
      <div style={{ width: 130, flexShrink: 0 }}>
        {label && <span className={`badge badge-${label}`} style={{ marginRight: 5, fontSize: 9 }}>{label}</span>}
        <span style={{ fontSize: 12, color: isNer ? 'var(--text-primary)' : 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
          {cleaned}
        </span>
      </div>
      <div style={{ flex: 1, height: 6, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.6s ease' }} />
      </div>
      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', minWidth: 50, textAlign: 'right' }}>
        {score.toFixed(4)}
      </span>
    </div>
  )
}

function EntityPie({ dist }: { dist: Record<string, number> }) {
  const total = Object.values(dist).reduce((a, b) => a + b, 0) || 1
  const data  = Object.entries(dist).map(([label, count]) => ({
    label,
    value: count,
    pct:   Math.round((count / total) * 100),
    fill:  NER_LABEL_COLOR[label] ?? 'var(--text-muted)',
  }))

  return (
    <div>
      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>
        Entity distribution in sample
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {data.map(d => (
          <div key={d.label}>
            <div className="flex justify-between" style={{ marginBottom: 3 }}>
              <span className={`badge badge-${d.label}`}>{d.label} — {ENTITY_FULL[d.label]}</span>
              <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: d.fill }}>
                {d.value.toLocaleString()} <span style={{ color: 'var(--text-muted)' }}>({d.pct}%)</span>
              </span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${d.pct}%`, background: d.fill }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

const ENTITY_FULL: Record<string, string> = {
  PER: 'Person', ORG: 'Organisation', LOC: 'Location', MISC: 'Miscellaneous',
}

export default function Comparison() {
  const [sampleSize, setSampleSize] = useState(200)
  const { data, loading, error, reload } = useQuery(
    () => api.tfidf(sampleSize),
    [sampleSize],
  )

  const cleanMax = data?.clean_top_terms[0]?.score ?? 1
  const nerMax   = data?.ner_top_terms[0]?.score   ?? 1

  const nerOnlyCount = data?.ner_top_terms.filter(t => t.is_ner).length ?? 0

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
          Standard TF-IDF on preprocessed text treats multi-word entity mentions (e.g.{' '}
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
              { label: 'Sample articles',  value: data.sample_size, cls: '' },
              { label: 'Clean vocab',      value: data.clean_vocab_size, cls: 'accent' },
              { label: 'NER vocab',        value: data.ner_vocab_size,   cls: 'green' },
              { label: 'NER tokens in top-25', value: nerOnlyCount, cls: 'gold' },
            ].map(s => (
              <div className="stat-card" key={s.label}>
                <div className="stat-label">{s.label}</div>
                <div className={`stat-value ${s.cls}`} style={{ fontSize: '1.4rem' }}>
                  {s.value.toLocaleString()}
                </div>
              </div>
            ))}
          </div>

          {/* ── Term comparison ── */}
          <div className="compare-split" style={{ marginBottom: 20 }}>
            <div className="compare-pane">
              <div className="compare-pane-title">
                <span style={{ color: 'var(--text-muted)' }}>A —</span>
                <span style={{ color: 'var(--text-primary)' }}>Clean TF-IDF</span>
                <span className="badge badge-info" style={{ marginLeft: 'auto', fontSize: 10 }}>Baseline</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {data.clean_top_terms.map(t => (
                  <TermBar key={t.term} term={t.term} score={t.score} maxScore={cleanMax} isNer={false} />
                ))}
              </div>
            </div>
            <div className="compare-pane">
              <div className="compare-pane-title">
                <span style={{ color: 'var(--text-muted)' }}>B —</span>
                <span style={{ color: 'var(--accent-hi)' }}>NER-Enhanced TF-IDF</span>
                <span className="badge badge-success" style={{ marginLeft: 'auto', fontSize: 10 }}>
                  {Math.round(data.ner_token_ratio * 100)}% NER tokens
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {data.ner_top_terms.map(t => (
                  <TermBar key={t.term} term={t.term} score={t.score} maxScore={nerMax} isNer={t.is_ner} />
                ))}
              </div>
            </div>
          </div>

          {/* ── Entity distribution ── */}
          <div className="grid-2" style={{ gap: 16 }}>
            <div className="card">
              <div className="card-title">Entity Distribution in Sample</div>
              <EntityPie dist={data.entity_distribution} />
            </div>

            <div className="card">
              <div className="card-title">Vocab Size: Clean vs NER-Enhanced</div>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart
                  data={[
                    { name: 'Clean', value: data.clean_vocab_size, fill: 'var(--accent)' },
                    { name: 'NER-Enhanced', value: data.ner_vocab_size, fill: 'var(--ner-loc)' },
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
                    {[0, 1].map(i => (
                      <Cell key={i} fill={i === 0 ? 'var(--accent)' : 'var(--ner-loc)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.7, marginTop: 8 }}>
                NER-enhanced text produces a larger vocabulary with entity-typed features,
                reducing ambiguity for downstream classifiers.
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
