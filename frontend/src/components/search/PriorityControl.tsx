import { useId } from 'react'
import { PRIORITIES, type Priority } from '../../types/search'
import { PRIORITY_LABELS } from '../../utils/labels'
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
  const hintId = `${id}-hint`
  return (
    <fieldset className={styles.priority}>
      <legend className={styles.legend}>Priority</legend>
      <div className={styles.segments}>
        {PRIORITIES.map((option) => {
          const disabled = option === 'distance' && !hasLocation
          return (
            <label
              key={option}
              className={styles.segment}
              title={disabled ? 'Choose a location to prioritize distance.' : undefined}
            >
              <input
                type="radio"
                className="visually-hidden"
                name={`${id}-priority`}
                value={option}
                checked={value === option}
                disabled={disabled}
                aria-describedby={disabled ? hintId : undefined}
                onChange={() => onChange(option)}
              />
              {PRIORITY_LABELS[option]}
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
