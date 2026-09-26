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
}

export interface ProviderScore {
  overall: number
  /** Always in COMPONENT_NAMES order; no distance entry without a location. */
  components: ScoreComponent[]
}

export interface ProviderSummary {
  id: number
  display_name: string
  specialty: SpecialtyRef
  subspecialty: string | null
  city: string
  state: string
  years_experience: number
  quality_score: number
  /** 1.0 = regional average; lower is cheaper. */
  cost_index: number
  accepting_new_patients: boolean
}

export interface ProviderDetail extends ProviderSummary {
  zip_code: string
  latitude: number
  longitude: number
  /** Annual patients. */
  patient_volume: number
  /** Fractions: 0.0464 = 4.64%. */
  complication_rate: number
  readmission_rate: number
  conditions: ConditionRef[]
}

/** GET /providers/{id} when `priority` is passed. */
export interface ScoredProviderDetail extends ProviderDetail {
  /** Rounded to 0.1 mile; null when no location was given. */
  distance_miles: number | null
  score: ProviderScore
  explanation: string
}
