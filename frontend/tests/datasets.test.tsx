import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import {
  CMS_DISCLAIMER_TEXT,
  DISCLAIMER_TEXT,
  NEUTRAL_DISCLAIMER_TEXT,
} from '../src/components/layout/Disclaimer'
import type { RankingWeightsResponse } from '../src/types/ranking'
import type { SearchResponse, SearchResult } from '../src/types/search'
import {
  CMS_DATASET,
  CMS_RESULT,
  CMS_RESULT_UNREPORTED,
  CMS_ROUTES,
  CMS_SCORED_DETAIL,
  SYNTHETIC_FLAGS,
  requestBodies,
  routeFetch,
  type Handler,
} from './fixtures'
import { errorBody, jsonResponse, renderAppAt, tableRows } from './utils'

const SEARCH = 'POST /api/v1/search'

const SYNTHETIC_RESULT: SearchResult = {
  provider: {
    id: 1,
    npi: null,
    data_source: 'synthetic',
    display_name: 'Dr. Maya Patel, MD',
    specialty: { slug: 'cardiology', name: 'Cardiology' },
    subspecialty: null,
    city: 'New York',
    state: 'NY',
    years_experience: 15,
    quality_score: 88.5,
    cost_index: 0.88,
    accepting_new_patients: true,
    metric_flags: SYNTHETIC_FLAGS,
  },
  distance_miles: null,
  score: {
    overall: 82.4,
    components: [
      {
        name: 'quality',
        raw: 88.5,
        normalized: 0.885,
        weight: 0.41,
        contribution: 36.4,
        imputed: false,
      },
      {
        name: 'experience',
        raw: 15,
        normalized: 0.8,
        weight: 0.24,
        contribution: 18.8,
        imputed: false,
      },
      {
        name: 'cost',
        raw: 0.88,
        normalized: 0.62,
        weight: 0.18,
        contribution: 10.9,
        imputed: false,
      },
      {
        name: 'volume',
        raw: 0.6,
        normalized: 0.6,
        weight: 0.18,
        contribution: 10.6,
        imputed: false,
      },
    ],
  },
  explanation: 'No single standout factor. 15 years of experience, cost 12% below average.',
}

const WEIGHTS: RankingWeightsResponse = {
  profiles: {
    balanced: { quality: 0.35, experience: 0.2, cost: 0.15, volume: 0.15, distance: 0.15 },
    quality: { quality: 0.55, experience: 0.2, cost: 0.05, volume: 0.1, distance: 0.1 },
    cost: { quality: 0.25, experience: 0.1, cost: 0.45, volume: 0.05, distance: 0.15 },
    experience: { quality: 0.25, experience: 0.45, cost: 0.1, volume: 0.1, distance: 0.1 },
    distance: { quality: 0.25, experience: 0.1, cost: 0.1, volume: 0.05, distance: 0.5 },
  },
  min_quality_weight: 0.25,
}

function searchResponse(items: SearchResult[]): SearchResponse {
  return {
    items,
    page: 1,
    page_size: 20,
    total: items.length,
    total_pages: items.length ? 1 : 0,
    priority: 'balanced',
    sort: 'match',
    weights_used: { quality: 0.412, experience: 0.235, cost: 0.176, volume: 0.176 },
  }
}

function renderCms(path: string, routes: Record<string, Handler> = {}) {
  const fetchSpy = routeFetch({ ...CMS_ROUTES, ...routes })
  renderAppAt(path)
  return fetchSpy
}

/** Waits until GET /dataset has answered with the CMS data (its banner is up). */
async function cmsLoaded() {
  return screen.findByRole('complementary', { name: 'About this data' })
}

/** Waits until GET /dataset has been answered, whatever it said. */
async function datasetFetched(fetchSpy: ReturnType<typeof routeFetch>) {
  await waitFor(() => expect(fetchSpy).toHaveBeenCalledWith('/api/v1/dataset', expect.anything()))
  // Let the response settle into state.
  await new Promise((resolve) => setTimeout(resolve, 0))
}

