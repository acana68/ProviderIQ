// Mirrors backend/app/schemas/search.py and ai.py (plus Location from common.py).

import type { Page } from './api'
import type { ComponentName, ProviderScore, ProviderSummary } from './provider'

export const PRIORITIES = ['balanced', 'quality', 'cost', 'experience', 'distance'] as const
export type Priority = (typeof PRIORITIES)[number]

export const SORT_OPTIONS = ['match', 'quality', 'experience', 'distance', 'cost'] as const
export type SortOption = (typeof SORT_OPTIONS)[number]

export type ParserUsed = 'llm' | 'rule_based'
export type SearchSource = 'nl' | 'manual'

/** A city from GET /cities; also the `location` of a search. */
export interface Location {
  city: string
  /** Two-letter code, e.g. "NY". */
  state: string
}

/**
 * POST /search body. Optional fields fall back to the backend defaults. The backend
 * rejects unknown fields, a radius or distance priority/sort without a location, and
 * parser_used without source "nl".
 */
export interface SearchRequest {
  specialty?: string | null
  condition?: string | null
  location?: Location | null
  /** 1-100, default 25. Only allowed with a location. */
  radius_miles?: number
  /** 0-100. */
  min_quality_score?: number | null
  /** 0-70. */
  min_years_experience?: number | null
  accepting_new_patients?: boolean | null
  /** Default "balanced". */
  priority?: Priority
  /** Default "match". */
  sort?: SortOption
  /** Default 1. */
  page?: number
  /** 1-50, default 20. */
  page_size?: number
  /** Default "manual". */
  source?: SearchSource
  parser_used?: ParserUsed | null
}

export interface SearchResult {
  provider: ProviderSummary
  /** Rounded to 0.1 mile; null when the search has no location. */
  distance_miles: number | null
  score: ProviderScore
  explanation: string
}

export interface SearchResponse extends Page<SearchResult> {
  priority: Priority
  sort: SortOption
  /** Effective weights after renormalization; no distance entry without a location. */
  weights_used: Partial<Record<ComponentName, number>>
}

/** Criteria from POST /ai/parse-query: same field names and shapes as SearchRequest. */
export interface ParsedCriteria {
  specialty: string | null
  condition: string | null
  location: Location | null
  radius_miles: number | null
  min_quality_score: number | null
  min_years_experience: number | null
  accepting_new_patients: boolean | null
  priority: Priority | null
}

export interface ParseQueryRequest {
  /** Trimmed by the backend; 1-500 characters. */
  query: string
}

export interface ParseQueryResponse {
  criteria: ParsedCriteria
  parser_used: ParserUsed
  /** Human-readable notes: what was inferred, dropped, or fell back. */
  warnings: string[]
}

/** Backend limits and defaults (backend/app/schemas/). */
export const DEFAULT_RADIUS_MILES = 25
export const MIN_RADIUS_MILES = 1
export const MAX_RADIUS_MILES = 100
export const MAX_QUERY_LENGTH = 500

/**
 * Search criteria as the frontend holds them: in the editor, and in the /results URL.
 * A missing field means "not set"; see utils/searchParams.ts for the URL format.
 */
export interface SearchCriteria {
  specialty?: string
  condition?: string
  location?: Location
  radius_miles?: number
  min_quality_score?: number
  min_years_experience?: number
  accepting_new_patients?: boolean
  priority?: Priority
  sort?: SortOption
  page?: number
  source?: SearchSource
  parser_used?: ParserUsed
}
