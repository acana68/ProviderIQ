import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { describe, expect, it } from 'vitest'
import { ProviderDetailPage } from '../src/pages/ProviderDetailPage'
import type { ProviderDetail, ScoredProviderDetail } from '../src/types/provider'
import { routeFetch, type Handler } from './fixtures'
import { errorBody, hangingFetch, jsonResponse, mockFetch, renderAppAt, tableRows } from './utils'

const DETAIL: ProviderDetail = {
  id: 7,
  display_name: 'Dr. Maya Patel',
  specialty: { slug: 'cardiology', name: 'Cardiology' },
  subspecialty: 'Interventional Cardiology',
  city: 'New York',
  state: 'NY',
  zip_code: '10016',
  latitude: 40.74,
  longitude: -73.98,
  years_experience: 31,
  quality_score: 88.4,
  cost_index: 0.79,
  accepting_new_patients: true,
  patient_volume: 2345,
  complication_rate: 0.0464,
  readmission_rate: 0.0812,
  conditions: [
    { slug: 'heart-failure', name: 'Heart Failure' },
    { slug: 'atrial-fibrillation', name: 'Atrial Fibrillation' },
  ],
}

function scored(overall: number): ScoredProviderDetail {
  return {
    ...DETAIL,
    distance_miles: 6.2,
    explanation:
      'Stands out for experience (31 years; more experienced than 97% of cardiologists).',
    score: {
      overall,
      components: [
        { name: 'quality', raw: 88.4, normalized: 0.884, weight: 0.55, contribution: 48.6 },
        { name: 'experience', raw: 31, normalized: 1, weight: 0.2, contribution: 20 },
        { name: 'cost', raw: 0.79, normalized: 0.71, weight: 0.05, contribution: 3.6 },
        { name: 'volume', raw: 0.963, normalized: 0.963, weight: 0.1, contribution: 9.6 },
        { name: 'distance', raw: 6.2, normalized: 0.38, weight: 0.1, contribution: 3.8 },
      ],
    },
  }
}

// Only the overall differs between priorities here; that's all the tests look at.
const SCORED_QUALITY = scored(85.6)
const SCORED_COST = scored(71.3)
const CONTEXT = '?priority=quality&city=New+York&state=NY&radius_miles=10'
const RESULTS_URL = '/results?specialty=cardiology&city=New+York&state=NY&sort=quality&page=2'

/** The current URL, shown next to the page. */
function LocationDisplay() {
  const { pathname, search } = useLocation()
  return <output aria-label="current URL">{pathname + search}</output>
}

function renderDetail(url: string, routes: Record<string, Handler>, state?: unknown) {
  const fetchSpy = routeFetch(routes)
  const [pathname, search = ''] = url.split('?')
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={[{ pathname, search: search && `?${search}`, state }]}>
      <Routes>
        <Route path="/providers/:providerId" element={<ProviderDetailPage />} />
        <Route path="/" element={<h1>Search page</h1>} />
        <Route path="/results" element={<h1>Results page</h1>} />
      </Routes>
      <LocationDisplay />
    </MemoryRouter>,
  )
  return { fetchSpy, user }
}

function providerCalls(fetchSpy: ReturnType<typeof routeFetch>): string[] {
  return fetchSpy.mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.includes('/providers/'))
}

function currentUrl(): string {
  return screen.getByRole('status', { name: 'current URL' }).textContent ?? ''
}

