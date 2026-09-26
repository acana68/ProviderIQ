import type { ConditionSummary, SpecialtySummary } from '../src/types/provider'
import type { Location } from '../src/types/search'
import { jsonResponse, mockFetch } from './utils'

export const SPECIALTIES: SpecialtySummary[] = [
  { id: 1, slug: 'cardiology', name: 'Cardiology', provider_count: 162 },
  { id: 3, slug: 'dermatology', name: 'Dermatology', provider_count: 134 },
]
export const CARDIOLOGY_CONDITIONS: ConditionSummary[] = [
  { id: 1, slug: 'heart-failure', name: 'Heart failure' },
  { id: 2, slug: 'atrial-fibrillation', name: 'Atrial fibrillation' },
]
export const DERMATOLOGY_CONDITIONS: ConditionSummary[] = [
  { id: 3, slug: 'psoriasis', name: 'Psoriasis' },
  { id: 4, slug: 'eczema', name: 'Eczema' },
]
export const CITIES: Location[] = [
  { city: 'Chicago', state: 'IL' },
  { city: 'New York', state: 'NY' },
]

export type Handler = (init?: RequestInit) => Response | Promise<Response>

const REFERENCE_ROUTES: Record<string, Handler> = {
  'GET /api/v1/specialties': () => jsonResponse(SPECIALTIES),
  'GET /api/v1/conditions': () =>
    jsonResponse([...CARDIOLOGY_CONDITIONS, ...DERMATOLOGY_CONDITIONS]),
  'GET /api/v1/conditions?specialty=cardiology': () => jsonResponse(CARDIOLOGY_CONDITIONS),
  'GET /api/v1/conditions?specialty=dermatology': () => jsonResponse(DERMATOLOGY_CONDITIONS),
  'GET /api/v1/cities': () => jsonResponse(CITIES),
}

/**
 * A fake API: answers by "METHOD url" (e.g. "POST /api/v1/search"), with the reference
 * data endpoints built in, and fails loudly on anything unexpected.
 */
export function routeFetch(routes: Record<string, Handler> = {}) {
  return mockFetch().mockImplementation(async (input, init) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    const handler = routes[key] ?? REFERENCE_ROUTES[key]
    if (!handler) throw new Error(`Unexpected request: ${key}`)
    return handler(init)
  })
}

/** The parsed JSON bodies of every call to one URL, in order. */
export function requestBodies(fetchSpy: ReturnType<typeof mockFetch>, url: string): unknown[] {
  return fetchSpy.mock.calls
    .filter(([input]) => String(input) === url)
    .map(([, init]) => JSON.parse(init?.body as string))
}
