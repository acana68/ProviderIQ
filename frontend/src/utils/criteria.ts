import { DEFAULT_RADIUS_MILES, type ParsedCriteria, type SearchCriteria } from '../types/search'

/** What the editor starts with. */
export const INITIAL_CRITERIA: SearchCriteria = { priority: 'balanced' }

/** AI-parsed criteria (nulls for "not mentioned") -> editor criteria (missing fields). */
export function criteriaFromParsed(parsed: ParsedCriteria): SearchCriteria {
  // Distance needs a location; the editor wouldn't let the user pick it without one either.
  const priority = parsed.priority === 'distance' && !parsed.location ? null : parsed.priority
  const criteria: SearchCriteria = { priority: priority ?? 'balanced' }
  if (parsed.specialty) criteria.specialty = parsed.specialty
  if (parsed.condition) criteria.condition = parsed.condition
  if (parsed.location) {
    criteria.location = parsed.location
    criteria.radius_miles = parsed.radius_miles ?? DEFAULT_RADIUS_MILES
  }
  if (parsed.min_quality_score !== null) criteria.min_quality_score = parsed.min_quality_score
  if (parsed.min_years_experience !== null) {
    criteria.min_years_experience = parsed.min_years_experience
  }
  if (parsed.accepting_new_patients) criteria.accepting_new_patients = true
  return criteria
}

/**
 * The criteria to put in the /results URL. A radius only goes with a location (the API
 * rejects one without), and it defaults to the API's 25 miles so the URL says what was
 * searched.
 */
export function criteriaForSearch(criteria: SearchCriteria): SearchCriteria {
  const { radius_miles, ...rest } = criteria
  if (!rest.location) return rest
  return { ...rest, radius_miles: radius_miles ?? DEFAULT_RADIUS_MILES }
}
