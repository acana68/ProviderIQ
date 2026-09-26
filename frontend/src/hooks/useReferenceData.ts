import { useCallback, useEffect, useState } from 'react'
import { type ApiError, isAbortError, toApiError } from '../services/apiClient'
import { getCities, getConditions, getSpecialties } from '../services/referenceApi'
import type { ConditionSummary, SpecialtySummary } from '../types/provider'
import type { Location } from '../types/search'

export interface AsyncData<T> {
  data: T | null
  loading: boolean
  error: ApiError | null
}

type Loader<T> = (signal: AbortSignal) => Promise<T>

/**
 * Runs `load` whenever `key` changes and aborts the request on change or unmount.
 *
 * The result is stored with the key it was loaded for, and `loading` is derived from
 * whether that key is still current. That avoids setting state synchronously inside the
 * effect, and a stale response can never be shown for a newer key.
 */
function useApiData<T>(key: string, load: Loader<T>): AsyncData<T> {
  const [result, setResult] = useState<{ key: string; data: T | null; error: ApiError | null }>()

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal).then(
      (data) => setResult({ key, data, error: null }),
      (error: unknown) => {
        if (!isAbortError(error)) setResult({ key, data: null, error: toApiError(error) })
      },
    )
    return () => controller.abort()
  }, [key, load])

  if (result?.key !== key) return { data: null, loading: true, error: null }
  return { data: result.data, loading: false, error: result.error }
}

const loadSpecialties: Loader<SpecialtySummary[]> = (signal) => getSpecialties({ signal })
const loadCities: Loader<Location[]> = (signal) => getCities({ signal })

export function useSpecialties(): AsyncData<SpecialtySummary[]> {
  return useApiData('specialties', loadSpecialties)
}

/** Conditions treated within `specialty` (a slug), or all conditions. */
export function useConditions(specialty?: string): AsyncData<ConditionSummary[]> {
  const load = useCallback<Loader<ConditionSummary[]>>(
    (signal) => getConditions(specialty, { signal }),
    [specialty],
  )
  return useApiData(`conditions:${specialty ?? ''}`, load)
}

export function useCities(): AsyncData<Location[]> {
  return useApiData('cities', loadCities)
}
