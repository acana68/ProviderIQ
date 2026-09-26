import type { ProviderDetail, ScoredProviderDetail } from '../types/provider'
import type { Priority, SearchCriteria } from '../types/search'
import { scoreContextParams } from '../utils/searchParams'
import { apiGet, type RequestOptions } from './apiClient'

/** What a provider is scored for: the settings of the search the user came from. */
export type ScoreContext = Pick<SearchCriteria, 'location' | 'radius_miles'> & {
  priority: Priority
}

/** One provider, plus its score when a context is given. 404 if there's no such provider. */
export function getProvider(
  id: number,
  context: ScoreContext | null,
  options?: RequestOptions,
): Promise<ProviderDetail | ScoredProviderDetail> {
  const query = context ? `?${scoreContextParams(context)}` : ''
  return apiGet<ProviderDetail | ScoredProviderDetail>(`/providers/${id}${query}`, options)
}

export function isScored(
  provider: ProviderDetail | ScoredProviderDetail,
): provider is ScoredProviderDetail {
  return 'score' in provider
}
