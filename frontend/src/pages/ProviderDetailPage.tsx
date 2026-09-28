import { useId } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router'
import { ErrorState } from '../components/common/ErrorState'
import { ScoreBreakdownTable } from '../components/provider/ScoreBreakdownTable'
import { ScoreBar } from '../components/results/ScoreBar'
import { PriorityControl } from '../components/search/PriorityControl'
import { useDataset } from '../hooks/useDataset'
import { useProvider } from '../hooks/useProvider'
import { isScored, type ScoreContext } from '../services/providerApi'
import type { ProviderDetail, ScoredProviderDetail } from '../types/provider'
import { DEFAULT_RADIUS_MILES, type Priority } from '../types/search'
import {
  NOT_PUBLISHED,
  NOT_REPORTED,
  formatCostVsAverage,
  formatDistance,
  formatRate,
  formatScore,
  formatSpendingVsPeers,
  pluralize,
} from '../utils/format'
import { resultsUrlFrom } from '../utils/navigation'
import { scoreContextParams, searchParamsToCriteria } from '../utils/searchParams'
import styles from './ProviderDetailPage.module.css'

/** The API's upper bound on provider ids (a 32-bit integer). */
const MAX_PROVIDER_ID = 2 ** 31 - 1

export function ProviderDetailPage() {
  const { providerId } = useParams<{ providerId: string }>()
  const id = parseProviderId(providerId)
  if (id === null) return <ProviderNotFound />
  // Keyed by id: another provider starts fresh, without the last one's data.
  return <ProviderDetailView key={id} id={id} />
}

/** A positive integer the API could hold, or null: nothing else can be a provider id. */
function parseProviderId(value: string | undefined): number | null {
  if (!value || !/^\d+$/.test(value)) return null
  const id = Number(value)
  return id >= 1 && id <= MAX_PROVIDER_ID ? id : null
}

function ProviderDetailView({ id }: { id: number }) {
  const [params, setParams] = useSearchParams()
  const location = useLocation()
  const context = scoreContextFromUrl(params)
  const provider = useProvider(id, context)
  // While a priority change refetches, keep showing the provider (dimmed) instead of a
  // skeleton, so the breakdown visibly changes rather than disappearing.
  const shown = provider.data ?? (provider.loading ? provider.previous : null)

  if (provider.error?.status === 404) return <ProviderNotFound />

  function changePriority(priority: Priority) {
    if (!context) return
    // Replace, and keep the router state: Back still goes to the results.
    setParams(scoreContextParams({ ...context, priority }), {
      replace: true,
      state: location.state,
    })
  }

  return (
    <div className={styles.page}>
      <title>{shown ? `${shown.display_name} · ProviderIQ` : 'Provider · ProviderIQ'}</title>
      <BackLink />

      {provider.error && (
        <ErrorState
          title="Couldn't load this provider"
          error={provider.error}
          onRetry={provider.retry}
        />
      )}

      {!shown && provider.loading && <DetailSkeleton />}

      {shown && (
        <>
          <ProviderHeader provider={shown} />
          {context && isScored(shown) ? (
            <MatchScore
              provider={shown}
              context={context}
              updating={provider.loading}
              onPriorityChange={changePriority}
            />
          ) : (
            <section className={styles.card}>
              <p className={styles.hint}>
                Scores depend on what you're looking for. Run a search to see this provider's match
                score.
              </p>
              <Link to="/">Start a search</Link>
            </section>
          )}
          <Metrics provider={shown} />
          <Conditions provider={shown} />
        </>
      )}
    </div>
  )
}

/**
 * The score context in the page URL (the ProviderCard link sets it). Parsed like any
 * search URL, so invalid values are dropped. No priority means no context: nothing is sent.
 */
function scoreContextFromUrl(params: URLSearchParams): ScoreContext | null {
  const criteria = searchParamsToCriteria(params)
  if (!criteria.priority) return null
  return {
    priority: criteria.priority,
    location: criteria.location,
    radius_miles: criteria.radius_miles,
  }
}

/** "← Back to results" to the exact results URL the user came from, else a new search. */
function BackLink() {
  const location = useLocation()
  const resultsUrl = resultsUrlFrom(location.state)
  return (
    <Link to={resultsUrl ?? '/'} className={styles.back}>
      <span aria-hidden="true">← </span>
      {resultsUrl ? 'Back to results' : 'New search'}
    </Link>
  )
}

function ProviderNotFound() {
  return (
    <div className={styles.page}>
      <title>Provider not found · ProviderIQ</title>
      <BackLink />
      <section className={styles.card}>
        <h1 className={styles.notFoundTitle}>Provider not found</h1>
        <p className={styles.hint}>
          There's no provider with that ID. The link may be mistyped or out of date.
        </p>
      </section>
    </div>
  )
}

function ProviderHeader({ provider }: { provider: ProviderDetail | ScoredProviderDetail }) {
  const distance = isScored(provider) ? provider.distance_miles : null
  return (
    <header className={`${styles.card} ${styles.header}`}>
      <h1 className={styles.name}>{provider.display_name}</h1>
      <p className={styles.meta}>
        {provider.specialty.name}
        {provider.subspecialty && ` · ${provider.subspecialty}`}
      </p>
      <p className={styles.meta}>
        {provider.city}, {provider.state}
        {distance !== null && ` · ${formatDistance(distance)}`}
      </p>
      {provider.accepting_new_patients && (
        <span className={styles.badge}>Accepting new patients</span>
      )}
    </header>
  )
}

interface MatchScoreProps {
  provider: ScoredProviderDetail
  context: ScoreContext
  /** A new priority's score is loading; the one shown is the previous one. */
  updating: boolean
  onPriorityChange: (priority: Priority) => void
}

