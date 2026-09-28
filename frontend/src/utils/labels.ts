import type { DatasetInfo } from '../types/dataset'
import type { ComponentName } from '../types/provider'
import type { ParserUsed, Priority, SortOption } from '../types/search'

export const PRIORITY_LABELS: Record<Priority, string> = {
  balanced: 'Balanced',
  quality: 'Quality',
  cost: 'Cost',
  experience: 'Experience',
  distance: 'Distance',
}

export const SORT_LABELS: Record<SortOption, string> = {
  match: 'Best match',
  quality: 'Quality',
  experience: 'Experience',
  distance: 'Distance',
  cost: 'Cost',
}

export const COMPONENT_LABELS: Record<ComponentName, string> = {
  quality: 'Quality',
  experience: 'Experience',
  cost: 'Cost',
  volume: 'Volume',
  distance: 'Distance',
}

export const PARSER_LABELS: Record<ParserUsed, string> = {
  llm: 'AI',
  rule_based: 'keyword matching',
}

/** Every name the UI gives a metric. Depends on the dataset: see labelsFor(). */
export interface Labels {
  /** Score components: breakdown table, legend, score bar, weights table. */
  components: Record<ComponentName, string>
  /** Short, for the priority buttons. */
  priorities: Record<Priority, string>
  /**
   * The full metric names behind the priority buttons, for their tooltip and accessible
   * name. Null when the buttons already say it all (synthetic).
   */
  priorityNames: Record<Priority, string> | null
  sorts: Record<SortOption, string>
  /** The provider detail page's metrics. */
  metrics: {
    quality_score: string
    years_experience: string
    cost_index: string
    patient_volume: string
    complication_rate: string
    readmission_rate: string
  }
  /** The shorter names on a result card. */
  card: { quality_score: string; years_experience: string; cost_index: string }
  /** Search filters. */
  minQuality: string
  minExperience: string
}

/** The synthetic dataset's labels: the ones the app has always used. */
export const SYNTHETIC_LABELS: Labels = {
  components: COMPONENT_LABELS,
  priorities: PRIORITY_LABELS,
  priorityNames: null,
  sorts: SORT_LABELS,
  metrics: {
    quality_score: 'Quality score',
    years_experience: 'Years of experience',
    cost_index: 'Cost',
    patient_volume: 'Annual patient volume',
    complication_rate: 'Complication rate',
    readmission_rate: 'Readmission rate',
  },
  card: { quality_score: 'Quality score', years_experience: 'Experience', cost_index: 'Cost' },
  minQuality: 'Minimum quality score',
  minExperience: 'Minimum years of experience',
}

/** Used for a CMS metric that GET /dataset didn't label (it labels all four today). */
const CMS_FALLBACK_LABELS = {
  quality_score: 'MIPS final score',
  years_experience: 'Years since medical school',
  cost_index: 'Medicare spending per patient',
  patient_volume: 'Medicare patients',
}

/**
 * Labels for a dataset. The CMS dataset's come from GET /dataset's metric_labels, so each
 * metric is named for what it really is ("Medicare spending per patient", never "Cost").
 * Anything else, including a dataset that hasn't loaded, gets the synthetic labels.
 */
export function labelsFor(dataset: DatasetInfo | null): Labels {
  if (dataset?.source !== 'cms_nj') return SYNTHETIC_LABELS
  const named = { ...CMS_FALLBACK_LABELS, ...dataset.metric_labels }
  // A missing short label falls back to the full one.
  const short = { ...named, ...dataset.metric_short_labels }
  const quality = named.quality_score
  const experience = named.years_experience
  const cost = named.cost_index
  return {
    components: { quality, experience, cost, volume: named.patient_volume, distance: 'Distance' },
    priorities: {
      balanced: 'Balanced',
      quality: short.quality_score,
      cost: short.cost_index,
      experience: short.years_experience,
      distance: 'Distance',
    },
    priorityNames: { balanced: 'Balanced', quality, cost, experience, distance: 'Distance' },
    sorts: { match: 'Best match', quality, experience, distance: 'Distance', cost },
    metrics: {
      quality_score: quality,
      years_experience: experience,
      cost_index: cost,
      patient_volume: named.patient_volume,
      complication_rate: named.complication_rate ?? 'Complication rate',
      readmission_rate: named.readmission_rate ?? 'Readmission rate',
    },
    card: { quality_score: quality, years_experience: experience, cost_index: cost },
    minQuality: `Minimum ${quality}`,
    minExperience: `Minimum ${lowerFirst(experience)}`,
  }
}

/** "Years since medical school" -> "years since medical school", but "MIPS score" stays. */
function lowerFirst(text: string): string {
  return /^[A-Z][a-z]/.test(text) ? text.charAt(0).toLowerCase() + text.slice(1) : text
}
