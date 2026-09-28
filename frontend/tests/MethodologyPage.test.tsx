import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { RankingWeightsResponse } from '../src/types/ranking'
import { routeFetch } from './fixtures'
import { errorBody, jsonResponse, renderAppAt, tableRows } from './utils'

const WEIGHTS_URL = 'GET /api/v1/ranking/weights'

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

describe('MethodologyPage', () => {
  it('renders the weight table from /ranking/weights', async () => {
    const fetchSpy = routeFetch({ [WEIGHTS_URL]: () => jsonResponse(WEIGHTS) })

    renderAppAt('/methodology')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Methodology' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Loading the weights…')).toBeInTheDocument()
    const table = await screen.findByRole('table', { name: 'Weight of each factor, by priority' })
    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/ranking/weights', expect.anything())
    expect(tableRows(table)).toEqual([
      ['Priority', 'Quality', 'Experience', 'Cost', 'Volume', 'Distance'],
      ['Balanced', '35%', '20%', '15%', '15%', '15%'],
      ['Quality', '55%', '20%', '5%', '10%', '10%'],
      ['Cost', '25%', '10%', '45%', '5%', '15%'],
      ['Experience', '25%', '45%', '10%', '10%', '10%'],
      ['Distance', '25%', '10%', '10%', '5%', '50%'],
    ])
    expect(screen.getByText(/Quality never drops below 25%\./)).toBeInTheDocument()
  })

  it('shows an error with the request ID, and Retry loads the weights', async () => {
    let calls = 0
    routeFetch({
      [WEIGHTS_URL]: () => {
        calls += 1
        return calls === 1
          ? jsonResponse(errorBody('INTERNAL_ERROR', 'An unexpected error occurred', 'req-w'), {
              status: 500,
            })
          : jsonResponse(WEIGHTS)
      },
    })
    const user = userEvent.setup()

    renderAppAt('/methodology')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("Couldn't load the weights")
    expect(alert).toHaveTextContent('Request ID: req-w')
    // The rest of the page doesn't depend on the weights.
    expect(screen.getByRole('heading', { name: 'The five factors' })).toBeInTheDocument()

    await user.click(within(alert).getByRole('button', { name: 'Try again' }))

    expect(
      await screen.findByRole('table', { name: 'Weight of each factor, by priority' }),
    ).toBeInTheDocument()
  })

  it('covers every section, the factor table and the repo link', async () => {
    routeFetch({ [WEIGHTS_URL]: () => jsonResponse(WEIGHTS) })

    renderAppAt('/methodology')

    await screen.findByRole('heading', { level: 1, name: 'Methodology' })
    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(headings).toEqual([
      'What ProviderIQ is',
      'How AI is used',
      'The five factors',
      'Priorities and weights',
      'How "Stands out for…" is chosen',
      'Limitations',
    ])
    const toc = screen.getByRole('navigation', { name: 'On this page' })
    expect(within(toc).getAllByRole('link')).toHaveLength(headings.length)

    const factors = screen.getByRole('table', { name: 'How each factor is scored' })
    expect(
      within(factors)
        .getAllByRole('rowheader')
        .map((h) => h.textContent),
    ).toEqual(['Quality', 'Experience', 'Cost', 'Volume', 'Distance'])
    expect(screen.getByRole('link', { name: 'GitHub' })).toHaveAttribute(
      'href',
      'https://github.com/acana68/ProviderIQ',
    )
    await screen.findByRole('table', { name: 'Weight of each factor, by priority' })
  })
})
