import type { ProviderScore } from '../../types/provider'
import { formatScore } from '../../utils/format'
import { COMPONENT_LABELS } from '../../utils/labels'
import styles from './ScoreBar.module.css'
import colors from './score.module.css'

/**
 * The overall score as one stacked bar: each component's segment is its contribution out
 * of 100, so the filled length is the overall score. The bar is an image to screen
 * readers, labelled with every contribution.
 */
export function ScoreBar({ score }: { score: ProviderScore }) {
  const parts = score.components.map(
    (c) => `${COMPONENT_LABELS[c.name]} ${formatScore(c.contribution)}`,
  )
  const label = `Score breakdown, ${formatScore(score.overall)} out of 100: ${parts.join(', ')}`

  return (
    <div className={styles.track} role="img" aria-label={label}>
      {score.components.map((c) => (
        <span
          key={c.name}
          className={`${styles.segment} ${colors[c.name]}`}
          style={{ width: `${Math.max(0, c.contribution)}%` }}
          data-component={c.name}
        />
      ))}
    </div>
  )
}
