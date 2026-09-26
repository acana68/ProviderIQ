import { describe, expect, it } from 'vitest'
import { formatCostVsAverage, formatDistance, formatScore, pluralize } from '../src/utils/format'
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
