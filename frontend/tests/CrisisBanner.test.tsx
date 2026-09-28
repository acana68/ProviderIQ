import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { ParseQueryResponse } from '../src/types/search'
import { requestBodies, routeFetch } from './fixtures'
import { jsonResponse, renderAppAt } from './utils'

const BANNER_TEXT =
  "If you're thinking about hurting yourself, you don't have to go through it alone. " +
  'Call or text 988 (Suicide & Crisis Lifeline, US). ' +
  "If you're in immediate danger, call 911."

function parsed(crisis: boolean): ParseQueryResponse {
  return {
    criteria: {
      specialty: 'cardiology',
      condition: null,
      location: { city: 'New York', state: 'NY' },
      radius_miles: null,
      min_quality_score: null,
      min_years_experience: null,
      accepting_new_patients: null,
      priority: null,
    },
    parser_used: 'rule_based',
    warnings: [],
    crisis,
  }
}

/** The search page in the whole app, answering parse-query with each response in turn. */
async function renderSearch(...responses: ParseQueryResponse[]) {
  const fetchSpy = routeFetch({
    'POST /api/v1/ai/parse-query': () => jsonResponse(responses.shift()),
    'POST /api/v1/search': () => new Promise<Response>(() => {}),
  })
  const user = userEvent.setup()
  renderAppAt('/')
  await screen.findByRole('option', { name: 'Cardiology (162)' })
  await screen.findByRole('option', { name: 'New York, NY' })
  return { user, fetchSpy }
}

const input = () =>
  screen.getByRole('textbox', { name: "Describe the provider you're looking for" })
const banner = () => screen.queryByRole('alert', { name: 'Crisis support' })

describe('crisis banner', () => {
  it('appears above the page, with the helpline, when the query is flagged', async () => {
    const { user } = await renderSearch(parsed(true))

    await user.type(input(), 'I want to hurt myself, heart doctor in NYC{Enter}')

    const alert = await screen.findByRole('alert', { name: 'Crisis support' })
    expect(alert).toHaveTextContent(BANNER_TEXT)
    expect(within(alert).getByRole('link', { name: '988' })).toHaveAttribute('href', 'tel:988')
    expect(within(alert).getByRole('link', { name: '911' })).toHaveAttribute('href', 'tel:911')
    // First in the page column: before the page's own heading.
    const heading = screen.getByRole('heading', { level: 1, name: 'ProviderIQ' })
    expect(alert.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('leaves the criteria and the search working', async () => {
    const { user, fetchSpy } = await renderSearch(parsed(true))

    await user.type(input(), 'I want to hurt myself, heart doctor in NYC{Enter}')
    await screen.findByRole('alert', { name: 'Crisis support' })
    await waitFor(() =>
      expect(screen.getByRole('combobox', { name: 'Specialty' })).toHaveValue('cardiology'),
    )
    await user.click(screen.getByRole('button', { name: 'Search providers' }))

    await waitFor(() => expect(requestBodies(fetchSpy, '/api/v1/search')).toHaveLength(1))
    const [body] = requestBodies(fetchSpy, '/api/v1/search')
    expect(body).toMatchObject({ specialty: 'cardiology', source: 'nl' })
    // Nothing about the crisis goes to the server with the search.
    expect(JSON.stringify(body)).not.toContain('crisis')
    // Still shown on the results page.
    expect(banner()).toBeInTheDocument()
  })

  it("doesn't appear for an ordinary query", async () => {
    const { user } = await renderSearch(parsed(false))

    await user.type(input(), 'heart doctor in NYC{Enter}')

    await screen.findByText('Keyword matching')
    expect(banner()).not.toBeInTheDocument()
  })

  it('stays once shown, even if a later query is not flagged', async () => {
    const { user } = await renderSearch(parsed(true), parsed(false))

    await user.type(input(), 'I want to hurt myself{Enter}')
    await screen.findByRole('alert', { name: 'Crisis support' })
    await user.clear(input())
    await user.type(input(), 'heart doctor in NYC{Enter}')
    await screen.findByText('Keyword matching')

    expect(banner()).toBeInTheDocument()
  })
})
