import { useCallback } from 'react'
import { getRankingWeights } from '../services/rankingApi'
import { getCities, getConditions, getSpecialties } from '../services/referenceApi'
import type { ConditionSummary, SpecialtySummary } from '../types/provider'
import type { RankingWeightsResponse } from '../types/ranking'
import type { Location } from '../types/search'
import { type AsyncData, type Loader, useApiData } from './useApiData'

const loadSpecialties: Loader<SpecialtySummary[]> = (signal) => getSpecialties({ signal })
const loadCities: Loader<Location[]> = (signal) => getCities({ signal })
const loadWeights: Loader<RankingWeightsResponse> = (signal) => getRankingWeights({ signal })

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

export function useRankingWeights(): AsyncData<RankingWeightsResponse> {
  return useApiData('ranking-weights', loadWeights)
}
