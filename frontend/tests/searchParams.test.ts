import { describe, expect, it } from 'vitest'
import type { SearchCriteria } from '../src/types/search'
import { criteriaToSearchParams, searchParamsToCriteria } from '../src/utils/searchParams'

const FULL: SearchCriteria = {
  specialty: 'cardiology',
  condition: 'heart-failure',
  location: { city: 'New York', state: 'NY' },
  radius_miles: 10,
  min_quality_score: 72.5,
  min_years_experience: 15,
  accepting_new_patients: true,
  priority: 'distance',
  sort: 'quality',
  page: 3,
  source: 'nl',
  parser_used: 'llm',
}

/** Criteria -> URL string -> criteria, the way the /results page gets them. */
function roundTrip(criteria: SearchCriteria): SearchCriteria {
  const url = `/results?${criteriaToSearchParams(criteria)}`
  return searchParamsToCriteria(new URL(url, 'http://localhost').searchParams)
}

function parse(query: string): SearchCriteria {
  return searchParamsToCriteria(new URLSearchParams(query))
}

describe('criteriaToSearchParams', () => {
  it('writes every field', () => {
    expect(Object.fromEntries(criteriaToSearchParams(FULL))).toEqual({
      specialty: 'cardiology',
      condition: 'heart-failure',
      city: 'New York',
      state: 'NY',
      radius_miles: '10',
      min_quality_score: '72.5',
      min_years_experience: '15',
      accepting_new_patients: 'true',
      priority: 'distance',
      sort: 'quality',
      page: '3',
      source: 'nl',
      parser_used: 'llm',
    })
  })

  it('omits unset and empty values', () => {
    expect(criteriaToSearchParams({}).toString()).toBe('')
    expect(
      criteriaToSearchParams({
        specialty: '',
        condition: undefined,
        priority: 'balanced',
      }).toString(),
    ).toBe('priority=balanced')
  })

  it('keeps zero', () => {
    expect(criteriaToSearchParams({ min_quality_score: 0 }).toString()).toBe('min_quality_score=0')
  })
})

describe('searchParamsToCriteria', () => {
  it.each<[string, SearchCriteria]>([
    ['everything', FULL],
    ['nothing', {}],
    ['manual, no location', { specialty: 'dermatology', priority: 'cost', source: 'manual' }],
    [
      'zeros and false',
      { min_quality_score: 0, min_years_experience: 0, accepting_new_patients: false },
    ],
    ['a city with spaces and punctuation', { location: { city: "Coeur d'Alene", state: 'ID' } }],
  ])('round-trips %s', (_name, criteria) => {
    expect(roundTrip(criteria)).toEqual(criteria)
  })

  it('upper-cases the state', () => {
    expect(parse('city=Boston&state=ma').location).toEqual({ city: 'Boston', state: 'MA' })
  })

  it.each([
    ['specialty=Cardiology!', 'not a slug'],
    ['specialty=' + 'a'.repeat(101), 'too long'],
    ['condition=heart failure', 'not a slug'],
    ['city=Boston', 'city without state'],
    ['state=MA', 'state without city'],
    ['city=Boston&state=Massachusetts', 'state not two letters'],
    ['radius_miles=10', 'radius without location'],
    ['min_quality_score=abc', 'not a number'],
    ['min_quality_score=150', 'above the maximum'],
    ['min_quality_score=-5', 'negative'],
    ['min_quality_score=1e2', 'exponent'],
    ['min_quality_score=0x10', 'hex'],
    ['min_quality_score=Infinity', 'Infinity'],
    ['min_quality_score=', 'empty'],
    ['min_years_experience=2.5', 'fractional years'],
    ['min_years_experience=71', 'too many years'],
    ['accepting_new_patients=yes', 'not true/false'],
    ['priority=fastest', 'unknown priority'],
    ['priority=distance', 'distance priority without location'],
    ['sort=random', 'unknown sort'],
    ['sort=distance', 'distance sort without location'],
    ['page=0', 'page zero'],
    ['page=-1', 'negative page'],
    ['page=99999999999999999999', 'page beyond safe integers'],
    ['source=email', 'unknown source'],
    ['parser_used=gpt', 'unknown parser'],
    ['parser_used=llm', 'parser without source'],
    ['source=manual&parser_used=llm', 'parser with manual source'],
    ['utm_source=newsletter&%E0%A4%A=1', 'unknown keys and bad encoding'],
  ])('ignores %s (%s)', (query) => {
    const criteria = parse(query)

    // Only a source can be valid in these; nothing else may get through.
    expect(Object.keys(criteria).filter((key) => key !== 'source')).toEqual([])
  })

  it('keeps the valid fields next to garbage ones', () => {
    expect(
      parse(
        'specialty=cardiology&radius_miles=lots&city=Chicago&state=IL&priority=distance&page=two&foo=bar',
      ),
    ).toEqual({
      specialty: 'cardiology',
      location: { city: 'Chicago', state: 'IL' },
      priority: 'distance',
    })
  })

  it('accepts the range boundaries', () => {
    expect(
      parse(
        'city=Austin&state=TX&radius_miles=100&min_quality_score=100&min_years_experience=70&page=1',
      ),
    ).toMatchObject({
      radius_miles: 100,
      min_quality_score: 100,
      min_years_experience: 70,
      page: 1,
    })
    expect(parse('city=Austin&state=TX&radius_miles=1').radius_miles).toBe(1)
    expect(parse('city=Austin&state=TX&radius_miles=0.5').radius_miles).toBeUndefined()
  })
})

describe('require_quality_score', () => {
  it('is written only when true', () => {
    expect(criteriaToSearchParams({ require_quality_score: true }).toString()).toBe(
      'require_quality_score=true',
    )
    expect(criteriaToSearchParams({ require_quality_score: false }).toString()).toBe('')
  })

  it('is read only from "true"', () => {
    const read = (value: string) =>
      searchParamsToCriteria(new URLSearchParams({ require_quality_score: value }))

    expect(read('true')).toEqual({ require_quality_score: true })
    expect(read('false')).toEqual({})
    expect(read('yes')).toEqual({})
  })
})
