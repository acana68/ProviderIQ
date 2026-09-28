import { useId } from 'react'
import { Link, useLocation } from 'react-router'
import { useDataset } from '../../hooks/useDataset'
import type { ProviderSummary } from '../../types/provider'
import type { SearchResult } from '../../types/search'
import {
  NOT_REPORTED,
  formatCostVsAverage,
  formatDistance,
  formatScore,
  formatSpendingVsPeers,
  pluralize,
} from '../../utils/format'
import { backState } from '../../utils/navigation'
import styles from './ProviderCard.module.css'
import { ScoreBar } from './ScoreBar'

interface ProviderCardProps {
  result: SearchResult
  /** The provider's detail page, with the search context so it shows the same score. */
  to: string
}

/**
 * One search result. The name is the link, stretched over the whole card, so the card is
 * clickable while screen readers still hear a short link name.
 */
export function ProviderCard({ result, to }: ProviderCardProps) {
  const { provider, score, distance_miles, explanation } = result
  const { labels, peerNoun } = useDataset()
  const headingId = useId()
  // The detail page's back link returns here, with the same sort and page.
  const { pathname, search } = useLocation()

  return (
    <article className={styles.card} aria-labelledby={headingId}>
      <header className={styles.header}>
        <h2 id={headingId} className={styles.name}>
          <Link to={to} state={backState(pathname + search)} className={styles.link}>
            {provider.display_name}
          </Link>
        </h2>
        <p className={styles.meta}>
          {provider.specialty.name}
          {provider.subspecialty && ` · ${provider.subspecialty}`}
        </p>
        <p className={styles.meta}>
          {provider.city}, {provider.state}
          {distance_miles !== null && ` · ${formatDistance(distance_miles)}`}
        </p>
        {provider.accepting_new_patients && (
          <span className={styles.badge}>Accepting new patients</span>
        )}
      </header>

      <div className={styles.score}>
        <p className={styles.scoreValue}>
          <span className={styles.scoreNumber}>{formatScore(score.overall)}</span>
          <span className={styles.scoreMax}>/100</span>
        </p>
        <p className={styles.scoreLabel}>Match score</p>
      </div>

      <div className={styles.body}>
        <dl className={styles.facts}>
          <div>
            <dt>{labels.card.quality_score}</dt>
            <dd>
              {provider.quality_score === null ? NOT_REPORTED : formatScore(provider.quality_score)}
            </dd>
          </div>
          <div>
            <dt>{labels.card.years_experience}</dt>
            <dd>
              {provider.years_experience === null
                ? NOT_REPORTED
                : pluralize(provider.years_experience, 'year')}
            </dd>
          </div>
          <div>
            <dt>{labels.card.cost_index}</dt>
            <dd>{costText(provider, score, peerNoun(provider.specialty))}</dd>
          </div>
        </dl>
        <p className={styles.explanation}>{explanation}</p>
      </div>

      <div className={styles.bar}>
        <ScoreBar score={score} />
      </div>
    </article>
  )
}

/**
 * Synthetic cost vs the regional average. CMS spending is scored as a percentile within
 * the specialty, which the score's cost component carries, so it's a peer comparison.
 */
function costText(provider: ProviderSummary, score: SearchResult['score'], peers: string): string {
  if (provider.cost_index === null) return NOT_REPORTED
  if (provider.data_source !== 'cms') return formatCostVsAverage(provider.cost_index)
  const cost = score.components.find((c) => c.name === 'cost')
  if (!cost || cost.imputed) return NOT_REPORTED
  return formatSpendingVsPeers(cost.normalized, peers)
}

/** A placeholder card while results load. Hidden from screen readers (the toolbar announces it). */
export function ProviderCardSkeleton() {
  return (
    <div className={`${styles.card} ${styles.skeleton}`} aria-hidden="true">
      <div className={styles.header}>
        <span className={styles.line} style={{ width: '40%', height: '1.25rem' }} />
        <span className={styles.line} style={{ width: '25%' }} />
        <span className={styles.line} style={{ width: '30%' }} />
      </div>
      <div className={styles.score}>
        <span className={styles.line} style={{ width: '4rem', height: '2rem' }} />
      </div>
      <div className={styles.body}>
        <span className={styles.line} style={{ width: '60%' }} />
        <span className={styles.line} style={{ width: '90%' }} />
      </div>
      <div className={styles.bar}>
        <span className={styles.line} style={{ width: '100%', height: '0.5rem' }} />
      </div>
    </div>
  )
}
