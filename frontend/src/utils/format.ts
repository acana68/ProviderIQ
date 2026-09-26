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

/** "1 provider", "1,204 providers". */
export function pluralize(count: number, noun: string): string {
  return `${count.toLocaleString('en-US')} ${noun}${count === 1 ? '' : 's'}`
}
