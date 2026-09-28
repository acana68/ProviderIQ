import { describe, expect, it } from 'vitest'
import {
  formatCostVsAverage,
  formatDistance,
  formatFactorValue,
  formatOrdinal,
  formatRate,
  formatScore,
  formatSpendingVsPeers,
  formatWeight,
  pluralize,
} from '../src/utils/format'
import { SYNTHETIC_LABELS, labelsFor } from '../src/utils/labels'
import { CMS_DATASET, SYNTHETIC_DATASET } from './fixtures'
import type { ComponentName, ScoreComponent } from '../src/types/provider'
import type { FactorContext } from '../src/utils/format'
import { pageItems } from '../src/utils/pagination'

describe('format', () => {
  it.each([
    [0.88, '12% below average'],
    [1.15, '15% above average'],
    [1, 'About average'],
    [1.004, 'About average'],
    [0.7, '30% below average'],
  ])('cost index %s -> %s', (index, text) => {
    expect(formatCostVsAverage(index)).toBe(text)
  })

  it('formats scores, distances and counts', () => {
    expect(formatScore(82)).toBe('82.0')
    expect(formatScore(82.44)).toBe('82.4')
    expect(formatDistance(6.2)).toBe('6.2 mi away')
    expect(formatDistance(0)).toBe('0.0 mi away')
    expect(pluralize(1, 'provider')).toBe('1 provider')
    expect(pluralize(0, 'provider')).toBe('0 providers')
    expect(pluralize(1204, 'year')).toBe('1,204 years')
  })
})

describe('detail formats', () => {
  it.each([
    [1, '1st'],
    [2, '2nd'],
    [3, '3rd'],
    [4, '4th'],
    [11, '11th'],
    [12, '12th'],
    [13, '13th'],
    [21, '21st'],
    [96, '96th'],
    [100, '100th'],
    [111, '111th'],
  ])('ordinal %i -> %s', (n, text) => {
    expect(formatOrdinal(n)).toBe(text)
  })

  it('formats rates and weights', () => {
    expect(formatRate(0.0464)).toBe('4.6%')
    expect(formatRate(0)).toBe('0.0%')
    expect(formatWeight(0.35)).toBe('35%')
    expect(formatWeight(0.6111)).toBe('61.1%')
    expect(formatWeight(1)).toBe('100%')
  })

  it.each<[ComponentName, number, string]>([
    ['quality', 88.4, '88.4 / 100'],
    ['experience', 31, '31 years'],
    ['experience', 1, '1 year'],
    ['cost', 0.79, '21% below average'],
    ['volume', 0.963, '96th percentile in specialty'],
    ['volume', 0.29, '29th percentile in specialty'],
    ['distance', 6.2, '6.2 mi'],
  ])('%s %s -> %s', (name, raw, text) => {
    expect(
      formatFactorValue({ name, raw, normalized: 0, weight: 0, contribution: 0, imputed: false }),
    ).toBe(text)
  })
})

describe('pageItems', () => {
  it.each([
    [1, 1, [1]],
    [1, 3, [1, 2, 3]],
    [1, 5, [1, 2, 'gap', 5]],
    [3, 5, [1, 2, 3, 4, 5]],
    [4, 7, [1, 2, 3, 4, 5, 6, 7]],
    [4, 8, [1, 2, 3, 4, 5, 'gap', 8]],
    [6, 12, [1, 'gap', 5, 6, 7, 'gap', 12]],
    [12, 12, [1, 'gap', 11, 12]],
  ])('page %i of %i', (current, total, expected) => {
    expect(pageItems(current, total)).toEqual(expected)
  })
})

describe('formatSpendingVsPeers', () => {
  it.each([
    [0.85, 'Lower than 85% of cardiologists'],
    [0.29, 'Higher than 71% of cardiologists'],
    [0.5, 'Lower than 50% of cardiologists'],
    [1, 'Lower than 100% of cardiologists'],
    [0, 'Higher than 100% of cardiologists'],
  ])('%s -> %s', (percentile, text) => {
    expect(formatSpendingVsPeers(percentile, 'cardiologists')).toBe(text)
  })
})

describe('formatFactorValue with a dataset', () => {
  const cost: ScoreComponent = {
    name: 'cost',
    raw: 0.81,
    normalized: 0.85,
    weight: 0.2,
    contribution: 17,
    imputed: false,
  }
  const cms: FactorContext = { data_source: 'cms', peers: 'oncologists' }

  it('shows CMS spending as a peer comparison', () => {
    expect(formatFactorValue(cost, cms)).toBe('Lower than 85% of oncologists')
    expect(formatFactorValue(cost, { ...cms, data_source: 'synthetic' })).toBe('19% below average')
  })

  it('says "Not reported" for an imputed value, whatever it is', () => {
    expect(formatFactorValue({ ...cost, imputed: true }, cms)).toBe('Not reported')
    expect(formatFactorValue({ ...cost, name: 'quality', raw: 90.3, imputed: true })).toBe(
      'Not reported',
    )
  })
})

describe('labelsFor', () => {
  it('keeps the current labels for synthetic data or no dataset', () => {
    expect(labelsFor(SYNTHETIC_DATASET)).toBe(SYNTHETIC_LABELS)
    expect(labelsFor(null)).toBe(SYNTHETIC_LABELS)
    expect(SYNTHETIC_LABELS.priorityNames).toBeNull()
    expect(SYNTHETIC_LABELS.card).toEqual({
      quality_score: 'Quality score',
      years_experience: 'Experience',
      cost_index: 'Cost',
    })
  })

  it('uses the CMS metric labels from GET /dataset', () => {
    const labels = labelsFor(CMS_DATASET)

    expect(labels.components).toEqual({
      quality: 'MIPS final score',
      experience: 'Years since medical school',
      cost: 'Medicare spending per patient',
      volume: 'Medicare patients',
      distance: 'Distance',
    })
    // Short on the priority buttons, with the full names alongside.
    expect(labels.priorities).toEqual({
      balanced: 'Balanced',
      quality: 'MIPS score',
      cost: 'Spending',
      experience: 'Years in medicine',
      distance: 'Distance',
    })
    expect(labels.priorityNames?.cost).toBe('Medicare spending per patient')
    expect(labels.sorts.cost).toBe('Medicare spending per patient')
    expect(labels.minQuality).toBe('Minimum MIPS final score')
    expect(labels.minExperience).toBe('Minimum years since medical school')
  })
})
