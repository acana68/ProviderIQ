import { useId, useState } from 'react'
import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { useSpecialties } from '../hooks/useReferenceData'
import styles from './SearchPage.module.css'

export function SearchPage() {
  const specialties = useSpecialties()
  const [specialty, setSpecialty] = useState('')
  const selectId = useId()

  return (
    <section className={styles.page}>
      <h1>ProviderIQ</h1>
      <p className={styles.lead}>
        Find and compare healthcare providers by quality, experience, cost, and distance.
      </p>

      <div className={styles.card}>
        {specialties.loading && <LoadingState label="Loading specialties…" />}
        {specialties.error && (
          <ErrorState title="Couldn't load specialties" error={specialties.error} />
        )}
        {specialties.data?.length === 0 && (
          <EmptyState title="No specialties yet">
            Seed the database with <code>python -m scripts.seed_db</code>.
          </EmptyState>
        )}
        {specialties.data && specialties.data.length > 0 && (
          <div className={styles.field}>
            <label htmlFor={selectId}>Specialty</label>
            <select
              id={selectId}
              className={styles.select}
              value={specialty}
              onChange={(event) => setSpecialty(event.target.value)}
            >
              <option value="">Any specialty</option>
              {specialties.data.map((s) => (
                <option key={s.slug} value={s.slug}>
                  {s.name} ({s.provider_count})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
    </section>
  )
}
