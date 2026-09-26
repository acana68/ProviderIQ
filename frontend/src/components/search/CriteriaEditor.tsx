import { useEffect, useId } from 'react'
import { useCities, useConditions, useSpecialties } from '../../hooks/useReferenceData'
import {
  DEFAULT_RADIUS_MILES,
  MAX_RADIUS_MILES,
  MIN_RADIUS_MILES,
  type Location,
  type SearchCriteria,
} from '../../types/search'
import { ErrorState } from '../common/ErrorState'
import styles from './CriteriaEditor.module.css'
import { PriorityControl } from './PriorityControl'

interface CriteriaEditorProps {
  value: SearchCriteria
  onChange: (next: SearchCriteria) => void
}

/** Editable search criteria. Controlled: the parent owns `value`. */
export function CriteriaEditor({ value, onChange }: CriteriaEditorProps) {
  const specialties = useSpecialties()
  const conditions = useConditions(value.specialty)
  const cities = useCities()
  const id = useId()

  const hasLocation = value.location !== undefined
  const priority = value.priority ?? 'balanced'

  // A condition picked (or parsed) for one specialty may not be treated in another. Once
  // the new specialty's list has loaded, drop the condition if it's not in it.
  const conditionList = conditions.data
  useEffect(() => {
    if (
      conditionList &&
      value.condition &&
      !conditionList.some((c) => c.slug === value.condition)
    ) {
      onChange({ ...value, condition: undefined })
    }
  }, [conditionList, value, onChange])

  function update(changes: Partial<SearchCriteria>) {
    onChange({ ...value, ...changes })
  }

  function setLocation(key: string) {
    const location = cities.data?.find((city) => locationKey(city) === key)
    if (location) {
      update({ location, radius_miles: value.radius_miles ?? DEFAULT_RADIUS_MILES })
    } else {
      // No location: no radius, and distance can't be the priority.
      update({
        location: undefined,
        radius_miles: undefined,
        priority: priority === 'distance' ? 'balanced' : priority,
      })
    }
  }

  const loadError = specialties.error ?? conditions.error ?? cities.error

  return (
    <div className={styles.editor}>
      {loadError && <ErrorState title="Couldn't load all search options" error={loadError} />}

      <div className={styles.grid}>
        <div className={styles.field}>
          <label htmlFor={`${id}-specialty`}>Specialty</label>
          <select
            id={`${id}-specialty`}
            className={styles.control}
            value={value.specialty ?? ''}
            disabled={specialties.loading}
            onChange={(event) => update({ specialty: event.target.value || undefined })}
          >
            <option value="">{specialties.loading ? 'Loading…' : 'Any specialty'}</option>
            {specialties.data?.map((s) => (
              <option key={s.slug} value={s.slug}>
                {s.name} ({s.provider_count})
              </option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <label htmlFor={`${id}-condition`}>Condition</label>
          <select
            id={`${id}-condition`}
            className={styles.control}
            value={value.condition ?? ''}
            disabled={conditions.loading}
            onChange={(event) => update({ condition: event.target.value || undefined })}
          >
            <option value="">{conditions.loading ? 'Loading…' : 'Any condition'}</option>
            {conditions.data?.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <label htmlFor={`${id}-location`}>Location</label>
          <select
            id={`${id}-location`}
            className={styles.control}
            value={value.location ? locationKey(value.location) : ''}
            disabled={cities.loading}
            onChange={(event) => setLocation(event.target.value)}
          >
            <option value="">{cities.loading ? 'Loading…' : 'Anywhere'}</option>
            {cities.data?.map((city) => (
              <option key={locationKey(city)} value={locationKey(city)}>
                {city.city}, {city.state}
              </option>
            ))}
          </select>
        </div>

        <NumberField
          id={`${id}-radius`}
          label="Radius (miles)"
          // Empty while the user retypes it; the search then uses the default.
          value={hasLocation ? value.radius_miles : undefined}
          min={MIN_RADIUS_MILES}
          max={MAX_RADIUS_MILES}
          disabled={!hasLocation}
          placeholder={String(DEFAULT_RADIUS_MILES)}
          hint={hasLocation ? undefined : 'Choose a location to set a radius.'}
          onChange={(radius_miles) => update({ radius_miles })}
        />

        <NumberField
          id={`${id}-quality`}
          label="Minimum quality score"
          value={value.min_quality_score}
          min={0}
          max={100}
          placeholder="Any"
          onChange={(min_quality_score) => update({ min_quality_score })}
        />

        <NumberField
          id={`${id}-years`}
          label="Minimum years of experience"
          value={value.min_years_experience}
          min={0}
          max={70}
          step={1}
          placeholder="Any"
          onChange={(min_years_experience) => update({ min_years_experience })}
        />
      </div>

      <label className={styles.checkbox}>
        <input
          type="checkbox"
          checked={value.accepting_new_patients === true}
          onChange={(event) =>
            update({ accepting_new_patients: event.target.checked ? true : undefined })
          }
        />
        Accepting new patients only
      </label>

      <PriorityControl
        value={priority}
        hasLocation={hasLocation}
        onChange={(next) => update({ priority: next })}
      />
    </div>
  )
}

function locationKey(location: Location): string {
  return `${location.city}|${location.state}`
}

interface NumberFieldProps {
  id: string
  label: string
  value: number | undefined
  min: number
  max: number
  step?: number | 'any'
  disabled?: boolean
  placeholder?: string
  hint?: string
  onChange: (value: number | undefined) => void
}

/** An optional number: empty means "not set". Out-of-range values are caught by the
 * browser's own validation when the form is submitted (min/max/step). */
function NumberField({
  id,
  label,
  value,
  min,
  max,
  step = 'any',
  disabled = false,
  placeholder,
  hint,
  onChange,
}: NumberFieldProps) {
  const hintId = `${id}-hint`
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        className={styles.control}
        type="number"
        inputMode="decimal"
        min={min}
        max={max}
        step={step}
        value={value ?? ''}
        disabled={disabled}
        placeholder={placeholder}
        aria-describedby={hint ? hintId : undefined}
        onChange={(event) => {
          const next = event.target.valueAsNumber
          onChange(Number.isNaN(next) ? undefined : next)
        }}
      />
      {hint && (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      )}
    </div>
  )
}
