/**
 * Router state a link can carry so the page it opens can link back to exactly where the
 * user was, e.g. a provider card passes its results URL, with sort and page.
 */
export interface BackState {
  from: string
}

export function backState(from: string): BackState {
  return { from }
}

/**
 * The results URL to go back to, if the page was opened from results. Router state is
 * whatever history holds, so anything else is ignored.
 */
export function resultsUrlFrom(state: unknown): string | null {
  if (typeof state !== 'object' || state === null) return null
  const from = (state as { from?: unknown }).from
  return typeof from === 'string' && /^\/results(\?|$)/.test(from) ? from : null
}
