import { Link } from 'react-router'
import { useDataset } from '../../hooks/useDataset'
import styles from './DatasetBanner.module.css'

/**
 * Above every page when the data is real (CMS): the dataset's disclaimer, where the data
 * comes from, and how current it is. Nothing for synthetic data.
 */
export function DatasetBanner() {
  const { dataset, isCms } = useDataset()
  if (!isCms || !dataset) return null
  return (
    <aside className={styles.banner} aria-label="About this data">
      <p className={styles.source}>
        <strong>{dataset.label}</strong>
        {dataset.as_of && <> · Data as of {formatDate(dataset.as_of)}</>}
        {' · '}
        <Link to="/methodology#real-data">About the real data</Link>
      </p>
      <p className={styles.disclaimer}>{dataset.disclaimer}</p>
    </aside>
  )
}

/** "2026-09-26" -> "September 26, 2026". A date without a time, so read as UTC. */
function formatDate(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return isoDate
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  })
}