function card(name: string): HTMLElement {
  return screen.getByRole('article', { name })
}

/** A result card's facts, term -> value. */
function facts(article: HTMLElement): Record<string, string> {
  const terms = within(article).getAllByRole('term')
  return Object.fromEntries(
    terms.map((term) => [term.textContent, term.nextElementSibling?.textContent ?? '']),
  )
}

describe('the disclaimer banner', () => {
  it('shows the CMS disclaimer, source and as-of date on every page', async () => {
    renderCms('/methodology', { 'GET /api/v1/ranking/weights': () => jsonResponse(WEIGHTS) })

    const banner = await cmsLoaded()

    expect(banner).toHaveTextContent('CMS public data: New Jersey')
    expect(banner).toHaveTextContent('Data as of September 26, 2026')
    expect(banner).toHaveTextContent(CMS_DATASET.disclaimer)
    expect(within(banner).getByRole('link', { name: 'About the real data' })).toHaveAttribute(
      'href',
      '/methodology#real-data',
    )
    // The footer stays, and no longer says the data is synthetic.
    expect(screen.getByRole('note')).toHaveTextContent(CMS_DISCLAIMER_TEXT)
  })

  it('is not shown for synthetic data, and the footer is unchanged', async () => {
    const fetchSpy = routeFetch({ [SEARCH]: () => jsonResponse(searchResponse([])) })
    renderAppAt('/results?specialty=cardiology')

    await datasetFetched(fetchSpy)
    expect(await screen.findByText('No providers match your search')).toBeInTheDocument()

    expect(screen.queryByRole('complementary', { name: 'About this data' })).toBeNull()
    expect(screen.getByRole('note')).toHaveTextContent(DISCLAIMER_TEXT)
  })
})

describe('result cards', () => {
  it('use the CMS labels, "Not reported" for nulls and a peer comparison for spending', async () => {
    renderCms('/results?specialty=cardiology', {
      [SEARCH]: () => jsonResponse(searchResponse([CMS_RESULT, CMS_RESULT_UNREPORTED])),
    })
    await cmsLoaded()
    await screen.findByText('Dr. Bob Testperson, DO')

    expect(facts(card('Dr. Bob Testperson, DO'))).toEqual({
      'MIPS final score': 'Not reported',
      'Years since medical school': '36 years',
      'Medicare spending per patient': 'Lower than 85% of cardiologists',
    })
    expect(facts(card('Dr. Ann Testperson, MD'))).toEqual({
      'MIPS final score': '65.0',
      'Years since medical school': 'Not reported',
      'Medicare spending per patient': 'Not reported',
    })
    const legend = screen.getByRole('list', { name: 'Score components and weights' })
    expect(legend).toHaveTextContent('Medicare spending per patient')
    expect(
      within(screen.getByLabelText('Sort by')).getByRole('option', {
        name: 'Medicare spending per patient',
      }),
    ).toBeInTheDocument()
    const main = screen.getByRole('main')
    expect(main).not.toHaveTextContent(/NaN|\bCost\b/)
  })

  it('show no badge when accepting new patients is unknown', async () => {
    renderCms('/results', { [SEARCH]: () => jsonResponse(searchResponse([CMS_RESULT])) })
    await cmsLoaded()
    await screen.findByText('Dr. Bob Testperson, DO')

    expect(screen.queryByText('Accepting new patients')).toBeNull()
  })

  it('keep the synthetic labels and values for synthetic data', async () => {
    const fetchSpy = routeFetch({
      [SEARCH]: () => jsonResponse(searchResponse([SYNTHETIC_RESULT])),
    })
    renderAppAt('/results')
    await datasetFetched(fetchSpy)
    await screen.findByText('Dr. Maya Patel, MD')

    expect(facts(card('Dr. Maya Patel, MD'))).toEqual({
      'Quality score': '88.5',
      Experience: '15 years',
      Cost: '12% below average',
    })
    expect(within(card('Dr. Maya Patel, MD')).getByText('Accepting new patients')).toBeVisible()
  })
})

