import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DISCLAIMER_TEXT } from '../src/components/layout/Disclaimer'
import { errorBody, hangingFetch, jsonResponse, mockFetch, renderAppAt } from './utils'

describe('routing', () => {
  it('renders NotFoundPage for an unknown URL, inside the layout', () => {
    renderAppAt('/no/such/page')

    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to search' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('note')).toHaveTextContent(DISCLAIMER_TEXT)
  })

  it('passes the provider id from the URL', async () => {
    const fetchSpy = mockFetch().mockImplementation(async () =>
      jsonResponse(errorBody('NOT_FOUND', 'Provider not found'), { status: 404 }),
    )

    renderAppAt('/providers/42')

    expect(await screen.findByRole('heading', { name: 'Provider not found' })).toBeInTheDocument()
    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/providers/42', expect.anything())
  })

  it('renders /methodology', () => {
    mockFetch().mockImplementation(hangingFetch)

    renderAppAt('/methodology')

    expect(screen.getByRole('heading', { name: 'Methodology', level: 1 })).toBeInTheDocument()
  })

  it('renders /results', async () => {
    const emptySearch = { items: [], page: 1, page_size: 20, total: 0, total_pages: 0 }
    mockFetch().mockImplementation(async (input) =>
      jsonResponse(String(input).endsWith('/search') ? emptySearch : []),
    )

    renderAppAt('/results')

    expect(screen.getByRole('heading', { name: 'Results', level: 1 })).toBeInTheDocument()
    expect(await screen.findByText('No providers match your search')).toBeInTheDocument()
  })

  it('renders the search page at /', async () => {
    // A fresh Response per call: the page loads specialties, conditions and cities.
    mockFetch().mockImplementation(async () => jsonResponse([]))

    renderAppAt('/')

    expect(screen.getByRole('heading', { name: 'ProviderIQ', level: 1 })).toBeInTheDocument()
    expect(await screen.findByRole('option', { name: 'Any specialty' })).toBeInTheDocument()
  })
})