function MatchScore({ provider, context, updating, onPriorityChange }: MatchScoreProps) {
  const headingId = useId()
  const { labels, peerNoun } = useDataset()
  const where = context.location
    ? `near ${context.location.city}, ${context.location.state} within ${
        context.radius_miles ?? DEFAULT_RADIUS_MILES
      } mi`
    : 'no location'

  return (
    <section
      className={`${styles.card} ${styles.score}`}
      aria-labelledby={headingId}
      aria-busy={updating}
    >
      <h2 id={headingId} className={styles.sectionTitle}>
        Match score
      </h2>
      <div className={styles.scoreSummary}>
        <p className={styles.overall}>
          <span className={styles.overallNumber}>{formatScore(provider.score.overall)}</span>
          <span className={styles.overallMax}>/100</span>
        </p>
        <div className={styles.scoreText}>
          <p className={styles.explanation}>{provider.explanation}</p>
          <p className={styles.context}>
            Scored for {labels.priorities[context.priority]} priority · {where}
          </p>
        </div>
      </div>

      <PriorityControl
        value={context.priority}
        hasLocation={context.location !== undefined}
        onChange={onPriorityChange}
      />
      <p className="visually-hidden" role="status" aria-live="polite">
        {updating ? 'Updating the score…' : ''}
      </p>

      <div className={updating ? styles.updating : undefined}>
        <ScoreBar score={provider.score} />
        <ScoreBreakdownTable
          score={provider.score}
          provider={{ data_source: provider.data_source, peers: peerNoun(provider.specialty) }}
        />
      </div>
      <p className={styles.footnote}>
        Points = normalized × weight × 100. Totals may differ by 0.1 due to rounding.{' '}
        <Link to="/methodology">How scoring works</Link>
      </p>
    </section>
  )
}

function Metrics({ provider }: { provider: ProviderDetail | ScoredProviderDetail }) {
  const headingId = useId()
  const { labels, peerNoun } = useDataset()
  const { metrics } = labels
  const rows: [string, string, string?][] = [
    [
      metrics.quality_score,
      provider.quality_score === null
        ? NOT_REPORTED
        : `${formatScore(provider.quality_score)} / 100`,
    ],
    [
      metrics.years_experience,
      provider.years_experience === null
        ? NOT_REPORTED
        : pluralize(provider.years_experience, 'year'),
    ],
    [metrics.cost_index, costText(provider, peerNoun(provider.specialty))],
    [metrics.patient_volume, pluralize(provider.patient_volume, 'patient')],
    rateRow(metrics.complication_rate, provider, provider.complication_rate),
    rateRow(metrics.readmission_rate, provider, provider.readmission_rate),
    ...(provider.npi ? [['NPI', provider.npi] as [string, string]] : []),
    ['ZIP code', provider.zip_code],
  ]
  return (
    <section className={styles.card} aria-labelledby={headingId}>
      <h2 id={headingId} className={styles.sectionTitle}>
        Metrics
      </h2>
      <dl className={styles.metrics}>
        {rows.map(([term, value, note]) => (
          <div key={term}>
            <dt>{term}</dt>
            <dd>
              {value}
              {note && <span className={styles.note}> ({note})</span>}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

/**
 * Synthetic cost vs the regional average. CMS spending is scored as a percentile within the
 * specialty, which only a score carries (its cost component), so without one there's no
 * peer comparison to show.
 */
function costText(provider: ProviderDetail | ScoredProviderDetail, peers: string): string {
  if (provider.cost_index === null) return NOT_REPORTED
  if (provider.data_source !== 'cms') return formatCostVsAverage(provider.cost_index)
  const cost = isScored(provider)
    ? provider.score.components.find((c) => c.name === 'cost')
    : undefined
  if (!cost) return 'Run a search to compare with peers'
  if (cost.imputed) return NOT_REPORTED
  return formatSpendingVsPeers(cost.normalized, peers)
}

/** A rate, or why there isn't one: CMS doesn't publish these per clinician. */
function rateRow(
  label: string,
  provider: ProviderDetail,
  rate: number | null,
): [string, string, string?] {
  if (rate !== null) return [label, formatRate(rate), 'lower is better']
  return [label, provider.data_source === 'cms' ? NOT_PUBLISHED : NOT_REPORTED]
}

function Conditions({ provider }: { provider: ProviderDetail }) {
  const headingId = useId()
  return (
    <section className={styles.card} aria-labelledby={headingId}>
      <h2 id={headingId} className={styles.sectionTitle}>
        Conditions treated
      </h2>
      {provider.conditions.length > 0 ? (
        <ul className={styles.chips}>
          {provider.conditions.map((condition) => (
            <li key={condition.slug} className={styles.chip}>
              {condition.name}
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.hint}>
          {provider.data_source === 'cms' ? `${NOT_PUBLISHED}.` : 'None listed.'}
        </p>
      )}
    </section>
  )
}

function DetailSkeleton() {
  return (
    <div className={styles.skeleton} data-testid="provider-loading" aria-hidden="true">
      <div className={styles.card}>
        <span className={styles.line} style={{ width: '45%', height: '1.75rem' }} />
        <span className={styles.line} style={{ width: '30%' }} />
        <span className={styles.line} style={{ width: '25%' }} />
      </div>
      <div className={styles.card}>
        <span className={styles.line} style={{ width: '5rem', height: '2.5rem' }} />
        <span className={styles.line} style={{ width: '80%' }} />
        <span className={styles.line} style={{ width: '100%', height: '0.5rem' }} />
      </div>
    </div>
  )
}