describe('the provider detail page with CMS data', () => {
  function renderDetail() {
    renderCms('/providers/21?priority=balanced', {
      'GET /api/v1/providers/21?priority=balanced': () => jsonResponse(CMS_SCORED_DETAIL),
    })
  }

  it('marks imputed rows in the breakdown, with a legend', async () => {
    renderDetail()
    await cmsLoaded()

    const table = await screen.findByRole('table', { name: 'Score breakdown' })
    const rows = tableRows(table)
    expect(rows[1]).toEqual([
      'MIPS final score*',
      'Not reported (scored as specialty median)',
      '0.90',
      '41.2%',
      '37.2',
    ])
    expect(rows[3]?.[1]).toBe('Lower than 85% of cardiologists')
    const imputed = table.querySelectorAll('tbody tr[data-imputed]')
    expect(Array.from(imputed, (row) => row.querySelector('th')?.textContent)).toEqual([
      'MIPS final score*',
    ])
    expect(
      screen.getByText(/Not reported for this provider: scored as the median of their specialty/),
    ).toBeInTheDocument()
  })

  it('says what CMS does not publish, and shows no badge', async () => {
    renderDetail()
    await cmsLoaded()
    await screen.findByRole('heading', { name: 'Dr. Bob Testperson, DO', level: 1 })

    const metrics = screen.getByRole('region', { name: 'Metrics' })
    const values = Object.fromEntries(
      within(metrics)
        .getAllByRole('term')
        .map((term) => [term.textContent, term.nextElementSibling?.textContent]),
    )
    expect(values).toEqual({
      'MIPS final score': 'Not reported',
      'Years since medical school': '36 years',
      'Medicare spending per patient': 'Lower than 85% of cardiologists',
      'Medicare patients': '944 patients',
      'Complication rate': 'Not published for individual clinicians',
      'Readmission rate': 'Not published for individual clinicians',
      NPI: '9000000002',
      'ZIP code': '07102',
    })
    expect(screen.getByRole('region', { name: 'Conditions treated' })).toHaveTextContent(
      'Not published for individual clinicians.',
    )
    expect(screen.queryByText('Accepting new patients')).toBeNull()
    expect(screen.getByText(/Scored for Balanced priority/)).toBeInTheDocument()
  })
})

describe('the search page', () => {
  it('hides the condition field for CMS and offers the quality checkbox', async () => {
    renderCms('/')
    await cmsLoaded()

    expect(screen.queryByLabelText('Condition')).toBeNull()
    expect(screen.queryByLabelText('Accepting new patients only')).toBeNull()
    expect(screen.getByLabelText('Only providers with a quality score')).not.toBeChecked()
    expect(screen.getByLabelText('Minimum MIPS final score')).toBeInTheDocument()
    expect(screen.getByLabelText('Minimum years since medical school')).toBeInTheDocument()
  })

  it('sends require_quality_score from the checkbox, and never a condition', async () => {
    const user = userEvent.setup()
    const fetchSpy = renderCms('/?specialty=cardiology&condition=heart-failure', {
      [SEARCH]: () => jsonResponse(searchResponse([])),
    })
    await cmsLoaded()

    await user.click(screen.getByLabelText('Only providers with a quality score'))
    await user.click(screen.getByRole('button', { name: 'Search providers' }))

    await screen.findByText('No providers match your search')
    const bodies = requestBodies(fetchSpy, '/api/v1/search')
    expect(bodies.at(-1)).toMatchObject({ specialty: 'cardiology', require_quality_score: true })
    expect(bodies.every((body) => !('condition' in (body as object)))).toBe(true)
    expect(screen.getByRole('region', { name: 'Your search' })).toHaveTextContent(
      'MIPS final scoreReported only',
    )
    expect(screen.getByText('Include providers without a quality score.')).toBeInTheDocument()
  })

  it('keeps the condition field and has no quality checkbox for synthetic data', async () => {
    const fetchSpy = routeFetch()
    renderAppAt('/')
    await datasetFetched(fetchSpy)

    expect(screen.getByLabelText('Condition')).toBeInTheDocument()
    expect(screen.getByLabelText('Accepting new patients only')).toBeInTheDocument()
    expect(screen.queryByLabelText('Only providers with a quality score')).toBeNull()
    expect(screen.getByLabelText('Minimum quality score')).toBeInTheDocument()
  })
})

