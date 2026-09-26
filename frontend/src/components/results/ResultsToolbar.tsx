import { useId } from 'react'
import { SORT_OPTIONS, type Priority, type SortOption } from '../../types/search'
import { pluralize } from '../../utils/format'
import { SORT_LABELS } from '../../utils/labels'
import { PriorityControl } from '../search/PriorityControl'
import styles from './ResultsToolbar.module.css'

interface ResultsToolbarProps {
  /** Null until the first response (or after an error). */
  total: number | null
  loading: boolean
  sort: SortOption
  priority: Priority
  hasLocation: boolean
  onSortChange: (sort: SortOption) => void
  onPriorityChange: (priority: Priority) => void
}

/** Result count plus the sort and priority controls. Distance needs a location in both. */
export function ResultsToolbar({
  total,
  loading,
  sort,
  priority,
  hasLocation,
  onSortChange,
  onPriorityChange,
}: ResultsToolbarProps) {
  const sortId = useId()
  let count = ''
  if (loading) count = 'Searching…'
  else if (total !== null) count = `${pluralize(total, 'provider')} found`

  return (
    <div className={styles.toolbar}>
      <p className={styles.count} role="status" aria-live="polite">
        {count}
      </p>
      <div className={styles.controls}>
        <div className={styles.sort}>
          <label htmlFor={sortId} className={styles.label}>
            Sort by
          </label>
          <select
            id={sortId}
            className={styles.select}
            value={sort}
            onChange={(event) => onSortChange(event.target.value as SortOption)}
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option} value={option} disabled={option === 'distance' && !hasLocation}>
                {SORT_LABELS[option]}
                {option === 'distance' && !hasLocation ? ' (needs a location)' : ''}
              </option>
            ))}
          </select>
        </div>
        <PriorityControl
          value={priority}
          hasLocation={hasLocation}
          onChange={onPriorityChange}
          compact
        />
      </div>
    </div>
  )
}
