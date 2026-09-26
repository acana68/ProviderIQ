import type { SearchRequest, SearchResponse } from '../types/search'
import { apiPost, type RequestOptions } from './apiClient'

/** Ranked search with structured criteria. */
export function search(request: SearchRequest, options?: RequestOptions): Promise<SearchResponse> {
  return apiPost<SearchResponse>('/search', request, options)
}
