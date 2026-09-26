import type { ProviderScore } from '../../types/provider'
import { formatFactorValue, formatScore, formatWeight } from '../../utils/format'
import { COMPONENT_LABELS } from '../../utils/labels'
import colors from '../results/score.module.css'
import styles from './ScoreBreakdownTable.module.css'

/** Every score component: the provider's value, how it normalized, its weight, its points. */
export function ScoreBreakdownTable({ score }: { score: ProviderScore }) {
  const totalWeight = score.components.reduce((sum, c) => sum + c.weight, 0)
  return (
    <div className={styles.scroll}>
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
            <tr key={c.name}>
              <th scope="row">
                <span className={`${styles.swatch} ${colors[c.name]}`} aria-hidden="true" />
                {COMPONENT_LABELS[c.name]}
              </th>
              <td>{formatFactorValue(c)}</td>
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
    </div>
  )
}
