/**
 * Search criteria <-> URL query string, e.g. for /results?specialty=cardiology&city=...
 *
 * Search state lives in the URL, so results survive a refresh, can be shared, and work
 * with the back button. The URL is user input, so parsing is strict: anything malformed or
 * out of range is dropped rather than passed on to the API, and nothing here throws.
 */

import {
  MAX_RADIUS_MILES,
  MIN_RADIUS_MILES,
  PRIORITIES,
  SORT_OPTIONS,
  type ParserUsed,
  type SearchCriteria,
  type SearchSource,
} from '../types/search'

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/
const STATE = /^[A-Za-z]{2}$/
const DECIMAL = /^\d+(?:\.\d+)?$/
const INTEGER = /^\d+$/
const MAX_TEXT_LENGTH = 100
const SOURCES: readonly SearchSource[] = ['nl', 'manual']
const PARSERS: readonly ParserUsed[] = ['llm', 'rule_based']

/** Criteria -> query string parameters. Unset values are left out entirely. */
export function criteriaToSearchParams(criteria: SearchCriteria): URLSearchParams {
  const params = new URLSearchParams()
  const set = (key: string, value: string | number | boolean | undefined) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  set('specialty', criteria.specialty)
  set('condition', criteria.condition)
  set('city', criteria.location?.city)
  set('state', criteria.location?.state)
  set('radius_miles', criteria.radius_miles)
  set('min_quality_score', criteria.min_quality_score)
  set('min_years_experience', criteria.min_years_experience)
  set('accepting_new_patients', criteria.accepting_new_patients)
  set('priority', criteria.priority)
  set('sort', criteria.sort)
  set('page', criteria.page)
  set('source', criteria.source)
  set('parser_used', criteria.parser_used)
  return params
}

/**
 * Query string -> criteria. Invalid values are ignored, and so are combinations the API
 * would reject: a radius or distance priority/sort without a location, or parser_used
 * without source "nl".
 */
export function searchParamsToCriteria(params: URLSearchParams): SearchCriteria {
  const criteria: SearchCriteria = {}
  const text = (key: string) => {
    const value = params.get(key)?.trim()
    return value && value.length <= MAX_TEXT_LENGTH ? value : undefined
  }

  const specialty = text('specialty')
  if (specialty && SLUG.test(specialty)) criteria.specialty = specialty
  const condition = text('condition')
  if (condition && SLUG.test(condition)) criteria.condition = condition

  const city = text('city')
  const state = text('state')
  if (city && state && STATE.test(state)) {
    criteria.location = { city, state: state.toUpperCase() }
  }

  const radius = number(params.get('radius_miles'), DECIMAL, MIN_RADIUS_MILES, MAX_RADIUS_MILES)
  if (radius !== undefined && criteria.location) criteria.radius_miles = radius
  const quality = number(params.get('min_quality_score'), DECIMAL, 0, 100)
  if (quality !== undefined) criteria.min_quality_score = quality
  const years = number(params.get('min_years_experience'), INTEGER, 0, 70)
  if (years !== undefined) criteria.min_years_experience = years

  const accepting = params.get('accepting_new_patients')
  if (accepting === 'true' || accepting === 'false') {
    criteria.accepting_new_patients = accepting === 'true'
  }

  const priority = oneOf(params.get('priority'), PRIORITIES)
  if (priority && (priority !== 'distance' || criteria.location)) criteria.priority = priority
  const sort = oneOf(params.get('sort'), SORT_OPTIONS)
  if (sort && (sort !== 'distance' || criteria.location)) criteria.sort = sort

  const page = number(params.get('page'), INTEGER, 1, Number.MAX_SAFE_INTEGER)
  if (page !== undefined) criteria.page = page

  const source = oneOf(params.get('source'), SOURCES)
  if (source) criteria.source = source
  const parser = oneOf(params.get('parser_used'), PARSERS)
  if (parser && source === 'nl') criteria.parser_used = parser

  return criteria
}

function number(
  value: string | null,
  format: RegExp,
  min: number,
  max: number,
): number | undefined {
  // The regexes reject what Number() would accept but a user never means: "1e3", "0x10",
  // " 12", "Infinity", "-5".
  if (value === null || !format.test(value)) return undefined
  const parsed = Number(value)
  return parsed >= min && parsed <= max ? parsed : undefined
}

function oneOf<T extends string>(value: string | null, allowed: readonly T[]): T | undefined {
  return allowed.find((option) => option === value)
}
