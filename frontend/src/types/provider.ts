// Mirrors backend/app/schemas/reference.py, provider.py and score.py.

export interface SpecialtyRef {
  slug: string
  name: string
}

export interface ConditionRef {
  slug: string
  name: string
}

/** GET /specialties item. */
export interface SpecialtySummary {
  id: number
  slug: string
  name: string
  provider_count: number
}

/** GET /conditions item. */
export interface ConditionSummary {
  id: number
  slug: string
  name: string
}

export const COMPONENT_NAMES = ['quality', 'experience', 'cost', 'volume', 'distance'] as const
export type ComponentName = (typeof COMPONENT_NAMES)[number]

export interface ScoreComponent {
  name: ComponentName
  /** The provider's own value: quality score, years, cost index, volume percentile, miles. */
  raw: number
  /** On [0, 1], higher is better. */
  normalized: number
  /** The weight actually applied, after renormalization. */
  weight: number
  /** Points toward `overall`: 100 * weight * normalized. */
  contribution: number
  /**
   * True when the provider doesn't have this metric: `raw` is the specialty median standing
   * in for it (quality, experience and cost only).
   */
  imputed: boolean
}

export interface ProviderScore {
  overall: number
  /** Always in COMPONENT_NAMES order; no distance entry without a location. */
  components: ScoreComponent[]
}

/** Which provider dataset a row comes from. */
export type DataSource = 'synthetic' | 'cms'

/**
 * reported: the value is in the response. imputed: not published, and scores use the
 * specialty median instead (the value itself stays null). not_reported: not published, and
 * not part of any score.
 */
export type MetricStatus = 'reported' | 'imputed' | 'not_reported'

/** What each metric that can be missing means for this provider. */
export interface MetricFlags {
  quality_score: MetricStatus
  years_experience: MetricStatus
  cost_index: MetricStatus
  complication_rate: MetricStatus
  readmission_rate: MetricStatus
}

export interface ProviderSummary {
  id: number
  /** National Provider Identifier; CMS data only. */
  npi: string | null
  data_source: DataSource
  display_name: string
  specialty: SpecialtyRef
  subspecialty: string | null
  city: string
  state: string
  /** Null when not published; see metric_flags. */
  years_experience: number | null
  quality_score: number | null
  /**
   * Lower is better. Synthetic: cost, 1.0 = regional average. CMS: Medicare spending per
   * patient, 1.0 = the NJ specialty median. Null when not reported.
   */
  cost_index: number | null
  /** Null when unknown (CMS doesn't publish it). */
  accepting_new_patients: boolean | null
  metric_flags: MetricFlags
}

export interface ProviderDetail extends ProviderSummary {
  zip_code: string
  latitude: number
  longitude: number
  /** Annual patients (CMS: Medicare patients only). */
  patient_volume: number
  /** Fractions: 0.0464 = 4.64%. Null when not published (CMS never publishes them). */
  complication_rate: number | null
  readmission_rate: number | null
  conditions: ConditionRef[]
}

/** GET /providers/{id} when `priority` is passed. */
export interface ScoredProviderDetail extends ProviderDetail {
  /** Rounded to 0.1 mile; null when no location was given. */
  distance_miles: number | null
  score: ProviderScore
  explanation: string
}
