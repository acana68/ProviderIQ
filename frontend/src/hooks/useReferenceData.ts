import { useCallback } from 'react'
import { getCities, getConditions, getSpecialties } from '../services/referenceApi'
import type { ConditionSummary, SpecialtySummary } from '../types/provider'
import type { Location } from '../types/search'
import { type AsyncData, type Loader, useApiData } from './useApiData'

const loadSpecialties: Loader<SpecialtySummary[]> = (signal) => getSpecialties({ signal })
const loadCities: Loader<Location[]> = (signal) => getCities({ signal })

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
