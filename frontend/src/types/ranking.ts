// Mirrors backend/app/schemas/ranking.py.

import type { ComponentName } from './provider'
import type { Priority } from './search'

/** GET /ranking/weights: the engine's base weight profiles. */
export interface RankingWeightsResponse {
  /** Each profile sums to 1. */
  profiles: Record<Priority, Record<ComponentName, number>>
  /** No profile gives quality less than this. */
  min_quality_weight: number
}
