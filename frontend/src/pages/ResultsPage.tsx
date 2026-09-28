import { Link, useSearchParams } from 'react-router'
import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'
import { Pagination } from '../components/results/Pagination'
import { ProviderCard, ProviderCardSkeleton } from '../components/results/ProviderCard'
import { ResultsToolbar } from '../components/results/ResultsToolbar'
import { ScoreLegend } from '../components/results/ScoreLegend'
import { SearchSummary } from '../components/results/SearchSummary'
import { useDataset } from '../hooks/useDataset'
import { useSearch } from '../hooks/useSearch'
import { DEFAULT_RADIUS_MILES, MAX_RADIUS_MILES, type SearchCriteria } from '../types/search'
import {
  criteriaToSearchParams,
  scoreContextParams,
  searchParamsToCriteria,
} from '../utils/searchParams'
import { criteriaForDataset } from '../utils/criteria'
import styles from './ResultsPage.module.css'

const SKELETON_COUNT = 3

/** Ranked results for the criteria in the URL. The URL is the only state: every control
 * here rewrites it, and the search follows. */
export function ResultsPage() {
  const [params, setParams] = useSearchParams()
  const { isCms, hasConditions } = useDataset()
  // A URL may carry a filter this dataset can't answer (e.g. an old link): it's dropped.
  const criteria = criteriaForDataset(searchParamsToCriteria(params), {
    hasConditions,
    hasAcceptingNewPatients: !isCms,
  })
  const results = useSearch(criteria)
  const { data } = results

  const hasLocation = criteria.location !== undefined
  const priority = criteria.priority ?? 'balanced'
  const changeSearchTo = `/?${criteriaToSearchParams({ ...criteria, sort: undefined, page: undefined })}`
  const detailQuery = scoreContextParams(criteria).toString()

  function update(changes: SearchCriteria) {
    setParams(criteriaToSearchParams({ ...criteria, ...changes }))
  }

  function changePage(page: number) {
    // Page 1 is the default, so it's left out of the URL.
    update({ page: page === 1 ? undefined : page })
    window.scrollTo({ top: 0 })
  }

  return (
    <div className={styles.page}>
      <title>Results · ProviderIQ</title>
      <h1 className={styles.title}>Results</h1>

      <SearchSummary criteria={criteria} changeSearchTo={changeSearchTo} />

      <ResultsToolbar
        total={data?.total ?? null}
        loading={results.loading}
        sort={criteria.sort ?? 'match'}
        priority={priority}
        hasLocation={hasLocation}
        // A new ordering starts again from page 1.
        onSortChange={(sort) => update({ sort, page: undefined })}
        onPriorityChange={(next) => update({ priority: next, page: undefined })}
      />

      {results.loading && (
        // Hidden from screen readers; the toolbar's status says "Searching…".
        <div className={styles.list} data-testid="results-loading">
          {Array.from({ length: SKELETON_COUNT }, (_, index) => (
            <ProviderCardSkeleton key={index} />
          ))}
        </div>
      )}

      {results.error && (
        <ErrorState title="Couldn't load results" error={results.error} onRetry={results.retry} />
      )}

      {data && data.total === 0 && (
        <EmptyState title="No providers match your search">
          <p>Try loosening it:</p>
          <ul className={styles.suggestions}>
            {suggestions(criteria).map((suggestion) => (
              <li key={suggestion}>{suggestion}</li>
            ))}
          </ul>
          <Link to={changeSearchTo}>Change search</Link>
        </EmptyState>
      )}

      {data && data.total > 0 && data.items.length === 0 && (
        // A page past the end, e.g. from an old link.
        <EmptyState title={`There's no page ${data.page}`}>
          <button type="button" className={styles.linkButton} onClick={() => changePage(1)}>
            Go to the first page
          </button>
        </EmptyState>
      )}

      {data && data.items.length > 0 && (
        <>
          <ScoreLegend weights={data.weights_used} />
          <ol className={styles.list} aria-label="Providers">
            {data.items.map((result) => (
              <li key={result.provider.id}>
                <ProviderCard
                  result={result}
                  to={`/providers/${result.provider.id}?${detailQuery}`}
                />
              </li>
            ))}
          </ol>
          <Pagination page={data.page} totalPages={data.total_pages} onPageChange={changePage} />
        </>
      )}
    </div>
  )
}

/** Ways to broaden a search that found nothing, for the filters it actually has. */
function suggestions(criteria: SearchCriteria): string[] {
  const list: string[] = []
  const radius = criteria.radius_miles ?? DEFAULT_RADIUS_MILES
  if (criteria.location && radius < MAX_RADIUS_MILES) {
    list.push(`Widen the radius (currently ${radius} miles).`)
  }
  if (criteria.min_quality_score !== undefined || criteria.min_years_experience !== undefined) {
    list.push('Remove the minimum quality score or years of experience.')
  }
  if (criteria.accepting_new_patients) {
    list.push("Include providers who aren't accepting new patients.")
  }
  if (criteria.require_quality_score) list.push('Include providers without a quality score.')
  if (criteria.condition) list.push('Search without a specific condition.')
  if (criteria.location) list.push('Try another location, or search anywhere.')
  if (list.length === 0) list.push('Try a different specialty.')
  return list
}
