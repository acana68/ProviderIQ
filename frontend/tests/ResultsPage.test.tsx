import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { ResultsPage } from '../src/pages/ResultsPage'
import type { SearchRequest, SearchResponse, SearchResult } from '../src/types/search'
import { type Handler, SYNTHETIC_FLAGS, requestBodies, routeFetch } from './fixtures'
import { errorBody, jsonResponse } from './utils'

const SEARCH_URL = '/api/v1/search'

function result(id: number, name: string): SearchResult {
  return {
    provider: {
      id,
      npi: null,
      data_source: 'synthetic',
      display_name: name,
      specialty: { slug: 'cardiology', name: 'Cardiology' },
      subspecialty: id === 1 ? 'Heart Failure & Transplant' : null,
      city: 'New York',
      state: 'NY',
      years_experience: 15,
      quality_score: 88.5,
      cost_index: 0.88,
      accepting_new_patients: id === 1,
      metric_flags: SYNTHETIC_FLAGS,
    },
    distance_miles: id === 1 ? 6.2 : null,
    score: {
      overall: 82.4,
      // Rounded separately, so they sum to 82.3: a rounding step off, as from the API.
      components: [
        {
          name: 'quality',
          raw: 88.5,
          normalized: 0.885,
          weight: 0.35,
          contribution: 31.1,
          imputed: false,
        },
        {
          name: 'experience',
          raw: 15,
          normalized: 0.8,
          weight: 0.2,
          contribution: 16,
          imputed: false,
        },
        {
          name: 'cost',
          raw: 0.88,
          normalized: 0.705,
          weight: 0.2,
          contribution: 14.1,
          imputed: false,
        },
        { name: 'volume', raw: 0.6, normalized: 0.6, weight: 0.1, contribution: 6, imputed: false },
        {
          name: 'distance',
          raw: 6.2,
          normalized: 1,
          weight: 0.15,
          contribution: 15.1,
          imputed: false,
        },
      ],
    },
    explanation: `${name} ranks highly for quality among cardiologists.`,
  }
}

const ALICE = result(1, 'Dr. Alice Chen')
const BOB = result(2, 'Dr. Bob Diaz')

function response(items: SearchResult[], overrides: Partial<SearchResponse> = {}): SearchResponse {
  return {
    items,
    page: 1,
    page_size: 20,
    total: items.length,
    total_pages: items.length ? 1 : 0,
    priority: 'balanced',
    sort: 'match',
    weights_used: { quality: 0.35, experience: 0.2, cost: 0.2, volume: 0.1, distance: 0.15 },
    ...overrides,
  }
}

/** The current URL, shown next to the page so tests can check what it navigated to. */
function LocationDisplay() {
  const { pathname, search } = useLocation()
  return <output aria-label="current URL">{pathname + search}</output>
}

function renderResults(path: string, search: Handler) {
  const fetchSpy = routeFetch({ [`POST ${SEARCH_URL}`]: search })
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/results" element={<ResultsPage />} />
      </Routes>
      <LocationDisplay />
    </MemoryRouter>,
  )
  return { fetchSpy, user }
}

function currentParams(): Record<string, string> {
  const url = screen.getByRole('status', { name: 'current URL' }).textContent ?? ''
  return Object.fromEntries(new URL(url, 'http://localhost').searchParams)
}

function searchBodies(fetchSpy: ReturnType<typeof routeFetch>) {
  return requestBodies(fetchSpy, SEARCH_URL) as SearchRequest[]
}

/** A search endpoint that answers every request the same way. */
const answer =
  (body: SearchResponse): Handler =>
  () =>
    jsonResponse(body)

/** A search endpoint that pages through `total` results of 20, following the requested page. */
const paged =
  (total: number): Handler =>
  (init) => {
    const { page = 1 } = JSON.parse(init?.body as string) as SearchRequest
    return jsonResponse(
      response([result(page, `Dr. Page ${page}`)], {
        page,
        total,
        total_pages: Math.ceil(total / 20),
      }),
    )
  }

