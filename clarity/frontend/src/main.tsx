import { Component, type ReactNode, StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Unhandled interface error:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '40px 28px', maxWidth: 800, margin: '60px auto', fontFamily: 'var(--sans, system-ui)' }}>
          <div className="banner" role="alert" style={{ background: '#fff', border: '1px solid #e3e1da', padding: 24, borderRadius: 6, boxShadow: '0 4px 16px rgba(0,0,0,0.08)' }}>
            <h2 style={{ marginTop: 0, color: 'var(--critical, #8c2a2a)' }}>Application Error Encountered</h2>
            <p style={{ color: 'var(--ink-soft, #38495a)' }}>
              An unhandled interface error occurred:
            </p>
            <pre style={{ background: 'var(--surface-sunk, #f2f1ec)', padding: 12, borderRadius: 4, overflow: 'auto', fontSize: 12 }}>
              {this.state.error?.message || String(this.state.error)}
            </pre>
            <div style={{ marginTop: 16 }}>
              <button
                type="button"
                className="btn primary"
                onClick={() => {
                  this.setState({ hasError: false, error: null })
                  window.location.reload()
                }}
              >
                Reload Application
              </button>
            </div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
