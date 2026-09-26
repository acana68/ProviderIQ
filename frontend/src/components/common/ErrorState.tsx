import type { ApiError } from '../../services/apiClient'
import styles from './states.module.css'

interface ErrorStateProps {
  error: ApiError
  title?: string
  onRetry?: () => void
}

/** A failed request: the API's message, plus the request ID to quote when reporting it. */
export function ErrorState({ error, title = 'Something went wrong', onRetry }: ErrorStateProps) {
  return (
    <div className={styles.error} role="alert">
      <p className={styles.title}>{title}</p>
      <p>{error.message}</p>
      {error.requestId && (
        <p className={styles.meta}>
          Request ID: <code>{error.requestId}</code>
        </p>
      )}
      {onRetry && (
        <button type="button" className={styles.retry} onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}
