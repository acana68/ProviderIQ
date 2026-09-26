import { useCallback } from 'react'
import { search } from '../services/searchApi'
import type { SearchCriteria, SearchRequest, SearchResponse } from '../types/search'
import { type AsyncData, type Loader, useApiData } from './useApiData'

/**
 * Ranked results for criteria parsed from the URL. Refetches when they change, and a
 * response for older criteria is never shown (see useApiData).
 */
export function useSearch(criteria: SearchCriteria): AsyncData<SearchResponse> {
  // SearchCriteria uses the request's field names, and searchParamsToCriteria already drops
  // what the API would reject, so the criteria are the request body as they are. The JSON is
  // the cache key: the criteria object is new on every render, but its JSON only changes
  // when the URL does (searchParamsToCriteria always builds fields in the same order).
  const body = JSON.stringify(criteria satisfies SearchRequest)
  const load = useCallback<Loader<SearchResponse>>(
    (signal) => search(JSON.parse(body) as SearchRequest, { signal }),
    [body],
  )
  return useApiData(`search:${body}`, load)
}
