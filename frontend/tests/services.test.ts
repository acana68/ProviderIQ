import { describe, expect, it } from 'vitest'
import { parseQuery } from '../src/services/aiApi'
import { search } from '../src/services/searchApi'
import type { ParseQueryResponse, SearchResponse } from '../src/types/search'
import { jsonResponse, mockFetch } from './utils'

describe('parseQuery', () => {
  it('posts the query to /ai/parse-query', async () => {
    const response: ParseQueryResponse = {
      criteria: {
        specialty: 'cardiology',
        condition: null,
        location: null,
        radius_miles: null,
        min_quality_score: null,
        min_years_experience: null,
        accepting_new_patients: null,
        priority: 'quality',
      },
      parser_used: 'llm',
      warnings: [],
    }
    const fetchSpy = mockFetch().mockResolvedValue(jsonResponse(response))

    await expect(parseQuery('a good cardiologist')).resolves.toEqual(response)

    const [url, init] = fetchSpy.mock.calls[0]!
    expect(url).toBe('/api/v1/ai/parse-query')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe('{"query":"a good cardiologist"}')
  })
})

describe('search', () => {
  it('posts the request to /search', async () => {
    const response: SearchResponse = {
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
      total_pages: 0,
      priority: 'balanced',
      sort: 'match',
      weights_used: { quality: 0.4, experience: 0.2, cost: 0.2, volume: 0.2 },
    }
    const fetchSpy = mockFetch().mockResolvedValue(jsonResponse(response))

    await expect(
      search({ specialty: 'cardiology', location: { city: 'Chicago', state: 'IL' } }),
    ).resolves.toEqual(response)

    const [url, init] = fetchSpy.mock.calls[0]!
    expect(url).toBe('/api/v1/search')
    expect(init?.method).toBe('POST')
    expect(JSON.parse(init?.body as string)).toEqual({
      specialty: 'cardiology',
      location: { city: 'Chicago', state: 'IL' },
    })
  })
})
