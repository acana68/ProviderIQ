import { useId } from 'react'
import { useDataset } from '../../hooks/useDataset'
import { PRIORITIES, type Priority } from '../../types/search'
import styles from './PriorityControl.module.css'

interface PriorityControlProps {
  value: Priority
  onChange: (priority: Priority) => void
  /** Distance can only be chosen with a location. */
  hasLocation: boolean
  /** Keep the "needs a location" hint for screen readers only (it's also a tooltip). */
  compact?: boolean
}

/** Segmented control for the ranking priority: radio buttons, so arrow keys move between them. */
export function PriorityControl({
  value,
  onChange,
  hasLocation,
  compact = false,
}: PriorityControlProps) {
  const id = useId()
  const { labels } = useDataset()
  const hintId = `${id}-hint`
  return (
    <fieldset className={styles.priority}>
      <legend className={styles.legend}>Priority</legend>
      <div className={styles.segments}>
        {PRIORITIES.map((option) => {
          const disabled = option === 'distance' && !hasLocation
          // A short button label (CMS: "Spending") carries the full metric name as its
          // tooltip and accessible name.
          const fullName = labels.priorityNames?.[option]
          const named = fullName !== undefined && fullName !== labels.priorities[option]
          return (
            <label
              key={option}
              className={styles.segment}
              title={
                disabled
                  ? 'Choose a location to prioritize distance.'
                  : named
                    ? fullName
                    : undefined
              }
            >
              <input
                type="radio"
                className="visually-hidden"
                name={`${id}-priority`}
                value={option}
                checked={value === option}
                disabled={disabled}
                aria-label={named ? fullName : undefined}
                aria-describedby={disabled ? hintId : undefined}
                onChange={() => onChange(option)}
              />
              {labels.priorities[option]}
            </label>
          )
        })}
      </div>
      {!hasLocation && (
        <p id={hintId} className={compact ? 'visually-hidden' : styles.hint}>
          Distance needs a location.
        </p>
      )}
    </fieldset>
  )
}
