import { describe, expect, it } from 'vitest'
import type { ParsedCriteria } from '../src/types/search'
import { criteriaForSearch, criteriaFromParsed } from '../src/utils/criteria'

const EMPTY_PARSED: ParsedCriteria = {
  specialty: null,
  condition: null,
  location: null,
  radius_miles: null,
  min_quality_score: null,
  min_years_experience: null,
  accepting_new_patients: null,
  priority: null,
}

describe('criteriaFromParsed', () => {
  it('drops nulls and defaults the priority', () => {
    expect(criteriaFromParsed(EMPTY_PARSED)).toEqual({ priority: 'balanced' })
  })

  it('keeps every parsed value', () => {
    expect(
      criteriaFromParsed({
        specialty: 'cardiology',
        condition: 'heart-failure',
        location: { city: 'New York', state: 'NY' },
        radius_miles: 10,
        min_quality_score: 0,
        min_years_experience: 5,
        accepting_new_patients: true,
        priority: 'distance',
      }),
    ).toEqual({
      specialty: 'cardiology',
      condition: 'heart-failure',
      location: { city: 'New York', state: 'NY' },
      radius_miles: 10,
      min_quality_score: 0,
      min_years_experience: 5,
      accepting_new_patients: true,
      priority: 'distance',
    })
  })

  it('gives a location the default radius', () => {
    const location = { city: 'Chicago', state: 'IL' }
    expect(criteriaFromParsed({ ...EMPTY_PARSED, location })).toMatchObject({
      location,
      radius_miles: 25,
    })
  })

  it('drops a radius and distance priority without a location', () => {
    expect(criteriaFromParsed({ ...EMPTY_PARSED, radius_miles: 10, priority: 'distance' })).toEqual(
      { priority: 'balanced' },
    )
  })

  it('treats accepting_new_patients false as not set', () => {
    expect(criteriaFromParsed({ ...EMPTY_PARSED, accepting_new_patients: false })).toEqual({
      priority: 'balanced',
    })
  })
})

describe('criteriaForSearch', () => {
  it('drops a radius without a location', () => {
    expect(criteriaForSearch({ radius_miles: 10, priority: 'quality' })).toEqual({
      priority: 'quality',
    })
  })

  it('fills in the default radius for a location', () => {
    const location = { city: 'Chicago', state: 'IL' }
    expect(criteriaForSearch({ location })).toEqual({ location, radius_miles: 25 })
    expect(criteriaForSearch({ location, radius_miles: 5 })).toEqual({ location, radius_miles: 5 })
  })
})