/** A response that only arrives when the test says so. */
function deferred() {
  let resolve: (response: Response) => void = () => {}
  const promise = new Promise<Response>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

const card = (name: string) => screen.getByRole('article', { name })

describe('ResultsPage', () => {
  it('sends the URL criteria as the search request, including page and sort', async () => {
    const { fetchSpy } = renderResults(
      '/results?specialty=cardiology&condition=heart-failure&city=New+York&state=NY' +
        '&radius_miles=10&min_quality_score=80&min_years_experience=5' +
        '&accepting_new_patients=true&priority=quality&sort=experience&page=2' +
        '&source=nl&parser_used=llm&junk=1',
      answer(response([], { page: 2 })),
    )

    await waitFor(() => expect(searchBodies(fetchSpy)).toHaveLength(1))
    expect(searchBodies(fetchSpy)[0]).toEqual({
      specialty: 'cardiology',
      condition: 'heart-failure',
      location: { city: 'New York', state: 'NY' },
      radius_miles: 10,
      min_quality_score: 80,
      min_years_experience: 5,
      accepting_new_patients: true,
      priority: 'quality',
      sort: 'experience',
      page: 2,
      source: 'nl',
      parser_used: 'llm',
    })
  })

  it('shows skeletons while loading, then the provider cards', async () => {
    const pending = deferred()
    renderResults('/results?specialty=cardiology', () => pending.promise)

    expect(await screen.findByText('Searching…')).toBeInTheDocument()
    expect(screen.getByTestId('results-loading')).toBeInTheDocument()
    expect(screen.queryAllByRole('article')).toHaveLength(0)

    pending.resolve(jsonResponse(response([ALICE, BOB])))

    expect(await screen.findByText('2 providers found')).toBeInTheDocument()
    expect(screen.queryByTestId('results-loading')).not.toBeInTheDocument()
    const alice = card('Dr. Alice Chen')
    expect(within(alice).getByText('82.4')).toBeInTheDocument()
    expect(within(alice).getByText('/100')).toBeInTheDocument()
    expect(alice).toHaveTextContent('Cardiology · Heart Failure & Transplant')
    expect(alice).toHaveTextContent('New York, NY · 6.2 mi away')
    expect(alice).toHaveTextContent('Accepting new patients')
    expect(alice).toHaveTextContent('Quality score88.5')
    expect(alice).toHaveTextContent('Experience15 years')
    expect(alice).toHaveTextContent('Cost12% below average')
    expect(
      within(alice).getByText('Dr. Alice Chen ranks highly for quality among cardiologists.'),
    ).toBeInTheDocument()

    const bob = card('Dr. Bob Diaz')
    expect(bob).not.toHaveTextContent('mi away')
    expect(bob).not.toHaveTextContent('Accepting new patients')

    // One legend for the whole list, with the weights.
    const legend = screen.getByRole('list', { name: 'Score components and weights' })
    expect(
      within(legend)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['Quality35%', 'Experience20%', 'Cost20%', 'Volume10%', 'Distance15%'])
  })

  it('links each card to the provider with the search context', async () => {
    renderResults(
      '/results?specialty=cardiology&city=New+York&state=NY&radius_miles=10&priority=quality&page=2',
      answer(response([ALICE])),
    )

    const link = await screen.findByRole('link', { name: 'Dr. Alice Chen' })

    const href = new URL(link.getAttribute('href')!, 'http://localhost')
    expect(href.pathname).toBe('/providers/1')
    expect(Object.fromEntries(href.searchParams)).toEqual({
      priority: 'quality',
      city: 'New York',
      state: 'NY',
      radius_miles: '10',
    })
  })

  it('links with just the priority when the search has no location', async () => {
    renderResults('/results?specialty=cardiology', answer(response([BOB])))

    const link = await screen.findByRole('link', { name: 'Dr. Bob Diaz' })

    expect(link).toHaveAttribute('href', '/providers/2?priority=balanced')
  })

  it('summarizes the criteria with names from the reference data', async () => {
    const fetchSpy = routeFetch({
      'GET /api/v1/specialties': () =>
        jsonResponse([
          { id: 9, slug: 'family-medicine', name: 'Family Medicine', provider_count: 3 },
        ]),
      [`POST ${SEARCH_URL}`]: answer(response([])),
    })
    render(
      <MemoryRouter
        initialEntries={[
          '/results?specialty=family-medicine&condition=heart-failure&city=Chicago&state=IL' +
            '&radius_miles=5&accepting_new_patients=true&source=nl&parser_used=rule_based',
        ]}
      >
        <ResultsPage />
      </MemoryRouter>,
    )

    const summary = screen.getByRole('region', { name: 'Your search' })
    await waitFor(() => expect(summary).toHaveTextContent('SpecialtyFamily Medicine'))
    expect(summary).toHaveTextContent('ConditionHeart failure')
    expect(summary).toHaveTextContent('LocationChicago, IL (within 5 mi)')
    expect(summary).toHaveTextContent('Accepting new patientsYes')
    expect(summary).toHaveTextContent('FromYour description (interpreted by keyword matching)')
    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/conditions', expect.anything())
  })

  it('shows the empty state with suggestions and a link back to the search', async () => {
    renderResults(
      '/results?specialty=cardiology&city=Chicago&state=IL&radius_miles=10&min_quality_score=90&sort=cost',
      answer(response([])),
    )

    expect(await screen.findByText('No providers match your search')).toBeInTheDocument()
    expect(screen.getByText('0 providers found')).toBeInTheDocument()
    expect(screen.getByText('Widen the radius (currently 10 miles).')).toBeInTheDocument()
    expect(
      screen.getByText('Remove the minimum quality score or years of experience.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Try another location, or search anywhere.')).toBeInTheDocument()
    const links = screen.getAllByRole('link', { name: 'Change search' })
    // Back to the editor with the same criteria, minus the results-only sort and page.
    for (const link of links) {
      expect(link).toHaveAttribute(
        'href',
        '/?specialty=cardiology&city=Chicago&state=IL&radius_miles=10&min_quality_score=90',
      )
    }
    expect(screen.queryByRole('list', { name: 'Score components and weights' })).toBeNull()
  })

  it('shows the error with its request ID, and Retry searches again', async () => {
    let calls = 0
    const { fetchSpy, user } = renderResults('/results?specialty=cardiology', () => {
      calls += 1
      return calls === 1
        ? jsonResponse(errorBody('INTERNAL_ERROR', 'An unexpected error occurred', 'req-500'), {
            status: 500,
          })
        : jsonResponse(response([ALICE]))
    })

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("Couldn't load results")
    expect(alert).toHaveTextContent('An unexpected error occurred')
    expect(alert).toHaveTextContent('Request ID: req-500')

    await user.click(within(alert).getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('article', { name: 'Dr. Alice Chen' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(searchBodies(fetchSpy)).toHaveLength(2)
  })

  it('changes the sort in the URL, back to page 1, and searches again', async () => {
    const { fetchSpy, user } = renderResults('/results?specialty=cardiology&page=3', paged(100))
    await screen.findByRole('article', { name: 'Dr. Page 3' })

    await user.selectOptions(screen.getByRole('combobox', { name: 'Sort by' }), 'Quality')

    await screen.findByRole('article', { name: 'Dr. Page 1' })
    expect(currentParams()).toEqual({ specialty: 'cardiology', sort: 'quality' })
    expect(searchBodies(fetchSpy)).toEqual([
      { specialty: 'cardiology', page: 3 },
      { specialty: 'cardiology', sort: 'quality' },
    ])
  })

  it('changes the priority in the URL, back to page 1, and searches again', async () => {
    const { fetchSpy, user } = renderResults(
      '/results?specialty=cardiology&priority=quality&page=2',
      paged(100),
    )
    await screen.findByRole('article', { name: 'Dr. Page 2' })
    expect(screen.getByRole('radio', { name: 'Quality' })).toBeChecked()

    await user.click(screen.getByRole('radio', { name: 'Cost' }))

    await screen.findByRole('article', { name: 'Dr. Page 1' })
    expect(currentParams()).toEqual({ specialty: 'cardiology', priority: 'cost' })
    expect(searchBodies(fetchSpy).at(-1)).toEqual({ specialty: 'cardiology', priority: 'cost' })
  })

  it('disables distance sort and priority without a location', async () => {
    renderResults('/results?specialty=cardiology', answer(response([ALICE])))

    expect(screen.getByRole('option', { name: 'Distance (needs a location)' })).toBeDisabled()
    expect(screen.getByRole('radio', { name: 'Distance' })).toBeDisabled()
    expect(screen.getByRole('radio', { name: 'Distance' })).toHaveAccessibleDescription(
      'Distance needs a location.',
    )
    await screen.findByRole('article', { name: 'Dr. Alice Chen' })
  })

  it('allows distance sort and priority with a location', async () => {
    renderResults('/results?city=Chicago&state=IL', answer(response([ALICE])))

    expect(screen.getByRole('option', { name: 'Distance' })).toBeEnabled()
    expect(screen.getByRole('radio', { name: 'Distance' })).toBeEnabled()
    await screen.findByRole('article', { name: 'Dr. Alice Chen' })
  })

  it('pages through the results, updating the URL and scrolling to the top', async () => {
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
    const { fetchSpy, user } = renderResults('/results?specialty=cardiology', paged(45))
    await screen.findByRole('article', { name: 'Dr. Page 1' })

    const nav = screen.getByRole('navigation', { name: 'Pagination' })
    expect(within(nav).getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(within(nav).getByRole('button', { name: 'Page 1' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(
      within(nav)
        .getAllByRole('button', { name: /^Page / })
        .map((b) => b.textContent),
    ).toEqual(['1', '2', '3'])

    await user.click(within(nav).getByRole('button', { name: 'Next' }))

    await screen.findByRole('article', { name: 'Dr. Page 2' })
    expect(currentParams()).toEqual({ specialty: 'cardiology', page: '2' })
    expect(scrollTo).toHaveBeenCalledWith({ top: 0 })

    await user.click(screen.getByRole('button', { name: 'Page 3' }))
    await screen.findByRole('article', { name: 'Dr. Page 3' })
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
    expect(currentParams()).toEqual({ specialty: 'cardiology', page: '3' })

    await user.click(screen.getByRole('button', { name: 'Page 1' }))
    await screen.findByRole('article', { name: 'Dr. Page 1' })
    expect(currentParams()).toEqual({ specialty: 'cardiology' })
    expect(searchBodies(fetchSpy).map((body) => body.page)).toEqual([undefined, 2, 3, undefined])
  })

  it('hides pagination when everything fits on one page', async () => {
    renderResults('/results', answer(response([ALICE, BOB])))

    await screen.findByRole('article', { name: 'Dr. Alice Chen' })
    expect(screen.queryByRole('navigation', { name: 'Pagination' })).not.toBeInTheDocument()
  })

  it('offers the first page when the page is past the end', async () => {
    const { user } = renderResults(
      '/results?page=9',
      answer(response([], { page: 9, total: 45, total_pages: 3 })),
    )

    expect(await screen.findByText("There's no page 9")).toBeInTheDocument()
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
    await user.click(screen.getByRole('button', { name: 'Go to the first page' }))
    expect(currentParams()).toEqual({})
  })

  it('never lets an older response replace a newer one', async () => {
    const first = deferred()
    let calls = 0
    const { fetchSpy, user } = renderResults('/results?specialty=cardiology', () => {
      calls += 1
      // The first request ignores its abort and answers last, as a slow server might.
      return calls === 1 ? first.promise : jsonResponse(response([BOB], { sort: 'quality' }))
    })
    await waitFor(() => expect(searchBodies(fetchSpy)).toHaveLength(1))
    const firstSignal = fetchSpy.mock.calls.find(([url]) => url === SEARCH_URL)![1]!.signal!

    await user.selectOptions(screen.getByRole('combobox', { name: 'Sort by' }), 'Quality')
    expect(await screen.findByRole('article', { name: 'Dr. Bob Diaz' })).toBeInTheDocument()
    expect(firstSignal.aborted).toBe(true)

    first.resolve(jsonResponse(response([ALICE])))
    // Let the stale response settle, then check it was dropped.
    await new Promise((resolve) => setTimeout(resolve, 20))

    expect(screen.queryByRole('article', { name: 'Dr. Alice Chen' })).not.toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Dr. Bob Diaz' })).toBeInTheDocument()
    expect(screen.getByText('1 provider found')).toBeInTheDocument()
  })

  it('ignores garbage parameters', async () => {
    const { fetchSpy } = renderResults(
      '/results?specialty=<script>&radius_miles=-1&priority=distance&page=abc&x=1',
      answer(response([ALICE])),
    )

    expect(screen.getByText('No filters: all providers.')).toBeInTheDocument()
    await screen.findByRole('article', { name: 'Dr. Alice Chen' })
    expect(searchBodies(fetchSpy)).toEqual([{}])
  })
})
