type EntityLabel = 'PER' | 'ORG' | 'LOC' | 'MISC'

const ENTITY_LABELS: Record<EntityLabel, string> = {
  PER: 'Person',
  ORG: 'Organisation',
  LOC: 'Location',
  MISC: 'Miscellaneous',
}

interface EntityTagProps {
  label: EntityLabel
  count?: number
  size?: 'sm' | 'md'
}

export function EntityTag({ label, count, size = 'md' }: EntityTagProps) {
  const fontSize = size === 'sm' ? 9 : 10

  return (
    <span className={`badge badge-${label}`} style={{ fontSize }} title={ENTITY_LABELS[label]}>
      {count != null ? `${count} ${label}` : label}
    </span>
  )
}

interface EntityLegendProps {
  labels?: EntityLabel[]
}

export function EntityLegend({ labels = ['PER', 'ORG', 'LOC', 'MISC'] }: EntityLegendProps) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 10,
        flexWrap: 'wrap',
        padding: '8px 14px',
        borderBottom: '1px solid var(--border)',
      }}
      role="list"
      aria-label="Entity type legend"
    >
      {labels.map(k => (
        <div key={k} role="listitem" style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: `var(--ner-${k.toLowerCase()})`,
              display: 'inline-block',
            }}
          />
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            {ENTITY_LABELS[k]}
          </span>
        </div>
      ))}
    </div>
  )
}