describe('ProviderDetailPage', () => {
  it('shows the score, explanation and breakdown when opened with a search context', async () => {
    const { fetchSpy } = renderDetail(`/providers/7${CONTEXT}`, {
      [`GET /api/v1/providers/7${CONTEXT}`]: () => jsonResponse(SCORED_QUALITY),
    })

    expect(await screen.findByRole('heading', { level: 1, name: 'Dr. Maya Patel' })).toBeVisible()
    expect(providerCalls(fetchSpy)).toEqual([`/api/v1/providers/7${CONTEXT}`])
    await waitFor(() => expect(document.title).toBe('Dr. Maya Patel · ProviderIQ'))
    expect(screen.getByText('Cardiology · Interventional Cardiology')).toBeInTheDocument()
    expect(screen.getByText('New York, NY · 6.2 mi away')).toBeInTheDocument()
    expect(screen.getByText('Accepting new patients')).toBeInTheDocument()

    const score = screen.getByRole('region', { name: 'Match score' })
    expect(score).toHaveTextContent(/^Match score85\.6\/100/)
    expect(score).toHaveTextContent(
      'Stands out for experience (31 years; more experienced than 97% of cardiologists).',
    )
    expect(score).toHaveTextContent('Scored for Quality priority · near New York, NY within 10 mi')
    expect(within(score).getByRole('radio', { name: 'Quality' })).toBeChecked()
    expect(
      within(score).getByRole('img', { name: /^Score breakdown, 85.6 out of 100/ }),
    ).toBeInTheDocument()

    expect(tableRows(within(score).getByRole('table', { name: 'Score breakdown' }))).toEqual([
      ['Factor', 'Value', 'Normalized', 'Weight', 'Points'],
      ['Quality', '88.4 / 100', '0.88', '55%', '48.6'],
      ['Experience', '31 years', '1.00', '20%', '20.0'],
      ['Cost', '21% below average', '0.71', '5%', '3.6'],
      ['Volume', '96th percentile in specialty', '0.96', '10%', '9.6'],
      ['Distance', '6.2 mi', '0.38', '10%', '3.8'],
      ['Total', '', '', '100%', '85.6'],
    ])
    expect(score).toHaveTextContent(
      'Points = normalized × weight × 100. Totals may differ by 0.1 due to rounding.',
    )
    expect(within(score).getByRole('link', { name: 'How scoring works' })).toHaveAttribute(
      'href',
      '/methodology',
    )
  })

  it('shows the metrics and conditions', async () => {
    renderDetail('/providers/7', { 'GET /api/v1/providers/7': () => jsonResponse(DETAIL) })

    const metrics = await screen.findByRole('region', { name: 'Metrics' })
    const pairs = Object.fromEntries(
      within(metrics)
        .getAllByRole('term')
        .map((term) => [term.textContent, term.nextElementSibling?.textContent]),
    )
    expect(pairs).toEqual({
      'Quality score': '88.4 / 100',
      'Years of experience': '31 years',
      Cost: '21% below average',
      'Annual patient volume': '2,345 patients',
      'Complication rate': '4.6% (lower is better)',
      'Readmission rate': '8.1% (lower is better)',
      'ZIP code': '10016',
    })

    const conditions = screen.getByRole('region', { name: 'Conditions treated' })
    expect(
      within(conditions)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['Heart Failure', 'Atrial Fibrillation'])
  })

  it('without a context: sends no context params, shows no score, and points to search', async () => {
    const { fetchSpy } = renderDetail('/providers/7', {
      'GET /api/v1/providers/7': () => jsonResponse(DETAIL),
    })

    await screen.findByRole('heading', { level: 1, name: 'Dr. Maya Patel' })
    expect(providerCalls(fetchSpy)).toEqual(['/api/v1/providers/7'])
    expect(screen.queryByRole('region', { name: 'Match score' })).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(
      screen.getByText(
        "Scores depend on what you're looking for. Run a search to see this provider's match score.",
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start a search' })).toHaveAttribute('href', '/')
    expect(screen.getByText('New York, NY')).toBeInTheDocument()
  })

  it('ignores invalid context params rather than sending them', async () => {
    const { fetchSpy } = renderDetail(
      '/providers/7?priority=fastest&city=New+York&radius_miles=9000',
      {
        'GET /api/v1/providers/7': () => jsonResponse(DETAIL),
      },
    )

    await screen.findByRole('heading', { level: 1, name: 'Dr. Maya Patel' })
    expect(providerCalls(fetchSpy)).toEqual(['/api/v1/providers/7'])
  })

  it('scores without a location when the context has none, with distance disabled', async () => {
    const withoutDistance: ScoredProviderDetail = {
      ...SCORED_QUALITY,
      distance_miles: null,
      score: {
        overall: 91.3,
        components: SCORED_QUALITY.score.components.filter((c) => c.name !== 'distance'),
      },
    }
    renderDetail('/providers/7?priority=quality', {
      'GET /api/v1/providers/7?priority=quality': () => jsonResponse(withoutDistance),
    })

    const score = await screen.findByRole('region', { name: 'Match score' })
    expect(score).toHaveTextContent('Scored for Quality priority · no location')
    expect(within(score).getByRole('radio', { name: 'Distance' })).toBeDisabled()
    expect(within(score).getAllByRole('row')).toHaveLength(1 + 4 + 1)
    expect(screen.queryByText(/mi away/)).not.toBeInTheDocument()
  })

  it('changing the priority updates the URL and refetches, keeping the provider on screen', async () => {
    let answerCost: (response: Response) => void = () => {}
    const { fetchSpy, user } = renderDetail(
      `/providers/7${CONTEXT}`,
      {
        [`GET /api/v1/providers/7${CONTEXT}`]: () => jsonResponse(SCORED_QUALITY),
        'GET /api/v1/providers/7?priority=cost&city=New+York&state=NY&radius_miles=10': () =>
          new Promise((resolve) => {
            answerCost = resolve
          }),
      },
      { from: RESULTS_URL },
    )
    const score = await screen.findByRole('region', { name: 'Match score' })

    await user.click(within(score).getByRole('radio', { name: 'Cost' }))

    expect(currentUrl()).toBe('/providers/7?priority=cost&city=New+York&state=NY&radius_miles=10')
    expect(providerCalls(fetchSpy)).toHaveLength(2)
    // Still showing the previous score while the new one loads.
    expect(screen.getByRole('heading', { level: 1, name: 'Dr. Maya Patel' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Match score' })).toHaveAttribute('aria-busy', 'true')

    answerCost(jsonResponse(SCORED_COST))

    await waitFor(() =>
      expect(screen.getByRole('region', { name: 'Match score' })).toHaveTextContent('71.3'),
    )
    expect(screen.getByRole('region', { name: 'Match score' })).toHaveTextContent(
      'Scored for Cost priority',
    )
    // The router state survived, so Back still returns to the results.
    expect(screen.getByRole('link', { name: 'Back to results' })).toHaveAttribute(
      'href',
      RESULTS_URL,
    )
  })

  it.each(['abc', '0', '-1', '1.5', '7x', '99999999999'])(
    'shows "Provider not found" for id %s without calling the API',
    (id) => {
      const { fetchSpy } = renderDetail(`/providers/${id}`, {})

      expect(screen.getByRole('heading', { name: 'Provider not found' })).toBeInTheDocument()
      expect(fetchSpy).not.toHaveBeenCalled()
      expect(document.title).toBe('Provider not found · ProviderIQ')
    },
  )

  it('shows "Provider not found" for a 404', async () => {
    renderDetail('/providers/404', {
      'GET /api/v1/providers/404': () =>
        jsonResponse(errorBody('NOT_FOUND', 'Provider not found'), { status: 404 }),
    })

    expect(await screen.findByRole('heading', { name: 'Provider not found' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows other errors with the request ID, and Retry loads again', async () => {
    let calls = 0
    const { fetchSpy, user } = renderDetail('/providers/7', {
      'GET /api/v1/providers/7': () => {
        calls += 1
        return calls === 1
          ? jsonResponse(errorBody('INTERNAL_ERROR', 'An unexpected error occurred', 'req-500'), {
              status: 500,
            })
          : jsonResponse(DETAIL)
      },
    })

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("Couldn't load this provider")
    expect(alert).toHaveTextContent('Request ID: req-500')

    await user.click(within(alert).getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Dr. Maya Patel' })).toBeVisible()
    expect(providerCalls(fetchSpy)).toHaveLength(2)
  })

  it('shows a skeleton while loading', () => {
    mockFetch().mockImplementation(hangingFetch)
    render(
      <MemoryRouter initialEntries={['/providers/7']}>
        <Routes>
          <Route path="/providers/:providerId" element={<ProviderDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByTestId('provider-loading')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument()
  })

  describe('back link', () => {
    it('returns to the exact results URL passed in router state', async () => {
      const { user } = renderDetail(
        '/providers/7',
        { 'GET /api/v1/providers/7': () => jsonResponse(DETAIL) },
        { from: RESULTS_URL },
      )

      const back = screen.getByRole('link', { name: 'Back to results' })
      expect(back).toHaveAttribute('href', RESULTS_URL)
      await user.click(back)

      expect(await screen.findByRole('heading', { name: 'Results page' })).toBeInTheDocument()
      expect(currentUrl()).toBe(RESULTS_URL)
    })

    it.each([
      ['no state', undefined],
      ['a non-results URL', { from: '/methodology' }],
      ['an external URL', { from: 'https://example.com/results' }],
      ['junk', 'results'],
    ])('falls back to "New search" with %s', (_name, state) => {
      renderDetail('/providers/7', { 'GET /api/v1/providers/7': () => jsonResponse(DETAIL) }, state)

      expect(screen.getByRole('link', { name: 'New search' })).toHaveAttribute('href', '/')
      expect(screen.queryByRole('link', { name: 'Back to results' })).not.toBeInTheDocument()
    })

    it('is set by the provider card on the results page', async () => {
      const results = `/results?specialty=cardiology&city=New+York&state=NY&radius_miles=10&priority=quality`
      const fetchSpy = routeFetch({
        'POST /api/v1/search': () =>
          jsonResponse({
            items: [
              {
                provider: SCORED_QUALITY,
                distance_miles: 6.2,
                score: SCORED_QUALITY.score,
                explanation: SCORED_QUALITY.explanation,
              },
            ],
            page: 1,
            page_size: 20,
            total: 1,
            total_pages: 1,
            priority: 'quality',
            sort: 'match',
            weights_used: {
              quality: 0.55,
              experience: 0.2,
              cost: 0.05,
              volume: 0.1,
              distance: 0.1,
            },
          }),
        [`GET /api/v1/providers/7${CONTEXT}`]: () => jsonResponse(SCORED_QUALITY),
      })
      const user = userEvent.setup()
      renderAppAt(results)

      await user.click(await screen.findByRole('link', { name: 'Dr. Maya Patel' }))

      expect(await screen.findByRole('region', { name: 'Match score' })).toBeInTheDocument()
      expect(fetchSpy).toHaveBeenCalledWith(`/api/v1/providers/7${CONTEXT}`, expect.anything())
      expect(screen.getByRole('link', { name: 'Back to results' })).toHaveAttribute('href', results)
    })
  })
})
