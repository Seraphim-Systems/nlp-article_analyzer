import { useState } from 'react'
import { useQuery } from '../hooks/useQuery'
import { api, NEREntity, Article } from '../api/client'
import { Search, Tag, FileText } from 'lucide-react'

const ENTITY_COLORS: Record<string, string> = {
  PER: 'var(--ner-per)', ORG: 'var(--ner-org)', LOC: 'var(--ner-loc)', MISC: 'var(--ner-misc)',
}
const ENTITY_LABELS: Record<string, string> = {
  PER: 'Person', ORG: 'Organisation', LOC: 'Location', MISC: 'Miscellaneous',
}
const NER_TYPES = ['PER', 'ORG', 'LOC', 'MISC'] as const

// ── Helpers ────────────────────────────────────────────────────────────────

function formatDate(pub?: string) {
  if (!pub) return null
  try {
    return new Date(pub).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch {
    return null
  }
}

// ── NER text renderer ──────────────────────────────────────────────────────

function renderNERText(body: string, entities: NEREntity[]): React.ReactNode[] {
  if (!entities.length) return [<span key="0">{body}</span>]
  const sorted = [...entities].sort((a, b) => a.start - b.start)
  const nodes: React.ReactNode[] = []
  let cursor = 0
  for (const ent of sorted) {
    if (ent.start < cursor) continue
    if (ent.start > cursor) nodes.push(<span key={`t${cursor}`}>{body.slice(cursor, ent.start)}</span>)
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
  if (cursor < body.length) nodes.push(<span key={`t${cursor}`}>{body.slice(cursor)}</span>)
  return nodes
}

// ── ArticleListItem ────────────────────────────────────────────────────────

function ArticleListItem({
  article,
  selected,
  onClick,
}: {
  article: Article
  selected: boolean
  onClick: () => void
}) {
  const date = formatDate(article.pub)
  const entityCount = article.entity_count ?? 0

  return (
    <button
      onClick={onClick}
      style={{
        width: '100%',
        background: selected ? 'rgba(59,130,246,0.07)' : 'transparent',
        border: 'none',
        borderLeft: `3px solid ${selected ? 'var(--accent)' : 'transparent'}`,
        borderBottom: '1px solid var(--border)',
        padding: '10px 14px 10px 11px',
        textAlign: 'left',
        cursor: 'pointer',
        transition: 'background 0.12s, border-color 0.12s',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}
      onMouseEnter={e => {
        if (!selected) (e.currentTarget as HTMLElement).style.background = 'var(--bg-hover)'
      }}
      onMouseLeave={e => {
        if (!selected) (e.currentTarget as HTMLElement).style.background = 'transparent'
      }}
    >
      {/* Title */}
      <span style={{
        fontSize: 12.5,
        fontWeight: 500,
        color: selected ? 'var(--text-primary)' : 'var(--text-secondary)',
        lineHeight: 1.4,
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        overflow: 'hidden',
        transition: 'color 0.12s',
      }}>
        {article.title}
      </span>

      {/* Meta row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{
          fontSize: 10,
          fontFamily: 'var(--font-mono)',
          color: 'var(--accent-hi)',
          background: 'var(--accent-glow)',
          border: '1px solid rgba(59,130,246,0.2)',
          borderRadius: 3,
          padding: '0px 5px',
          letterSpacing: '0.04em',
          flexShrink: 0,
        }}>
          {article.feed}
        </span>
        {date && (
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            {date}
          </span>
        )}
        {article.lang && article.lang !== 'en' && (
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginLeft: 'auto' }}>
            {article.lang}
          </span>
        )}
      </div>

      {/* Entity signature */}
      {entityCount > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 1 }}>
          <Tag size={9} color="var(--text-muted)" style={{ flexShrink: 0 }} />
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            {entityCount} {entityCount === 1 ? 'entity' : 'entities'}
          </span>
          {/* Pip row: one dot per entity, capped at 20, colored by cycling through types */}
          <div style={{ display: 'flex', gap: 2, marginLeft: 2, flexWrap: 'wrap' }}>
            {Array.from({ length: Math.min(entityCount, 20) }).map((_, i) => (
              <span
                key={i}
                style={{
                  width: 5, height: 5, borderRadius: '50%',
                  background: ENTITY_COLORS[NER_TYPES[i % 4]],
                  opacity: 0.7,
                  flexShrink: 0,
                }}
              />
            ))}
            {entityCount > 20 && (
              <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                +{entityCount - 20}
              </span>
            )}
          </div>
        </div>
      )}
    </button>
  )
}

