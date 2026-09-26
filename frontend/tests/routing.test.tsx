import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DISCLAIMER_TEXT } from '../src/components/layout/Disclaimer'
import { jsonResponse, mockFetch, renderAppAt } from './utils'

describe('routing', () => {
  it('renders NotFoundPage for an unknown URL, inside the layout', () => {
    renderAppAt('/no/such/page')

    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to search' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('note')).toHaveTextContent(DISCLAIMER_TEXT)
  })

  it('passes the provider id from the URL', () => {
    renderAppAt('/providers/42')

    expect(screen.getByRole('heading', { name: 'Provider 42' })).toBeInTheDocument()
  })

  it.each([
    ['/methodology', 'Methodology'],
    ['/results', 'Results'],
  ])('renders %s', (path, heading) => {
    renderAppAt(path)

    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()
  })

  it('renders the search page at /', async () => {
    // A fresh Response per call: the page loads specialties, conditions and cities.
    mockFetch().mockImplementation(async () => jsonResponse([]))

    renderAppAt('/')

    expect(screen.getByRole('heading', { name: 'ProviderIQ', level: 1 })).toBeInTheDocument()
    expect(await screen.findByRole('option', { name: 'Any specialty' })).toBeInTheDocument()
  })
})
