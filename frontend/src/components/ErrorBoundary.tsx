import { Component, type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  handleReset = () => {
    this.setState({ error: null })
  }

  render() {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div
          role="alert"
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 16,
            padding: '48px 24px',
            color: 'var(--text-secondary)',
          }}
        >
          <AlertTriangle size={32} color="var(--error)" strokeWidth={1.5} />
          <div style={{ textAlign: 'center' }}>
            <p style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 6 }}>
              Something went wrong
            </p>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: 400 }}>
              {this.state.error.message}
            </p>
          </div>
          <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={this.handleReset}>
            <RefreshCw size={13} /> Try again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
