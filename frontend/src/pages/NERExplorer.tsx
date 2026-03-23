import { useState } from 'react'
import { useQuery } from '../hooks/useQuery'
import { api, NEREntity } from '../api/client'
import { Search, ChevronRight, Tag } from 'lucide-react'

const ENTITY_COLORS: Record<string, string> = {
  PER: 'var(--ner-per)', ORG: 'var(--ner-org)', LOC: 'var(--ner-loc)', MISC: 'var(--ner-misc)',
}

const ENTITY_LABELS: Record<string, string> = {
  PER: 'Person', ORG: 'Organisation', LOC: 'Location', MISC: 'Miscellaneous',
}

function EntityLegend() {
  return (
    <div className="flex gap-3" style={{ flexWrap: 'wrap' }}>
      {Object.entries(ENTITY_LABELS).map(([k, v]) => (
        <div key={k} className="flex items-center gap-2">
          <span className={`badge badge-${k}`}>{k}</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{v}</span>
        </div>
      ))}
    </div>
  )
}

function renderNERText(body: string, entities: NEREntity[]): React.ReactNode[] {
  if (!entities.length) return [<span key="0">{body}</span>]

  // Sort by start offset, deduplicate overlapping spans
  const sorted = [...entities].sort((a, b) => a.start - b.start)
  const nodes: React.ReactNode[] = []
  let cursor = 0

  for (const ent of sorted) {
    if (ent.start < cursor) continue // skip overlapping
    if (ent.start > cursor) {
      nodes.push(<span key={`t${cursor}`}>{body.slice(cursor, ent.start)}</span>)
    }
    nodes.push(
      <span
        key={`e${ent.start}`}
        className={`ner-span ner-span-${ent.label}`}
        title={`${ENTITY_LABELS[ent.label] ?? ent.label}: "${ent.text}"`}
      >
        {body.slice(ent.start, ent.end)}
        <sup className={`ner-label ner-label-${ent.label}`}>{ent.label}</sup>
      </span>,
    )
    cursor = ent.end
  }
  if (cursor < body.length) {
    nodes.push(<span key={`t${cursor}`}>{body.slice(cursor)}</span>)
  }
  return nodes
}

