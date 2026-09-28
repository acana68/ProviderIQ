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

/** What the dataset can be filtered on (see useDataset). Both true for synthetic data. */
export interface DatasetFilters {
  /** False for CMS: a condition would be rejected by the API. */
  hasConditions?: boolean
  /** False for CMS: nobody's is known, so the filter would match nobody. */
  hasAcceptingNewPatients?: boolean
}

/** Drops filters the dataset can't answer: a condition, or accepting new patients (CMS). */
export function criteriaForDataset(
  criteria: SearchCriteria,
  { hasConditions = true, hasAcceptingNewPatients = true }: DatasetFilters = {},
): SearchCriteria {
  const { condition, accepting_new_patients, ...rest } = criteria
  return {
    ...rest,
    ...(hasConditions && condition !== undefined ? { condition } : {}),
    ...(hasAcceptingNewPatients && accepting_new_patients !== undefined
      ? { accepting_new_patients }
      : {}),
  }
}

/**
 * The criteria to put in the /results URL. A radius only goes with a location (the API
 * rejects one without), and it defaults to the API's 25 miles so the URL says what was
 * searched. Filters the dataset can't answer are dropped (criteriaForDataset).
 */
export function criteriaForSearch(
  criteria: SearchCriteria,
  dataset: DatasetFilters = {},
): SearchCriteria {
  const { radius_miles, ...rest } = criteriaForDataset(criteria, dataset)
  if (!rest.location) return rest
  return { ...rest, radius_miles: radius_miles ?? DEFAULT_RADIUS_MILES }
}

/**
 * Criteria from a URL -> what the editor holds. Sort and page belong to the results page,
 * and where the criteria came from (source, parser_used) is kept separately by SearchPage.
 */
export function criteriaForEditor(criteria: SearchCriteria): SearchCriteria {
  const editable: SearchCriteria = { priority: criteria.priority ?? 'balanced' }
  if (criteria.specialty) editable.specialty = criteria.specialty
  if (criteria.condition) editable.condition = criteria.condition
  if (criteria.location) {
    editable.location = criteria.location
    editable.radius_miles = criteria.radius_miles ?? DEFAULT_RADIUS_MILES
  }
  if (criteria.min_quality_score !== undefined) {
    editable.min_quality_score = criteria.min_quality_score
  }
  if (criteria.min_years_experience !== undefined) {
    editable.min_years_experience = criteria.min_years_experience
  }
  if (criteria.accepting_new_patients) editable.accepting_new_patients = true
  if (criteria.require_quality_score) editable.require_quality_score = true
  return editable
}