describe('the results page with an old link', () => {
  it('drops a condition the CMS data cannot answer', async () => {
    const fetchSpy = renderCms('/results?specialty=cardiology&condition=heart-failure', {
      [SEARCH]: () => jsonResponse(searchResponse([])),
    })
    await cmsLoaded()

    await waitFor(() => {
      const bodies = requestBodies(fetchSpy, '/api/v1/search')
      expect(bodies.at(-1)).toEqual({ specialty: 'cardiology' })
    })
    expect(screen.getByRole('region', { name: 'Your search' })).not.toHaveTextContent('Condition')
  })
})

describe('the methodology page', () => {
  it('explains the real data for CMS', async () => {
    renderCms('/methodology', { 'GET /api/v1/ranking/weights': () => jsonResponse(WEIGHTS) })
    await cmsLoaded()

    const section = screen.getByRole('region', { name: 'About the real data' })
    for (const text of [
      'Doctors and Clinicians National Downloadable File',
      'PY 2024 Clinician Public Reporting: Overall MIPS Performance',
      'Medicare Physician & Other Practitioners – by Provider',
      'A MIPS final score of 0 counts as not reported.',
      'Spending leaves out Part B drugs',
      'Spending needs at least 30 patients.',
      'A missing value is scored as the specialty median',
    ]) {
      expect(section).toHaveTextContent(text)
    }
    expect(within(section).getByRole('link', { name: 'data-quality report' })).toHaveAttribute(
      'href',
      'https://github.com/acana68/ProviderIQ/blob/main/docs/data-quality.md',
    )
    const toc = screen.getByRole('navigation', { name: 'On this page' })
    expect(within(toc).getByRole('link', { name: 'About the real data' })).toHaveAttribute(
      'href',
      '#real-data',
    )
    expect(screen.queryByText(/All provider data is synthetic/)).toBeNull()
    const weights = await screen.findByRole('table', { name: 'Weight of each factor, by priority' })
    expect(tableRows(weights)[0]).toContain('Medicare spending per patient')
  })

  it('has no real-data section for synthetic data', async () => {
    const fetchSpy = routeFetch({ 'GET /api/v1/ranking/weights': () => jsonResponse(WEIGHTS) })
    renderAppAt('/methodology')
    await datasetFetched(fetchSpy)

    expect(screen.queryByRole('region', { name: 'About the real data' })).toBeNull()
    expect(
      within(screen.getByRole('main')).getByText(/All provider data is synthetic/),
    ).toBeVisible()
  })
})