// ── EntityLegend ───────────────────────────────────────────────────────────

function EntityLegend() {
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', padding: '8px 14px', borderBottom: '1px solid var(--border)' }}>
      {NER_TYPES.map(k => (
        <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: ENTITY_COLORS[k], display: 'inline-block' }} />
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{ENTITY_LABELS[k]}</span>
        </div>
      ))}
    </div>
  )
}

// ── ArticleDetail ──────────────────────────────────────────────────────────

function ArticleDetail({ url, showNER }: { url: string; showNER: boolean }) {
  const { data, loading, error } = useQuery(() => api.nerArticle(url), [url])

  if (loading) return <div className="loading"><div className="spinner" /> Loading article…</div>
  if (error)   return <div style={{ color: 'var(--error)', fontSize: 13, padding: 20 }}>Error: {error}</div>
  if (!data)   return null

  const { clean, ner } = data
  const entities = (showNER && ner?.entities) ? ner.entities : []
  const byLabel: Record<string, number> = {}
  entities.forEach(e => { byLabel[e.label] = (byLabel[e.label] ?? 0) + 1 })

  return (
    <div className="fade-up">
      {/* Header */}
      <div style={{ marginBottom: 16 }}>
        <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.4rem', marginBottom: 6, lineHeight: 1.3 }}>
          {clean.title}
        </h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span className="badge badge-info">{clean.feed}</span>
          {clean.lang && (
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              {clean.lang}
            </span>
          )}
          {clean.pub && (
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              {formatDate(clean.pub)}
            </span>
          )}
        </div>
      </div>

      {/* Entity summary */}
      {showNER && (
        <div style={{ marginBottom: 14 }}>
          {ner ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              {Object.entries(byLabel).length > 0
                ? Object.entries(byLabel).map(([k, n]) => (
                    <span key={k} className={`badge badge-${k}`}>{n} {k}</span>
                  ))
                : <span style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>No entities extracted</span>
              }
            </div>
          ) : (
            <span className="badge badge-warn">Not yet NER-processed</span>
          )}
        </div>
      )}

      <div className="divider" />

      {/* Body */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: 8, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          {showNER && ner ? 'Article body with entity highlights' : 'Article body'}
        </div>
        <div style={{
          fontSize: 13.5,
          lineHeight: 1.85,
          color: 'var(--text-secondary)',
          maxHeight: 360,
          overflowY: 'auto',
          padding: 16,
          background: 'var(--bg-elevated)',
          borderRadius: 'var(--radius)',
          border: '1px solid var(--border)',
        }}>
          {showNER && ner
            ? renderNERText(ner.body, entities)
            : <span>{clean.body}</span>
          }
        </div>
      </div>

      <div className="divider" />

      {/* Preprocessed text */}
      <div>
        <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: 8, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          Preprocessed text (stopwords removed, lemmatized)
        </div>
        <div style={{
          fontSize: 12,
          lineHeight: 1.7,
          color: 'var(--text-muted)',
          maxHeight: 140,
          overflowY: 'auto',
          padding: '10px 14px',
          background: 'var(--bg-base)',
          borderRadius: 'var(--radius)',
          border: '1px solid var(--border)',
          fontFamily: 'var(--font-mono)',
        }}>
          {clean.preprocessed_text ?? 'Not available'}
        </div>
      </div>

      {/* Document stats */}
      {clean.doc_stats && (
        <div style={{ display: 'flex', gap: 20, marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
          {[
            { k: 'chars',     v: clean.doc_stats.char_count },
            { k: 'tokens',    v: clean.doc_stats.token_count },
            { k: 'sentences', v: clean.doc_stats.sentence_count },
            { k: 'entities',  v: entities.length },
          ].map(s => (
            <div key={s.k} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 16, color: 'var(--accent-hi)', lineHeight: 1 }}>
                {s.v.toLocaleString()}
              </span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {s.k}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── NERExplorer ────────────────────────────────────────────────────────────

export default function NERExplorer() {
  const [search, setSearch]         = useState('')
  const [selected, setSelected]     = useState<string | null>(null)
  const [collection, setCollection] = useState<'ner' | 'clean'>('ner')
  const [limit, setLimit]           = useState(10)

  const { data, loading } = useQuery(
    () => api.articles({ collection, limit, search: search || undefined }),
    [collection, search, limit],
  )

  const showNER = collection === 'ner'

  return (
    <div
      className="fade-up"
      style={{ display: 'grid', gridTemplateColumns: '320px 1fr', height: 'calc(100vh - 80px)', overflow: 'hidden' }}
    >
      {/* Left panel */}
      <div style={{
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        borderRight: '1px solid var(--border)', background: 'var(--bg-surface)', borderRadius: 'var(--radius-lg)',
      }}>
        {/* Panel header */}
        <div style={{ padding: '16px 14px 12px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.5rem', marginBottom: 2 }}>NER Explorer</h2>
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Browse articles with entity highlighting</p>
        </div>

        {/* Collection toggle */}
        <div style={{ display: 'flex', padding: '10px 14px', gap: 8, borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          {(['ner', 'clean'] as const).map(c => (
            <button
              key={c}
              className={`btn ${collection === c ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: 11, padding: '4px 12px', flex: 1 }}
              onClick={() => { setCollection(c); setSelected(null); setLimit(10) }}
            >
              {c === 'ner' ? 'NER' : 'Clean'}
            </button>
          ))}
        </div>

        {/* Search */}
        <div style={{ padding: '8px 14px', borderBottom: '1px solid var(--border)', flexShrink: 0, position: 'relative' }}>
          <Search size={12} style={{ position: 'absolute', left: 24, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
          <input
            style={{
              width: '100%', padding: '6px 10px 6px 28px',
              background: 'var(--bg-elevated)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)',
              fontFamily: 'var(--font-ui)', fontSize: 12, outline: 'none',
            }}
            placeholder="Search articles…"
            value={search}
            onChange={e => { setSearch(e.target.value); setLimit(10) }}
          />
        </div>

        {/* Legend */}
        {showNER && <EntityLegend />}

        {/* Article list */}
        <div style={{ overflowY: 'auto', flex: 1 }}>
          {loading && !data && (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}>
              <div className="spinner" />
            </div>
          )}
          {data?.items.map(a => (
            <ArticleListItem
              key={a.url}
              article={a}
              selected={selected === a.url}
              onClick={() => setSelected(a.url)}
            />
          ))}
          {data && data.items.length < data.total && (
            <div style={{ padding: '12px 14px', textAlign: 'center' }}>
              <button
                className="btn btn-ghost"
                style={{ fontSize: 11, width: '100%' }}
                onClick={() => setLimit(prev => prev + 10)}
                disabled={loading}
              >
                {loading ? 'Loading…' : 'Load More'}
              </button>
            </div>
          )}
          {data?.items.length === 0 && !loading && (
            <div style={{ color: 'var(--text-muted)', fontSize: 12, textAlign: 'center', padding: '32px 16px' }}>
              {collection === 'ner' ? 'NER job not yet run' : 'No articles found'}
            </div>
          )}
        </div>

        {/* Footer count */}
        {data && (
          <div style={{ padding: '8px 14px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              {data.total.toLocaleString()} articles
              {data.items.length < data.total && ` (showing ${data.items.length})`}
            </span>
          </div>
        )}
      </div>

      {/* Right panel */}
      <div style={{ overflowY: 'auto', padding: '24px 28px' }}>
        {selected ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                Article detail
              </div>
              <button
                className="btn btn-ghost"
                style={{ fontSize: 11, padding: '3px 10px' }}
                onClick={() => setSelected(null)}
              >
                Close
              </button>
            </div>
            <ArticleDetail url={selected} showNER={showNER} />
          </>
        ) : (
          <div style={{
            height: '100%', display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 10,
            color: 'var(--text-muted)',
          }}>
            <FileText size={36} strokeWidth={1} opacity={0.25} />
            <p style={{ fontSize: 13 }}>Select an article to inspect</p>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', opacity: 0.6 }}>
              {showNER ? 'Entity spans highlighted in article body' : 'Clean article text view'}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
