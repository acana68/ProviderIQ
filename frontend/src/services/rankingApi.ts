import type { RankingWeightsResponse } from '../types/ranking'
import { apiGet, type RequestOptions } from './apiClient'

/** The weight profile for each priority, straight from the ranking engine. */
export function getRankingWeights(options?: RequestOptions): Promise<RankingWeightsResponse> {
  return apiGet<RankingWeightsResponse>('/ranking/weights', options)
}
