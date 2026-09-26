import { Component, type ErrorInfo, type ReactNode } from 'react'
import { useNavigate } from 'react-router'
import styles from './ErrorBoundary.module.css'

interface ErrorBoundaryProps {
  children: ReactNode
  /** When this changes (e.g. on navigation), a caught error is cleared and the children render again. */
  resetKey: string
}

interface ErrorBoundaryState {
  error: Error | null
}

/**
 * Catches errors thrown while rendering a page, so one broken page shows a friendly
 * fallback instead of blanking the whole app. It only wraps the routed content: the header
 * and disclaimer stay put. (Errors in event handlers and fetches aren't render errors;
 * pages show those themselves.)
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Page crashed:', error, info.componentStack)
  }

  override componentDidUpdate(previous: ErrorBoundaryProps) {
    if (this.state.error && previous.resetKey !== this.props.resetKey) {
      this.setState({ error: null })
    }
  }

  override render() {
    return this.state.error ? <ErrorFallback /> : this.props.children
  }
}

function ErrorFallback() {
  const navigate = useNavigate()
  return (
    <section className={styles.fallback} role="alert">
      <title>Something went wrong · ProviderIQ</title>
      <h1 className={styles.title}>Something went wrong on this page.</h1>
      <p className={styles.text}>
        Try reloading it, or start again from the home page. If it keeps happening, the problem is
        on our side.
      </p>
      <div className={styles.actions}>
        {/* Navigating changes the reset key, which clears the error. */}
        <button type="button" className={styles.primary} onClick={() => navigate('/')}>
          Go to home
        </button>
        <button type="button" className={styles.secondary} onClick={() => window.location.reload()}>
          Reload
        </button>
      </div>
    </section>
  )
}
