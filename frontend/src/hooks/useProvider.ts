import { useCallback } from 'react'
import { getProvider, type ScoreContext } from '../services/providerApi'
import type { ProviderDetail, ScoredProviderDetail } from '../types/provider'
import { type AsyncData, type Loader, useApiData } from './useApiData'

/**
 * One provider, scored for `context` when given. Refetches when either changes, and a
 * response for an older id or context is never shown (see useApiData).
 */
export function useProvider(
  id: number,
  context: ScoreContext | null,
): AsyncData<ProviderDetail | ScoredProviderDetail> {
  // The context object is new on every render; its JSON is stable (see useSearch).
  const contextJson = JSON.stringify(context)
  const load = useCallback<Loader<ProviderDetail | ScoredProviderDetail>>(
    (signal) => getProvider(id, JSON.parse(contextJson) as ScoreContext | null, { signal }),
    [id, contextJson],
  )
  return useApiData(`provider:${id}:${contextJson}`, load)
}
