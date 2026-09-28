import type { DataSource, ScoreComponent } from '../types/provider'

/** What a missing value shows: never 0, blank or "NaN". */
export const NOT_REPORTED = 'Not reported'
/** Complication and readmission rates in the CMS data: CMS doesn't publish them per clinician. */
export const NOT_PUBLISHED = 'Not published for individual clinicians'

/** A score on 0-100 with one decimal, e.g. "82.4". */
export function formatScore(value: number): string {
  return value.toFixed(1)
}

/** "6.2 mi away". The API already rounds distances to 0.1 mile. */
export function formatDistance(miles: number): string {
  return `${miles.toFixed(1)} mi away`
}

/** cost_index (1.0 = regional average) as words: 0.88 -> "12% below average". */
export function formatCostVsAverage(costIndex: number): string {
  const percent = Math.round(Math.abs(1 - costIndex) * 100)
  if (percent === 0) return 'About average'
  return `${percent}% ${costIndex < 1 ? 'below' : 'above'} average`
}

/**
 * CMS spending per patient as a peer comparison, from its percentile (the share of the
 * specialty that spends more) and the specialty's peer noun (useDataset().peerNoun):
 * 0.85 -> "Lower than 85% of cardiologists", 0.1 -> "Higher than 90% of cardiologists".
 * Rounded down, like the explanations, so it never overstates.
 */
export function formatSpendingVsPeers(percentile: number, peers: string): string {
  if (percentile >= 0.5) return `Lower than ${floorPercent(percentile)}% of ${peers}`
  return `Higher than ${floorPercent(1 - percentile)}% of ${peers}`
}

/** The epsilon stops float error turning 0.29 * 100 = 28.999... into 28. */
function floorPercent(fraction: number): number {
  return Math.floor(fraction * 100 + 1e-9)
}

/** "1 provider", "1,204 providers". */
export function pluralize(count: number, noun: string): string {
  return `${count.toLocaleString('en-US')} ${noun}${count === 1 ? '' : 's'}`
}

const ORDINAL_SUFFIXES: Record<number, string> = { 1: 'st', 2: 'nd', 3: 'rd' }

/** 1 -> "1st", 22 -> "22nd", 13 -> "13th", 96 -> "96th". */
export function formatOrdinal(n: number): string {
  const lastTwo = n % 100
  if (lastTwo >= 11 && lastTwo <= 13) return `${n}th`
  return `${n}${ORDINAL_SUFFIXES[n % 10] ?? 'th'}`
}

/** A fraction as a percentage with one decimal: 0.0464 -> "4.6%". */
export function formatRate(fraction: number): string {
  return `${(fraction * 100).toFixed(1)}%`
}

/** A weight as a percentage, with a decimal only when needed: 0.35 -> "35%", 0.6111 -> "61.1%". */
export function formatWeight(weight: number): string {
  return `${Number((weight * 100).toFixed(1))}%`
}

/** Whose score a component belongs to: what its values mean depends on the dataset. */
export interface FactorContext {
  data_source: DataSource
  /** The specialty's peer noun, e.g. "cardiologists". */
  peers: string
}

/**
 * A component's value in its own terms, as the breakdown table shows it. An imputed value
 * isn't the provider's, so it's "Not reported". CMS spending is scored as a percentile, so
 * it's shown as a peer comparison rather than a percentage of the median.
 */
export function formatFactorValue(component: ScoreComponent, context?: FactorContext): string {
  const { name, raw } = component
  if (component.imputed) return NOT_REPORTED
  switch (name) {
    case 'quality':
      return `${formatScore(raw)} / 100`
    case 'experience':
      return pluralize(Math.round(raw), 'year')
    case 'cost':
      return context?.data_source === 'cms'
        ? formatSpendingVsPeers(component.normalized, context.peers)
        : formatCostVsAverage(raw)
    case 'volume':
      // Rounded down, like the explanations, so it never overstates.
      return `${formatOrdinal(floorPercent(raw))} percentile in specialty`
    case 'distance':
      return `${raw.toFixed(1)} mi`
  }
}
