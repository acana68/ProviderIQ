import { useCallback, useEffect, useState } from 'react'
import { type ApiError, isAbortError, toApiError } from '../services/apiClient'

export interface AsyncData<T> {
  data: T | null
  loading: boolean
  error: ApiError | null
  /** Loads the same key again, e.g. from an error's "Try again" button. */
  retry: () => void
  /** The last data loaded, for any key: lets a page keep showing it while it refetches. */
  previous: T | null
}

export type Loader<T> = (signal: AbortSignal) => Promise<T>

/**
 * Runs `load` whenever `key` changes and aborts the request on change or unmount.
 *
 * The result is stored with the key it was loaded for, and `loading` is derived from
 * whether that key is still current. That avoids setting state synchronously inside the
 * effect. A response that arrives after its effect was cleaned up is dropped even if the
 * abort came too late to stop it, so an older request can never overwrite a newer one.
 */
export function useApiData<T>(key: string, load: Loader<T>): AsyncData<T> {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<{ key: string; data: T | null; error: ApiError | null }>()
  const requestKey = `${attempt}:${key}`

  useEffect(() => {
    const controller = new AbortController()
    let current = true
    load(controller.signal).then(
      (data) => {
        if (current) setResult({ key: requestKey, data, error: null })
      },
      (error: unknown) => {
        if (current && !isAbortError(error)) {
          setResult({ key: requestKey, data: null, error: toApiError(error) })
        }
      },
    )
    return () => {
      current = false
      controller.abort()
    }
  }, [requestKey, load])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])

  const previous = result?.data ?? null
  if (result?.key !== requestKey) return { data: null, loading: true, error: null, retry, previous }
  return { data: result.data, loading: false, error: result.error, retry, previous }
}
