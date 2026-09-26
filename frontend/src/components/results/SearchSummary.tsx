import { type ReactNode, useId } from 'react'
import { Link } from 'react-router'
import { useConditions, useSpecialties } from '../../hooks/useReferenceData'
import type { SearchCriteria } from '../../types/search'
import { PARSER_LABELS } from '../../utils/labels'
import styles from './SearchSummary.module.css'

interface SearchSummaryProps {
  criteria: SearchCriteria
  /** Back to the search page with these criteria filled in. */
  changeSearchTo: string
}

/** The search's filters as label/value pairs. Priority and sort live in the toolbar. */
export function SearchSummary({ criteria, changeSearchTo }: SearchSummaryProps) {
  const specialties = useSpecialties()
  // All conditions, not the specialty's: the name is needed even if the pair doesn't match.
  const conditions = useConditions()
  const headingId = useId()

  const rows: [string, ReactNode][] = []
  if (criteria.specialty) {
    const name = specialties.data?.find((s) => s.slug === criteria.specialty)?.name
    rows.push(['Specialty', name ?? humanize(criteria.specialty)])
  }
  if (criteria.condition) {
    const name = conditions.data?.find((c) => c.slug === criteria.condition)?.name
    rows.push(['Condition', name ?? humanize(criteria.condition)])
  }
  if (criteria.location) {
    const { city, state } = criteria.location
    rows.push([
      'Location',
      <>
        {/* Each part wraps as a whole: never "(within 25 / mi)". */}
        <span className={styles.nowrap}>
          {city}, {state}
        </span>
        {criteria.radius_miles !== undefined && (
          <>
            {' '}
            <span className={styles.nowrap}>(within {criteria.radius_miles} mi)</span>
          </>
        )}
      </>,
    ])
  }
  if (criteria.min_quality_score !== undefined) {
    rows.push(['Minimum quality score', String(criteria.min_quality_score)])
  }
  if (criteria.min_years_experience !== undefined) {
    rows.push(['Minimum years of experience', String(criteria.min_years_experience)])
  }
  if (criteria.accepting_new_patients !== undefined) {
    rows.push(['Accepting new patients', criteria.accepting_new_patients ? 'Yes' : 'No'])
  }
  if (criteria.source === 'nl') {
    const parser = criteria.parser_used
      ? ` (interpreted by ${PARSER_LABELS[criteria.parser_used]})`
      : ''
    rows.push(['From', `Your description${parser}`])
  }

  return (
    <section className={styles.card} aria-labelledby={headingId}>
      <div className={styles.heading}>
        <h2 id={headingId} className={styles.title}>
          Your search
        </h2>
        <Link to={changeSearchTo}>Change search</Link>
      </div>
      {rows.length > 0 ? (
        <dl className={styles.summary}>
          {rows.map(([term, detail]) => (
            <div key={term}>
              <dt>{term}</dt>
              <dd>{detail}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className={styles.muted}>No filters: all providers.</p>
      )}
    </section>
  )
}

/** "heart-failure" -> "Heart failure", shown until (or if) the real name can't be loaded. */
function humanize(slug: string): string {
  const words = slug.replaceAll('-', ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}
