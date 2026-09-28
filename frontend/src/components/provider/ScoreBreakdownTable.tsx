import { useDataset } from '../../hooks/useDataset'
import type { ProviderScore } from '../../types/provider'
import {
  type FactorContext,
  formatFactorValue,
  formatScore,
  formatWeight,
} from '../../utils/format'
import { TableScroll } from '../common/TableScroll'
import colors from '../results/score.module.css'
import styles from './ScoreBreakdownTable.module.css'

interface ScoreBreakdownTableProps {
  score: ProviderScore
  /** Whose score it is: CMS spending reads as a peer comparison. */
  provider?: FactorContext
}

/**
 * Every score component: the provider's value, how it normalized, its weight, its points.
 * A value the provider doesn't have (imputed) says so, and is marked, with a legend.
 */
export function ScoreBreakdownTable({ score, provider }: ScoreBreakdownTableProps) {
  const { labels } = useDataset()
  const totalWeight = score.components.reduce((sum, c) => sum + c.weight, 0)
  const anyImputed = score.components.some((c) => c.imputed)
  return (
    <>
      <TableScroll label="Score breakdown" className={styles.scroll}>
        <table className={styles.table}>
          <caption className="visually-hidden">Score breakdown</caption>
          <thead>
            <tr>
              <th scope="col">Factor</th>
              <th scope="col">Value</th>
              <th scope="col" className={styles.number}>
                Normalized
              </th>
              <th scope="col" className={styles.number}>
                Weight
              </th>
              <th scope="col" className={styles.number}>
                Points
              </th>
            </tr>
          </thead>
          <tbody>
            {score.components.map((c) => (
              <tr
                key={c.name}
                className={c.imputed ? styles.imputed : undefined}
                data-imputed={c.imputed || undefined}
              >
                <th scope="row">
                  <span className={`${styles.swatch} ${colors[c.name]}`} aria-hidden="true" />
                  {labels.components[c.name]}
                  {c.imputed && (
                    <span className={styles.marker} aria-hidden="true">
                      *
                    </span>
                  )}
                </th>
                <td>
                  {formatFactorValue(c, provider)}
                  {c.imputed && <span className={styles.note}> (scored as specialty median)</span>}
                </td>
                <td className={styles.number}>{c.normalized.toFixed(2)}</td>
                <td className={styles.number}>{formatWeight(c.weight)}</td>
                <td className={styles.number}>{formatScore(c.contribution)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">Total</th>
              <td />
              <td />
              <td className={styles.number}>{formatWeight(totalWeight)}</td>
              <td className={styles.number}>{formatScore(score.overall)}</td>
            </tr>
          </tfoot>
        </table>
      </TableScroll>
      {anyImputed && (
        <p className={styles.legend}>
          <span className={styles.marker} aria-hidden="true">
            *
          </span>{' '}
          Not reported for this provider: scored as the median of their specialty, so it neither
          helps nor hurts.
        </p>
      )}
    </>
  )
}
