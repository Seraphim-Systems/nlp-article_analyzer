import { useState, useEffect } from 'react';
import { Activity, Database, Newspaper, ShieldCheck, AlertTriangle, RefreshCw, ExternalLink } from 'lucide-react';
import './App.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Health {
  status: string;
  database: string;
  timestamp: string;
}

interface Stats {
  clean_count: number;
  raw_counts: Record<string, number>;
  timestamp: string;
}

interface Article {
  url: string;
  title: string;
  feed: string;
  pub: string | null;
  lang: string | null;
}

function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [hRes, sRes, aRes] = await Promise.all([
        fetch(`${API_BASE}/health`),
        fetch(`${API_BASE}/stats`),
        fetch(`${API_BASE}/articles?limit=10`)
      ]);

      if (!hRes.ok || !sRes.ok || !aRes.ok) throw new Error('API fetch failed');

      const hData = await hRes.json();
      const sData = await sRes.json();
      const aData = await aRes.json();

      setHealth(hData);
      setStats(sData);
      setArticles(aData.items);
      setError(null);
    } catch (err) {
      setError('Could not connect to the API. Ensure the backend is running at ' + API_BASE);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="container">
      <header className="header">
        <div className="brand">
          <Activity className="logo" />
          <h1>NLP Article Analyzer</h1>
        </div>
        <div className="status-bar">
          <button className="refresh-btn" onClick={fetchData} disabled={loading}>
            <RefreshCw className={loading ? 'spinning' : ''} size={18} />
          </button>
          {health && (
            <div className={`badge ${health.status === 'healthy' ? 'success' : 'warning'}`}>
              {health.status === 'healthy' ? <ShieldCheck size={16} /> : <AlertTriangle size={16} />}
              <span>System: {health.status}</span>
            </div>
          )}
          {health && (
            <div className={`badge ${health.database === 'connected' ? 'success' : 'danger'}`}>
              <Database size={16} />
              <span>DB: {health.database}</span>
            </div>
          )}
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <main className="dashboard">
        <section className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon clean"><ShieldCheck size={24} /></div>
            <div className="stat-content">
              <span className="stat-label">Clean Articles</span>
              <span className="stat-value">{stats?.clean_count ?? 0}</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon raw"><Newspaper size={24} /></div>
            <div className="stat-content">
              <span className="stat-label">Raw Scraped</span>
              <span className="stat-value">{Object.values(stats?.raw_counts ?? {}).reduce((a, b) => a + b, 0)}</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon unranked"><AlertTriangle size={24} /></div>
            <div className="stat-content">
              <span className="stat-label">Unranked</span>
              <span className="stat-value">{stats?.raw_counts['unranked'] ?? 0}</span>
            </div>
          </div>
        </section>

        <section className="recent-articles">
          <div className="section-header">
            <h2><Newspaper size={20} /> Recent Clean Articles</h2>
          </div>
          <div className="table-container">
            <table className="article-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Source</th>
                  <th>Published</th>
                  <th>Lang</th>
                  <th>Link</th>
                </tr>
              </thead>
              <tbody>
                {articles.length > 0 ? (
                  articles.map((art, idx) => (
                    <tr key={idx}>
                      <td className="title-cell">{art.title}</td>
                      <td><span className="feed-badge">{art.feed}</span></td>
                      <td>{art.pub ? new Date(art.pub).toLocaleDateString() : 'N/A'}</td>
                      <td>{art.lang?.toUpperCase() ?? 'EN'}</td>
                      <td>
                        <a href={art.url} target="_blank" rel="noopener noreferrer" className="icon-link">
                          <ExternalLink size={16} />
                        </a>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="empty-state">No clean articles found. Run the cleaning pipeline.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      <footer className="footer">
        <p>NLP Article Analyzer &bull; {new Date().getFullYear()}</p>
        {stats && <p className="last-update">Last update: {new Date(stats.timestamp).toLocaleTimeString()}</p>}
      </footer>
    </div>
  );
}

export default App;
