import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, FlaskConical, Cpu, BarChart3, Play } from 'lucide-react'
import { useQuery } from './hooks/useQuery'
import { api } from './api/client'
import Dashboard   from './pages/Dashboard'
import NERExplorer from './pages/NERExplorer'
import Comparison  from './pages/Comparison'
import JobRunner   from './pages/JobRunner'

function Sidebar() {
  const loc = useLocation()
  const nav = [
    { to: '/',         icon: <LayoutDashboard size={15} />, label: 'Observatory' },
    { to: '/ner',      icon: <FlaskConical size={15} />,    label: 'NER Explorer' },
    { to: '/compare',  icon: <BarChart3 size={15} />,       label: 'TF-IDF Compare' },
    { to: '/jobs',     icon: <Play size={15} />,            label: 'Job Runner' },
  ]
  return (
    <nav className="sidebar">
      <div className="sidebar-section">Navigation</div>
      {nav.map(n => (
        <NavLink
          key={n.to}
          to={n.to}
          end={n.to === '/'}
          className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
        >
          {n.icon}
          {n.label}
        </NavLink>
      ))}
      <div className="sidebar-section" style={{ marginTop: 'auto' }}>System</div>
      <div className="nav-item" style={{ cursor: 'default', fontSize: 12 }}>
        <Cpu size={14} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
          {loc.pathname === '/' ? 'Dashboard' : 'Active'}
        </span>
      </div>
    </nav>
  )
}

function Header() {
  const { data, error } = useQuery(() => api.health(), [], { interval: 30_000 })

  const mongo = !error && data?.mongodb === 'healthy'
  const ner   = (data?.collections.ner ?? 0) > 0

  return (
    <header className="header">
      <div className="header-brand">
        <h1>NLP Research Station</h1>
        <span className="tag">v1.0</span>
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

export default function App() {
  return (
    <BrowserRouter>
      <div className="shell">
        <Header />
        <Sidebar />
        <main className="main">
          <Routes>
            <Route path="/"        element={<Dashboard />} />
            <Route path="/ner"     element={<NERExplorer />} />
            <Route path="/compare" element={<Comparison />} />
            <Route path="/jobs"    element={<JobRunner />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
