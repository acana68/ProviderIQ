export type PageItem = number | 'gap'

/**
 * Compact page numbers: the first and last pages, and the current page with its
 * neighbours, with a gap where pages are skipped. A gap never hides a single page:
 * 1 2 3 4 5 rather than 1 ... 3 4 5.
 *
 * pageItems(6, 12) -> [1, 'gap', 5, 6, 7, 'gap', 12]
 */
export function pageItems(current: number, total: number): PageItem[] {
  const shown = [1, current - 1, current, current + 1, total]
    .filter((page, index, all) => page >= 1 && page <= total && all.indexOf(page) === index)
    .sort((a, b) => a - b)

  const items: PageItem[] = []
  for (const page of shown) {
    const previous = items.at(-1)
    if (typeof previous === 'number' && page - previous === 2) items.push(previous + 1)
    else if (typeof previous === 'number' && page - previous > 2) items.push('gap')
    items.push(page)
  }
  return items
}
