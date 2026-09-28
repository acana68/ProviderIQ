import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { describe, expect, it } from 'vitest'
import { SearchPage } from '../src/pages/SearchPage'
import type { ParseQueryResponse, ParsedCriteria } from '../src/types/search'
import { routeFetch } from './fixtures'
import { errorBody, hangingFetch, jsonResponse, mockFetch } from './utils'

const NO_CRITERIA: ParsedCriteria = {
  specialty: null,
  condition: null,
  location: null,
  radius_miles: null,
  min_quality_score: null,
  min_years_experience: null,
  accepting_new_patients: null,
  priority: null,
}

const LLM_RESULT: ParseQueryResponse = {
  criteria: {
    ...NO_CRITERIA,
    specialty: 'cardiology',
    condition: 'heart-failure',
    location: { city: 'New York', state: 'NY' },
    min_quality_score: 80,
    priority: 'quality',
  },
  parser_used: 'llm',
  warnings: [],
  crisis: false,
}

/** The /results URL the page navigated to, shown by a stand-in results page. */
function ResultsProbe() {
  const { search } = useLocation()
  return <output aria-label="results URL">{search}</output>
}

async function renderSearchPage(path = '/') {
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<SearchPage />} />
        <Route path="/results" element={<ResultsProbe />} />
      </Routes>
    </MemoryRouter>,
  )
  // Wait for all three option lists.
  await screen.findByRole('option', { name: 'Cardiology (162)' })
  await screen.findByRole('option', { name: 'New York, NY' })
  await screen.findByRole('option', { name: 'Heart failure' })
  return user
}

const input = () =>
  screen.getByRole('textbox', { name: "Describe the provider you're looking for" })
const specialty = () => screen.getByRole('combobox', { name: 'Specialty' })
const condition = () => screen.getByRole('combobox', { name: 'Condition' })
const location = () => screen.getByRole('combobox', { name: 'Location' })
const radius = () => screen.getByRole('spinbutton', { name: 'Radius (miles)' })
const priority = (name: string) => screen.getByRole('radio', { name })

function parseCalls(fetchSpy: ReturnType<typeof mockFetch>) {
  return fetchSpy.mock.calls.filter(([url]) => String(url) === '/api/v1/ai/parse-query')
}

async function resultsParams() {
  const output = await screen.findByRole('status', { name: 'results URL' })
  return Object.fromEntries(new URLSearchParams(output.textContent ?? ''))
}

