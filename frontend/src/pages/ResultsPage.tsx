import { Link, useSearchParams } from 'react-router'
import type { ParserUsed, Priority, SearchCriteria, SortOption } from '../types/search'
import { searchParamsToCriteria } from '../utils/searchParams'
import styles from './ResultsPage.module.css'

const PRIORITY_LABELS: Record<Priority, string> = {
  balanced: 'Balanced',
  quality: 'Quality',
  cost: 'Cost',
  experience: 'Experience',
  distance: 'Distance',
}

const SORT_LABELS: Record<SortOption, string> = {
  match: 'Best match',
  quality: 'Quality',
  experience: 'Experience',
  distance: 'Distance',
  cost: 'Cost',
}

const PARSER_LABELS: Record<ParserUsed, string> = {
  llm: 'AI',
  rule_based: 'keyword matching',
}

export function ResultsPage() {
  const [params] = useSearchParams()
  const criteria = searchParamsToCriteria(params)
  const rows = summarize(criteria)

  return (
    <section className={styles.page}>
      <title>Results · ProviderIQ</title>
      <h1>Results</h1>

      <div className={styles.card}>
        <h2 className={styles.cardHeading}>Your search</h2>
        {rows.length > 0 ? (
          <dl className={styles.summary}>
            {rows.map(([term, detail]) => (
              <div key={term} className={styles.row}>
                <dt>{term}</dt>
                <dd>{detail}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className={styles.muted}>No filters: all providers.</p>
        )}
        <Link to="/">Change search</Link>
      </div>

      <p className={styles.muted}>Ranked search results will appear here.</p>
    </section>
  )
}

/** Criteria as label/value rows, in the order the editor shows them. Unset fields are left out. */
function summarize(criteria: SearchCriteria): [string, string][] {
  const rows: [string, string][] = []
  if (criteria.specialty) rows.push(['Specialty', humanize(criteria.specialty)])
  if (criteria.condition) rows.push(['Condition', humanize(criteria.condition)])
  if (criteria.location) {
    const { city, state } = criteria.location
    const radius =
      criteria.radius_miles === undefined ? '' : ` (within ${criteria.radius_miles} mi)`
    rows.push(['Location', `${city}, ${state}${radius}`])
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
  if (criteria.priority) rows.push(['Priority', PRIORITY_LABELS[criteria.priority]])
  if (criteria.sort) rows.push(['Sort', SORT_LABELS[criteria.sort]])
  if (criteria.page) rows.push(['Page', String(criteria.page)])
  if (criteria.source === 'nl') {
    const parser = criteria.parser_used
      ? ` (interpreted by ${PARSER_LABELS[criteria.parser_used]})`
      : ''
    rows.push(['From', `Your description${parser}`])
  } else if (criteria.source === 'manual') {
    rows.push(['From', 'Manual criteria'])
  }
  return rows
}

/** "heart-failure" -> "Heart failure". Real names come with the results in Stage 10. */
function humanize(slug: string): string {
  const words = slug.replaceAll('-', ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}
