import type { ParseQueryResponse } from '../types/search'
import { apiPost, type RequestOptions } from './apiClient'

/**
 * Natural language -> search criteria. Never runs a search. Succeeds even when the AI is
 * unavailable: the backend then answers with keyword matching (parser_used "rule_based").
 */
export function parseQuery(query: string, options?: RequestOptions): Promise<ParseQueryResponse> {
  return apiPost<ParseQueryResponse>('/ai/parse-query', { query }, options)
}
