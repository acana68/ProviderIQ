import type { ConditionSummary, SpecialtySummary } from '../types/provider'
import type { Location } from '../types/search'
import { apiGet, type RequestOptions } from './apiClient'

/** All specialties, ordered by name, with provider counts. */
export function getSpecialties(options?: RequestOptions): Promise<SpecialtySummary[]> {
  return apiGet<SpecialtySummary[]>('/specialties', options)
}

/** All conditions, or only those treated within a specialty (by slug). */
export function getConditions(
  specialty?: string,
  options?: RequestOptions,
): Promise<ConditionSummary[]> {
  const query = specialty ? `?${new URLSearchParams({ specialty })}` : ''
  return apiGet<ConditionSummary[]>(`/conditions${query}`, options)
}

/** Cities a search can use, ordered by state then name; each is a ready-made `location`. */
export function getCities(options?: RequestOptions): Promise<Location[]> {
  return apiGet<Location[]>('/cities', options)
}
