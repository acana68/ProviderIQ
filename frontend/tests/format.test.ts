import { describe, expect, it } from 'vitest'
import {
  formatCostVsAverage,
  formatDistance,
  formatFactorValue,
  formatOrdinal,
  formatRate,
  formatScore,
  formatWeight,
  pluralize,
} from '../src/utils/format'
import type { ComponentName } from '../src/types/provider'
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
    expect(formatFactorValue({ name, raw, normalized: 0, weight: 0, contribution: 0 })).toBe(text)
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