function ArticleDetail({ url }: { url: string }) {
  const { data, loading, error } = useQuery(() => api.nerArticle(url), [url])

  if (loading) return <div className="loading"><div className="spinner" /> Loading article…</div>
  if (error)   return <div style={{ color: 'var(--error)', fontSize: 13, padding: 20 }}>Error: {error}</div>
  if (!data)   return null

  const { clean, ner } = data
  const entities = ner?.entities ?? []

  // Count by label
  const byLabel: Record<string, number> = {}
  entities.forEach(e => { byLabel[e.label] = (byLabel[e.label] ?? 0) + 1 })

  return (
    <div className="fade-up">
      <div style={{ marginBottom: 16 }}>
        <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.4rem', marginBottom: 6 }}>
          {clean.title}
        </h3>
        <div className="flex items-center gap-3" style={{ marginBottom: 10 }}>
          <span className="badge badge-info">{clean.feed}</span>
          {clean.lang && <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>lang: {clean.lang}</span>}
          {clean.pub  && <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{new Date(clean.pub).toLocaleDateString()}</span>}
        </div>
        {/* Entity distribution */}
        {ner && (
          <div className="flex items-center gap-3" style={{ flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Entities found:</span>
            {Object.entries(byLabel).map(([k, n]) => (
              <span key={k} className={`badge badge-${k}`}>{n} {k}</span>
            ))}
            {entities.length === 0 && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>None extracted</span>
            )}
          </div>
        )}
        {!ner && (
          <span className="badge badge-warn">Not yet NER-processed</span>
        )}
      </div>

      <div className="divider" />

      {/* Article body with NER highlighting */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: 8, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          Article body — entities highlighted
        </div>
        <div
          style={{
            fontSize: 14,
            lineHeight: 1.9,
            color: 'var(--text-secondary)',
            maxHeight: 360,
            overflowY: 'auto',
            padding: '16px',
            background: 'var(--bg-elevated)',
            borderRadius: 'var(--radius)',
            border: '1px solid var(--border)',
          }}
        >
          {ner ? renderNERText(ner.body, entities) : <span>{clean.body}</span>}
        </div>
      </div>

      <div className="divider" />

      {/* Preprocessed text */}
      <div>
        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: 8, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          Preprocessed text (stopwords removed + lemmatized)
        </div>
        <div
          style={{
            fontSize: 12,
            lineHeight: 1.7,
            color: 'var(--text-muted)',
            maxHeight: 160,
            overflowY: 'auto',
            padding: '12px 16px',
            background: 'var(--bg-base)',
            borderRadius: 'var(--radius)',
            border: '1px solid var(--border)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {clean.preprocessed_text ?? '—'}
        </div>
      </div>

      {/* Document stats */}
      {clean.doc_stats && (
        <div className="flex gap-4 mt-4">
          {[
            { k: 'chars',      v: clean.doc_stats.char_count },
            { k: 'tokens',     v: clean.doc_stats.token_count },
            { k: 'sentences',  v: clean.doc_stats.sentence_count },
            { k: 'entities',   v: entities.length },
          ].map(s => (
            <div key={s.k} style={{ textAlign: 'center' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 15, color: 'var(--accent-hi)' }}>
                {s.v.toLocaleString()}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {s.k}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function NERExplorer() {
  const [search, setSearch]       = useState('')
  const [selected, setSelected]   = useState<string | null>(null)
  const [collection, setCollection] = useState<'ner' | 'clean'>('ner')

  const { data, loading } = useQuery(
    () => api.articles({ collection, limit: 40, search: search || undefined }),
    [collection, search],
  )

  return (
    <div className="fade-up" style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 20, height: 'calc(100vh - 80px)', overflow: 'hidden' }}>
      {/* ── Article list panel ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflow: 'hidden' }}>
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h2>NER Explorer</h2>
          <p>Browse articles with entity highlighting</p>
        </div>

        {/* Controls */}
        <div className="flex gap-2">
          {(['ner', 'clean'] as const).map(c => (
            <button
              key={c}
              className={`btn ${collection === c ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: 12, padding: '5px 12px' }}
              onClick={() => setCollection(c)}
            >
              {c === 'ner' ? 'NER articles' : 'Clean articles'}
            </button>
          ))}
        </div>

        <div style={{ position: 'relative' }}>
          <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input
            style={{
              width: '100%', padding: '7px 10px 7px 30px',
              background: 'var(--bg-elevated)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius)', color: 'var(--text-primary)',
              fontFamily: 'var(--font-ui)', fontSize: 13, outline: 'none',
            }}
            placeholder="Search articles…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        {/* Legend */}
        <EntityLegend />

        {/* Article list */}
        <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 2, flex: 1 }}>
          {loading && <div className="loading"><div className="spinner" /></div>}
          {data?.items.map(a => (
            <button
              key={a.url}
              onClick={() => setSelected(a.url)}
              style={{
                background: selected === a.url ? 'var(--accent-glow)' : 'var(--bg-surface)',
                border: `1px solid ${selected === a.url ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 'var(--radius)',
                padding: '10px 12px',
                textAlign: 'left',
                cursor: 'pointer',
                transition: 'all 0.1s',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                gap: 8,
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="truncate" style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, marginBottom: 3 }}>
                  {a.title}
                </div>
                <div className="flex items-center gap-2">
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{a.feed}</span>
                  {a.entity_count !== undefined && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, color: 'var(--ner-loc)' }}>
                      <Tag size={9} />{a.entity_count}
                    </span>
                  )}
                </div>
              </div>
              <ChevronRight size={12} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
            </button>
          ))}
          {data?.items.length === 0 && !loading && (
            <div style={{ color: 'var(--text-muted)', fontSize: 13, textAlign: 'center', padding: 20 }}>
              {collection === 'ner' ? 'NER job not yet run' : 'No articles found'}
            </div>
          )}
        </div>
      </div>

      {/* ── Article detail panel ── */}
      <div style={{ overflowY: 'auto', padding: '0 4px' }}>
        {selected ? (
          <>
            <div className="page-header" style={{ marginBottom: 16 }}>
              <div className="flex justify-between items-center">
                <h2 style={{ fontSize: '1.4rem' }}>Article Detail</h2>
                <button
                  className="btn btn-ghost"
                  style={{ fontSize: 11 }}
                  onClick={() => setSelected(null)}
                >
                  Close
                </button>
              </div>
            </div>
            <ArticleDetail url={selected} />
          </>
        ) : (
          <div style={{
            height: '100%', display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 12,
            color: 'var(--text-muted)',
          }}>
            <FlaskConical size={40} opacity={0.3} />
            <p style={{ fontSize: 14 }}>Select an article to inspect entities</p>
            <p style={{ fontSize: 12 }}>
              Entity spans are highlighted directly in the article body
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function FlaskConical({ size, opacity }: { size: number; opacity: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} opacity={opacity}>
      <path d="M10 2v8L4.72 20.55A1 1 0 0 0 5.82 22h12.36a1 1 0 0 0 1.1-1.45L14 10V2" />
      <line x1="8.5" y1="2" x2="15.5" y2="2" />
      <line x1="7" y1="16" x2="17" y2="16" />
    </svg>
  )
}
