import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { AppLayout } from '../src/components/layout/AppLayout'
import { DISCLAIMER_TEXT } from '../src/components/layout/Disclaimer'

function renderLayout() {
  render(
    <MemoryRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<p>Page content</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('AppLayout', () => {
  it('renders the disclaimer', () => {
    renderLayout()

    expect(screen.getByRole('note')).toHaveTextContent(
      'Educational portfolio project. All provider data is synthetic. Not medical advice.',
    )
  })

  it('renders the home link and navigation', () => {
    renderLayout()

    expect(screen.getByRole('link', { name: 'ProviderIQ' })).toHaveAttribute('href', '/')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { name: 'Methodology' })).toHaveAttribute(
      'href',
      '/methodology',
    )
  })

  it('links to the privacy page and the source code in the footer', () => {
    renderLayout()

    const footer = screen.getByRole('navigation', { name: 'Footer' })
    expect(within(footer).getByRole('link', { name: 'Privacy' })).toHaveAttribute(
      'href',
      '/privacy',
    )
    expect(within(footer).getByRole('link', { name: 'GitHub' })).toHaveAttribute(
      'href',
      'https://github.com/acana68/ProviderIQ',
    )
  })

  it('renders the routed page inside main', () => {
    renderLayout()

    expect(within(screen.getByRole('main')).getByText('Page content')).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent(DISCLAIMER_TEXT)
  })
})
