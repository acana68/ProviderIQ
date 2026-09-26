import { type FormEvent, useEffect, useId, useRef, useState } from 'react'
import { parseQuery } from '../../services/aiApi'
import { type ApiError, isAbortError, toApiError } from '../../services/apiClient'
import { MAX_QUERY_LENGTH, type ParseQueryResponse } from '../../types/search'
import { EXAMPLE_QUERIES } from './exampleQueries'
import styles from './NaturalLanguageSearch.module.css'

interface NaturalLanguageSearchProps {
  /** Called with the parsed criteria after each successful Interpret. */
  onParsed: (result: ParseQueryResponse) => void
}

type Status =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'done'; result: ParseQueryResponse }
  | { kind: 'error'; error: ApiError }

/**
 * "Describe what you need" box. Only fills in criteria (via onParsed); it never searches.
 * The API is called only on submit: typing and the example chips don't call it.
 */
export function NaturalLanguageSearch({ onParsed }: NaturalLanguageSearchProps) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<Status>({ kind: 'idle' })
  const inputRef = useRef<HTMLInputElement>(null)
  const requestRef = useRef<AbortController | null>(null)
  const inputId = useId()
  const counterId = useId()

  // Abort an in-flight parse if the page goes away.
  useEffect(() => () => requestRef.current?.abort(), [])

  const loading = status.kind === 'loading'
  const trimmed = query.trim()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!trimmed || loading) return

    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    setStatus({ kind: 'loading' })
    try {
      const result = await parseQuery(trimmed, { signal: controller.signal })
      setStatus({ kind: 'done', result })
      onParsed(result)
    } catch (error) {
      if (!isAbortError(error)) setStatus({ kind: 'error', error: toApiError(error) })
    }
  }

  function fillExample(example: string) {
    setQuery(example)
    inputRef.current?.focus()
  }

  return (
    <section className={styles.panel} aria-labelledby={`${inputId}-heading`}>
      <h2 id={`${inputId}-heading`} className={styles.heading}>
        Describe what you need
      </h2>
      <form className={styles.form} onSubmit={handleSubmit}>
        <label htmlFor={inputId} className="visually-hidden">
          Describe the provider you're looking for
        </label>
        <div className={styles.inputRow}>
          <input
            ref={inputRef}
            id={inputId}
            className={styles.input}
            type="text"
            value={query}
            maxLength={MAX_QUERY_LENGTH}
            placeholder="e.g. a highly rated cardiologist near New York for heart failure"
            autoComplete="off"
            aria-describedby={counterId}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button
            type="submit"
            className={styles.button}
            disabled={!trimmed || loading}
            aria-busy={loading}
          >
            {loading ? 'Interpreting…' : 'Interpret'}
          </button>
        </div>
        <p id={counterId} className={styles.counter}>
          {query.length}/{MAX_QUERY_LENGTH} characters
        </p>
      </form>

      <div className={styles.examples}>
        <span className={styles.examplesLabel}>Try:</span>
        {EXAMPLE_QUERIES.map((example) => (
          <button
            key={example}
            type="button"
            className={styles.chip}
            onClick={() => fillExample(example)}
          >
            {example}
          </button>
        ))}
      </div>

      <p className="visually-hidden" role="status" aria-live="polite">
        {status.kind === 'loading' && 'Interpreting your description…'}
        {status.kind === 'done' && 'Search criteria filled in below. Review them, then search.'}
      </p>

      {status.kind === 'error' && (
        <p className={styles.error} role="alert">
          Couldn't interpret that: {status.error.message}
        </p>
      )}

      {status.kind === 'done' && (
        <div className={styles.result}>
          <span
            className={
              status.result.parser_used === 'llm'
                ? `${styles.badge} ${styles.badgeAi}`
                : `${styles.badge} ${styles.badgeKeyword}`
            }
          >
            {status.result.parser_used === 'llm' ? 'Interpreted by AI' : 'Keyword matching'}
          </span>
          <span className={styles.resultText}>Criteria filled in below. Adjust as needed.</span>
          {status.result.warnings.length > 0 && (
            <ul className={styles.warnings} aria-label="Notes">
              {status.result.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
