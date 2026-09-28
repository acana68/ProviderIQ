import { useDataset } from '../../hooks/useDataset'
import { COMPONENT_NAMES, type ComponentName } from '../../types/provider'
import colors from './score.module.css'
import styles from './ScoreLegend.module.css'

interface ScoreLegendProps {
  /** The search's effective weights (no distance entry without a location). */
  weights: Partial<Record<ComponentName, number>>
}

/** One legend for every card's ScoreBar: each component's color and weight. */
export function ScoreLegend({ weights }: ScoreLegendProps) {
  const { labels } = useDataset()
  const names = COMPONENT_NAMES.filter((name) => weights[name] !== undefined)
  return (
    <div className={styles.legend}>
      <span className={styles.title}>Score breakdown</span>
      <ul className={styles.items} aria-label="Score components and weights">
        {names.map((name) => (
          <li key={name} className={styles.item}>
            <span className={`${styles.swatch} ${colors[name]}`} aria-hidden="true" />
            {labels.components[name]}
            <span className={styles.weight}>{Math.round((weights[name] ?? 0) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