describe('SearchPage', () => {
  it('renders the title, the description box, and the criteria editor', async () => {
    routeFetch()
    await renderSearchPage()

    expect(screen.getByRole('heading', { level: 1, name: 'ProviderIQ' })).toBeInTheDocument()
    expect(input()).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Interpret' })).toBeDisabled()
    expect(
      within(location())
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Anywhere', 'Chicago, IL', 'New York, NY'])
    expect(priority('Balanced')).toBeChecked()
    expect(screen.getByRole('button', { name: 'Search providers' })).toBeEnabled()
  })

  describe('Interpret', () => {
    it('fills the editor from the AI and shows "Interpreted by AI"', async () => {
      const fetchSpy = routeFetch({ 'POST /api/v1/ai/parse-query': () => jsonResponse(LLM_RESULT) })
      const user = await renderSearchPage()

      await user.type(input(), '  good cardiologist in NYC for heart failure  ')
      expect(parseCalls(fetchSpy)).toHaveLength(0)
      await user.keyboard('{Enter}')

      expect(await screen.findByText('Interpreted by AI')).toBeInTheDocument()
      expect(parseCalls(fetchSpy)[0]![1]?.body).toBe(
        '{"query":"good cardiologist in NYC for heart failure"}',
      )
      expect(specialty()).toHaveValue('cardiology')
      await waitFor(() => expect(condition()).toHaveValue('heart-failure'))
      expect(location()).toHaveValue('New York|NY')
      expect(radius()).toHaveValue(25)
      expect(screen.getByRole('spinbutton', { name: 'Minimum quality score' })).toHaveValue(80)
      expect(priority('Quality')).toBeChecked()
      expect(screen.getByRole('status', { name: '' })).toHaveTextContent(
        'Search criteria filled in below',
      )

      // Still editable afterwards.
      await user.selectOptions(specialty(), 'dermatology')
      expect(specialty()).toHaveValue('dermatology')
    })

    it('shows "Keyword matching" and the warnings for the rule-based fallback', async () => {
      routeFetch({
        'POST /api/v1/ai/parse-query': () =>
          jsonResponse({
            criteria: { ...NO_CRITERIA, specialty: 'dermatology' },
            parser_used: 'rule_based',
            warnings: ['AI interpretation was unavailable; used keyword matching.'],
          }),
      })
      const user = await renderSearchPage()

      await user.type(input(), 'skin doctor{Enter}')

      expect(await screen.findByText('Keyword matching')).toBeInTheDocument()
      expect(screen.queryByText('Interpreted by AI')).not.toBeInTheDocument()
      const notes = screen.getByRole('list', { name: 'Notes' })
      expect(within(notes).getByRole('listitem')).toHaveTextContent(
        'AI interpretation was unavailable; used keyword matching.',
      )
      expect(specialty()).toHaveValue('dermatology')
    })

    it('shows a loading state on the button while interpreting', async () => {
      routeFetch({ 'POST /api/v1/ai/parse-query': (init) => hangingFetch('', init) })
      const user = await renderSearchPage()

      await user.type(input(), 'cardiologist{Enter}')

      const button = screen.getByRole('button', { name: 'Interpreting…' })
      expect(button).toBeDisabled()
      expect(button).toHaveAttribute('aria-busy', 'true')
      expect(screen.getByRole('status', { name: '' })).toHaveTextContent(
        'Interpreting your description…',
      )
    })

    it('counts characters and caps the input at 500', async () => {
      routeFetch()
      const user = await renderSearchPage()

      await user.type(input(), 'cardiologist')

      expect(screen.getByText('12/500 characters')).toBeInTheDocument()
      expect(input()).toHaveAttribute('maxLength', '500')
    })

    it('fills the input from an example without calling the API', async () => {
      const fetchSpy = routeFetch()
      const user = await renderSearchPage()
      const example =
        'Find me a highly rated cardiologist near New York with experience treating heart failure'

      await user.click(screen.getByRole('button', { name: example }))

      expect(input()).toHaveValue(example)
      expect(input()).toHaveFocus()
      expect(parseCalls(fetchSpy)).toHaveLength(0)
      expect(screen.queryByText('Interpreted by AI')).not.toBeInTheDocument()
    })

    it('shows an inline error when parsing fails, and the editor still works', async () => {
      routeFetch({
        'POST /api/v1/ai/parse-query': () =>
          jsonResponse(errorBody('INTERNAL_ERROR', 'An unexpected error occurred'), {
            status: 500,
          }),
      })
      const user = await renderSearchPage()

      await user.type(input(), 'cardiologist{Enter}')

      expect(await screen.findByRole('alert')).toHaveTextContent('An unexpected error occurred')
      expect(screen.getByRole('button', { name: 'Interpret' })).toBeEnabled()
      await user.selectOptions(specialty(), 'cardiology')
      await user.selectOptions(location(), 'Chicago, IL')
      expect(specialty()).toHaveValue('cardiology')
      expect(radius()).toBeEnabled()
    })

    it.each([
      [
        '429',
        () =>
          jsonResponse(errorBody('RATE_LIMITED', 'Rate limit exceeded'), {
            status: 429,
            headers: { 'Retry-After': '30' },
          }),
        'Too many requests. Please wait 30 seconds.',
      ],
      [
        '502',
        () => new Response('<html>Bad Gateway</html>', { status: 502 }),
        "Can't reach the server right now. Please try again in a moment.",
      ],
    ])('shows the friendly message for a %s', async (_status, respond, message) => {
      routeFetch({ 'POST /api/v1/ai/parse-query': respond })
      const user = await renderSearchPage()

      await user.type(input(), 'cardiologist{Enter}')

      expect(await screen.findByRole('alert')).toHaveTextContent(message)
    })
  })

  describe('criteria editor', () => {
    it('reloads conditions for a new specialty and clears one that no longer applies', async () => {
      const fetchSpy = routeFetch()
      const user = await renderSearchPage()

      await user.selectOptions(specialty(), 'cardiology')
      await screen.findByRole('option', { name: 'Atrial fibrillation' })
      await waitFor(() => expect(condition()).toBeEnabled())
      await user.selectOptions(condition(), 'heart-failure')
      expect(condition()).toHaveValue('heart-failure')

      await user.selectOptions(specialty(), 'dermatology')

      await screen.findByRole('option', { name: 'Psoriasis' })
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/conditions?specialty=dermatology',
        expect.anything(),
      )
      await waitFor(() => expect(condition()).toHaveValue(''))
      expect(
        within(condition())
          .getAllByRole('option')
          .map((o) => o.textContent),
      ).toEqual(['Any condition', 'Psoriasis', 'Eczema'])
    })

    it('keeps a condition the new specialty also treats', async () => {
      routeFetch()
      const user = await renderSearchPage()

      await user.selectOptions(condition(), 'heart-failure')
      await user.selectOptions(specialty(), 'cardiology')

      await screen.findByRole('option', { name: 'Atrial fibrillation' })
      expect(condition()).toHaveValue('heart-failure')
    })

    it('disables the radius until a location is chosen', async () => {
      routeFetch()
      const user = await renderSearchPage()

      expect(radius()).toBeDisabled()
      expect(radius()).toHaveAccessibleDescription('Choose a location to set a radius.')

      await user.selectOptions(location(), 'Chicago, IL')

      expect(radius()).toBeEnabled()
      expect(radius()).toHaveValue(25)
      await user.clear(radius())
      await user.type(radius(), '10')
      expect(radius()).toHaveValue(10)
    })

    it('disables distance priority without a location, and resets it when the location is cleared', async () => {
      routeFetch()
      const user = await renderSearchPage()

      expect(priority('Distance')).toBeDisabled()
      expect(priority('Distance')).toHaveAccessibleDescription('Distance needs a location.')

      await user.selectOptions(location(), 'New York, NY')
      expect(priority('Distance')).toBeEnabled()
      await user.click(priority('Distance'))
      expect(priority('Distance')).toBeChecked()

      await user.selectOptions(location(), 'Anywhere')

      expect(priority('Distance')).toBeDisabled()
      expect(priority('Balanced')).toBeChecked()
      expect(radius()).toBeDisabled()
    })

    it('keeps another priority when the location is cleared', async () => {
      routeFetch()
      const user = await renderSearchPage()

      await user.selectOptions(location(), 'New York, NY')
      await user.click(priority('Cost'))
      await user.selectOptions(location(), 'Anywhere')

      expect(priority('Cost')).toBeChecked()
    })
  })

  describe('Search providers', () => {
    it('navigates to /results with the manual criteria', async () => {
      routeFetch()
      const user = await renderSearchPage()

      await user.selectOptions(specialty(), 'cardiology')
      await user.selectOptions(location(), 'New York, NY')
      await user.click(screen.getByRole('checkbox', { name: 'Accepting new patients only' }))
      await user.click(priority('Experience'))
      await user.click(screen.getByRole('button', { name: 'Search providers' }))

      expect(await resultsParams()).toEqual({
        specialty: 'cardiology',
        city: 'New York',
        state: 'NY',
        radius_miles: '25',
        accepting_new_patients: 'true',
        priority: 'experience',
        source: 'manual',
      })
    })

    it('marks interpreted criteria as source=nl with the parser, even after edits', async () => {
      routeFetch({ 'POST /api/v1/ai/parse-query': () => jsonResponse(LLM_RESULT) })
      const user = await renderSearchPage()

      await user.type(input(), 'cardiologist in NYC{Enter}')
      await screen.findByText('Interpreted by AI')
      await waitFor(() => expect(condition()).toHaveValue('heart-failure'))
      await user.click(priority('Cost'))
      await user.click(screen.getByRole('button', { name: 'Search providers' }))

      expect(await resultsParams()).toEqual({
        specialty: 'cardiology',
        condition: 'heart-failure',
        city: 'New York',
        state: 'NY',
        radius_miles: '25',
        min_quality_score: '80',
        priority: 'cost',
        source: 'nl',
        parser_used: 'llm',
      })
    })

    it('goes back to source=manual after Reset', async () => {
      routeFetch({ 'POST /api/v1/ai/parse-query': () => jsonResponse(LLM_RESULT) })
      const user = await renderSearchPage()

      await user.type(input(), 'cardiologist in NYC{Enter}')
      await screen.findByText('Interpreted by AI')
      await user.click(screen.getByRole('button', { name: 'Reset' }))
      await user.click(screen.getByRole('button', { name: 'Search providers' }))

      expect(await resultsParams()).toEqual({ priority: 'balanced', source: 'manual' })
    })
  })

  it('starts from the criteria in its URL, as "Change search" links to', async () => {
    routeFetch()
    const user = await renderSearchPage(
      '/?specialty=cardiology&condition=heart-failure&city=New+York&state=NY&radius_miles=10' +
        '&priority=distance&sort=cost&page=3&source=nl&parser_used=rule_based',
    )

    expect(specialty()).toHaveValue('cardiology')
    await waitFor(() => expect(condition()).toHaveValue('heart-failure'))
    expect(location()).toHaveValue('New York|NY')
    expect(radius()).toHaveValue(10)
    expect(priority('Distance')).toBeChecked()

    await user.click(screen.getByRole('button', { name: 'Search providers' }))

    // Sort and page are left behind; where the criteria came from is kept.
    expect(await resultsParams()).toEqual({
      specialty: 'cardiology',
      condition: 'heart-failure',
      city: 'New York',
      state: 'NY',
      radius_miles: '10',
      priority: 'distance',
      source: 'nl',
      parser_used: 'rule_based',
    })
  })

  it('shows an error when the search options fail to load', async () => {
    routeFetch({
      'GET /api/v1/cities': () =>
        jsonResponse(errorBody('INTERNAL_ERROR', 'An unexpected error occurred', 'req-500'), {
          status: 500,
        }),
    })
    render(
      <MemoryRouter>
        <SearchPage />
      </MemoryRouter>,
    )

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("Couldn't load all search options")
    expect(alert).toHaveTextContent('Request ID: req-500')
    // The rest of the editor still works.
    expect(await screen.findByRole('option', { name: 'Cardiology (162)' })).toBeInTheDocument()
  })

  it('aborts the reference requests when it unmounts', async () => {
    const fetchSpy = mockFetch().mockImplementation(hangingFetch)

    const { unmount } = render(
      <MemoryRouter>
        <SearchPage />
      </MemoryRouter>,
    )
    const signals = fetchSpy.mock.calls.map(([, init]) => init!.signal!)
    expect(signals).toHaveLength(3)
    unmount()

    expect(signals.every((signal) => signal.aborted)).toBe(true)
  })
})