describe('before GET /dataset answers', () => {
  it('shows only a neutral loading state, then the page with the right labels', async () => {
    let answer: (response: Response) => void = () => {}
    routeFetch({
      ...CMS_ROUTES,
      'GET /api/v1/dataset': () => new Promise<Response>((resolve) => (answer = resolve)),
    })

    renderAppAt('/')

    expect(await screen.findByRole('status')).toHaveTextContent('Loading…')
    // Nothing that depends on the dataset: no page, no banner, no dataset claim.
    expect(screen.queryByRole('heading', { level: 1 })).toBeNull()
    expect(screen.queryByRole('complementary', { name: 'About this data' })).toBeNull()
    expect(screen.getByRole('note')).toHaveTextContent(NEUTRAL_DISCLAIMER_TEXT)
    expect(document.body).not.toHaveTextContent(/synthetic|CMS|Quality score|Cost/)

    answer(jsonResponse(CMS_DATASET))

    await cmsLoaded()
    expect(screen.getByRole('heading', { level: 1, name: 'ProviderIQ' })).toBeInTheDocument()
    expect(screen.getByLabelText('Minimum MIPS final score')).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent(CMS_DISCLAIMER_TEXT)
  })

  it('falls back to synthetic labels and a neutral footer if it fails', async () => {
    routeFetch({
      'GET /api/v1/dataset': () =>
        jsonResponse(errorBody('INTERNAL_ERROR', 'An unexpected error occurred'), { status: 500 }),
    })

    renderAppAt('/')

    expect(await screen.findByRole('heading', { level: 1, name: 'ProviderIQ' })).toBeVisible()
    expect(screen.getByLabelText('Minimum quality score')).toBeInTheDocument()
    expect(screen.getByLabelText('Condition')).toBeInTheDocument()
    expect(screen.queryByRole('complementary', { name: 'About this data' })).toBeNull()
    // Claims neither dataset.
    expect(screen.getByRole('note')).toHaveTextContent(NEUTRAL_DISCLAIMER_TEXT)
    expect(screen.getByRole('note')).not.toHaveTextContent(/synthetic|CMS/)
  })
})

describe('priority buttons with CMS data', () => {
  it('are short, with the full metric name as tooltip and accessible name', async () => {
    renderCms('/')
    await cmsLoaded()

    const priority = screen.getByRole('group', { name: 'Priority' })
    const radios = within(priority).getAllByRole('radio')
    expect(radios.map((radio) => radio.closest('label')?.textContent)).toEqual([
      'Balanced',
      'MIPS score',
      'Spending',
      'Years in medicine',
      'Distance',
    ])
    const spending = within(priority).getByRole('radio', { name: 'Medicare spending per patient' })
    expect(spending.closest('label')).toHaveAttribute('title', 'Medicare spending per patient')
    expect(
      within(priority).getByRole('radio', { name: 'Years since medical school' }),
    ).toBeInTheDocument()
    // Distance keeps its "needs a location" tooltip.
    expect(
      within(priority).getByRole('radio', { name: 'Distance' }).closest('label'),
    ).toHaveAttribute('title', 'Choose a location to prioritize distance.')
  })

  it('are unchanged for synthetic data: no extra tooltip or name', async () => {
    const fetchSpy = routeFetch()
    renderAppAt('/')
    await datasetFetched(fetchSpy)

    const priority = await screen.findByRole('group', { name: 'Priority' })
    const cost = within(priority).getByRole('radio', { name: 'Cost' })
    expect(cost.closest('label')).not.toHaveAttribute('title')
    expect(cost).not.toHaveAttribute('aria-label')
  })
})

describe('values served by GET /dataset', () => {
  it('names peers and the spending minimum as the dataset says', async () => {
    const dataset = {
      ...CMS_DATASET,
      min_spending_patients: 25,
      peer_nouns: { cardiology: 'heart specialists' },
    }
    renderCms('/results', {
      'GET /api/v1/dataset': () => jsonResponse(dataset),
      [SEARCH]: () => jsonResponse(searchResponse([CMS_RESULT])),
      'GET /api/v1/ranking/weights': () => jsonResponse(WEIGHTS),
    })
    await cmsLoaded()
    await screen.findByText('Dr. Bob Testperson, DO')

    expect(facts(card('Dr. Bob Testperson, DO'))['Medicare spending per patient']).toBe(
      'Lower than 85% of heart specialists',
    )

    await userEvent.setup().click(screen.getByRole('link', { name: 'Methodology' }))
    const section = await screen.findByRole('region', { name: 'About the real data' })
    expect(section).toHaveTextContent('Spending needs at least 25 patients.')
  })
})
