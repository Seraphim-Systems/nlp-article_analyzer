import { useState, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { LayoutDashboard, FlaskConical, BarChart3, Play, Menu, Microscope } from 'lucide-react'
import { useQuery } from './hooks/useQuery'
import { api } from './api/client'
import { ErrorBoundary, LoadingSpinner } from './components'

const Dashboard   = lazy(() => import('./pages/Dashboard'))
const NERExplorer = lazy(() => import('./pages/NERExplorer'))
const Comparison  = lazy(() => import('./pages/Comparison'))
const JobRunner   = lazy(() => import('./pages/JobRunner'))
const Findings    = lazy(() => import('./pages/Findings'))

// ── Logo ───────────────────────────────────────────────────────────────────

function RadarLogo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="14" cy="14" r="10" stroke="var(--accent)" strokeWidth="1" opacity="0.25" />
      <circle cx="14" cy="14" r="6.5" stroke="var(--accent)" strokeWidth="1" opacity="0.45" />
      <circle cx="14" cy="14" r="3" stroke="var(--accent-hi)" strokeWidth="1" opacity="0.75" />
      <circle cx="14" cy="14" r="1.5" fill="var(--accent-hi)" />
      <line
        x1="14" y1="14" x2="14" y2="4"
        stroke="var(--accent-hi)"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.6"
        style={{ transformOrigin: '14px 14px', animation: 'radarSweep 4s linear infinite' }}
      />
    </svg>
  )
}

// ── Header ─────────────────────────────────────────────────────────────────

function Header({ collapsed }: { collapsed: boolean }) {
  const { data, error } = useQuery(() => api.health(), [], { interval: 30_000 })

  const mongo = !error && data?.mongodb === 'healthy'
  const ner   = (data?.collections.ner ?? 0) > 0

  return (
    <header className="header" style={{ gridColumn: '1 / -1' }}>
      <div className="header-brand" style={{ gap: collapsed ? 0 : 10, overflow: 'hidden', transition: 'gap 0.2s' }}>
        <RadarLogo size={26} />
        <span style={{
          fontFamily: 'var(--font-display)',
          fontSize: '1.25rem',
          fontStyle: 'italic',
          color: 'var(--text-primary)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          maxWidth: collapsed ? 0 : 200,
          opacity: collapsed ? 0 : 1,
          transition: 'max-width 0.25s ease, opacity 0.15s ease',
        }}>
          NLP Research Station
        </span>
        <span className="tag" style={{
          opacity: collapsed ? 0 : 1,
          maxWidth: collapsed ? 0 : 40,
          overflow: 'hidden',
          transition: 'max-width 0.25s ease, opacity 0.15s ease',
        }}>
          v1.0
        </span>
      </div>
      <div className="header-status">
        <div className="flex items-center gap-2">
          <span className={`status-dot${error ? ' error' : ''}`} />
          <span>{error ? 'API offline' : 'API connected'}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`status-dot${!mongo ? ' warn' : ''}`} />
          <span>MongoDB</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`status-dot${!ner ? ' idle' : ''}`} />
          <span>NER {ner ? `${(data?.collections.ner ?? 0).toLocaleString()} docs` : 'pending'}</span>
        </div>
      </div>
    </header>
  )
}

// ── Sidebar ────────────────────────────────────────────────────────────────

const NAV = [
  { to: '/',         icon: <LayoutDashboard size={16} />, label: 'Observatory' },
  { to: '/ner',      icon: <FlaskConical size={16} />,    label: 'NER Explorer' },
  { to: '/compare',  icon: <BarChart3 size={16} />,       label: 'TF-IDF Compare' },
  { to: '/analysis', icon: <Microscope size={16} />,      label: 'Analysis' },
  { to: '/jobs',     icon: <Play size={16} />,            label: 'Job Runner' },
]

function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  return (
    <nav
      className="sidebar"
      style={{
        width: collapsed ? 52 : 220,
        minWidth: collapsed ? 52 : 220,
        transition: 'width 0.22s ease, min-width 0.22s ease',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Hamburger toggle */}
      <div style={{
        padding: '8px',
        display: 'flex',
        justifyContent: collapsed ? 'center' : 'space-between',
        alignItems: 'center',
        borderBottom: '1px solid var(--border)',
        marginBottom: 4,
      }}>
        {!collapsed && (
          <span style={{
            fontSize: 9,
            fontFamily: 'var(--font-mono)',
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            color: 'var(--text-muted)',
            paddingLeft: 6,
          }}>
            Navigation
          </span>
        )}
        <button
          onClick={onToggle}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 30,
            height: 30,
            padding: 0,
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-mid)',
            borderRadius: 'var(--radius)',
            cursor: 'pointer',
            color: 'var(--text-muted)',
            flexShrink: 0,
            transition: 'color 0.15s, background 0.15s, border-color 0.15s',
          }}
          onMouseEnter={e => {
            const el = e.currentTarget as HTMLElement
            el.style.color = 'var(--text-primary)'
            el.style.background = 'var(--bg-hover)'
            el.style.borderColor = 'var(--border-hi)'
          }}
          onMouseLeave={e => {
            const el = e.currentTarget as HTMLElement
            el.style.color = 'var(--text-muted)'
            el.style.background = 'var(--bg-elevated)'
            el.style.borderColor = 'var(--border-mid)'
          }}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <Menu size={14} />
        </button>
      </div>

      {NAV.map(n => (
        <NavLink
          key={n.to}
          to={n.to}
          end={n.to === '/'}
          className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          style={{ justifyContent: collapsed ? 'center' : undefined, padding: collapsed ? '10px 0' : undefined }}
          title={collapsed ? n.label : undefined}
        >
          {n.icon}
          {!collapsed && <span style={{ whiteSpace: 'nowrap' }}>{n.label}</span>}
        </NavLink>
      ))}

    </nav>
  )
}

// ── App ────────────────────────────────────────────────────────────────────

export default function App() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <BrowserRouter>
      <div
        className="shell"
        style={{ gridTemplateColumns: `${collapsed ? 52 : 220}px 1fr`, transition: 'grid-template-columns 0.22s ease' }}
      >
        <Header collapsed={collapsed} />
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} />
        <main className="main">
          <ErrorBoundary>
            <Suspense fallback={<LoadingSpinner message="Loading..." />}>
              <Routes>
                <Route path="/"         element={<Dashboard />} />
                <Route path="/ner"      element={<NERExplorer />} />
                <Route path="/compare"  element={<Comparison />} />
                <Route path="/analysis" element={<Findings />} />
                <Route path="/jobs"     element={<JobRunner />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
    </BrowserRouter>
  )
}
