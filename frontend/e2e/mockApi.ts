import type { Page, Route } from '@playwright/test'
import type { ParseQueryResponse } from '../src/types/search'
import type { ApiFixture } from './fixtures'

/** Queries the fake parser flags as a crisis, as the backend's keyword check would. */
const CRISIS_WORDS = /hurt myself|kill myself|suicid/i

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

/**
 * Answers every /api/v1 request from a fixture, so the checks need no backend. Anything
 * the fixture doesn't cover gets a 500 and is recorded in the returned list, which a test
 * should expect to stay empty.
 */
export async function mockApi(page: Page, api: ApiFixture): Promise<string[]> {
  const unexpected: string[] = []
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace('/api/v1', '')
    const key = `${request.method()} ${path}`

    if (key === 'GET /dataset') return json(route, api.dataset)
    if (key === 'GET /specialties') return json(route, api.specialties)
    if (key === 'GET /conditions') {
      return json(route, api.conditions(url.searchParams.get('specialty') ?? ''))
    }
    if (key === 'GET /cities') return json(route, api.cities)
    if (key === 'GET /ranking/weights') return json(route, api.weights)
    if (key === 'POST /search') {
      const body = request.postDataJSON() as { page?: number }
      return json(route, { ...api.search, page: body.page ?? 1 })
    }
    const provider = /^GET \/providers\/(\d+)$/.exec(key)
    if (provider) {
      const detail = api.details.get(Number(provider[1]))
      if (!detail) {
        return json(
          route,
          { error: { code: 'NOT_FOUND', message: 'Provider not found', request_id: 'e2e' } },
          404,
        )
      }
      return json(route, url.searchParams.has('priority') ? detail.scored : detail.plain)
    }
    if (key === 'POST /ai/parse-query') {
      const { query } = request.postDataJSON() as { query: string }
      const response: ParseQueryResponse = {
        criteria: {
          specialty: 'cardiology',
          condition: null,
          location: api.cities[0] ?? null,
          radius_miles: null,
          min_quality_score: null,
          min_years_experience: null,
          accepting_new_patients: null,
          priority: 'quality',
        },
        parser_used: 'rule_based',
        warnings: ['Inferred the specialty (Cardiology) from the description you typed.'],
        crisis: CRISIS_WORDS.test(query),
      }
      return json(route, response)
    }

    unexpected.push(key)
    return json(route, { error: { code: 'E2E', message: key, request_id: null } }, 500)
  })
  return unexpected
}
