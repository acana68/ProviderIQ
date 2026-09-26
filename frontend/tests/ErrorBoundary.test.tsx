import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link, MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { AppLayout } from '../src/components/layout/AppLayout'
import { DISCLAIMER_TEXT } from '../src/components/layout/Disclaimer'

function Boom(): never {
  throw new Error('kaboom')
}

function renderLayoutAt(path: string) {
  // React and the boundary both log the caught error; keep the test output clean.
  const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<h1>Home</h1>} />
          <Route path="boom" element={<Boom />} />
          <Route
            path="fine"
            element={
              <>
                <h1>Fine</h1>
                <Link to="/boom">Break it</Link>
              </>
            }
          />
          <Route path="*" element={<h1>Other page</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
  return { consoleError, user }
}

describe('ErrorBoundary', () => {
  it('shows the fallback for a crashing page, keeping the header and disclaimer', () => {
    const { consoleError } = renderLayoutAt('/boom')

    const fallback = screen.getByRole('alert')
    expect(fallback).toHaveTextContent('Something went wrong on this page.')
    expect(screen.getByRole('button', { name: 'Go to home' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'ProviderIQ' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent(DISCLAIMER_TEXT)
    expect(consoleError).toHaveBeenCalledWith(
      'Page crashed:',
      expect.objectContaining({ message: 'kaboom' }),
      expect.any(String),
    )
  })

  it('"Go to home" navigates away and clears the error', async () => {
    const { user } = renderLayoutAt('/boom')

    await user.click(screen.getByRole('button', { name: 'Go to home' }))

    expect(screen.getByRole('heading', { name: 'Home' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('resets when the route changes, e.g. from the header link', async () => {
    const { user } = renderLayoutAt('/boom')
    expect(screen.getByRole('alert')).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Methodology' }))

    expect(screen.getByRole('heading', { name: 'Other page' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'ProviderIQ' }))
    expect(screen.getByRole('heading', { name: 'Home' })).toBeInTheDocument()
  })

  it('catches a page that crashes after navigation, too', async () => {
    const { user } = renderLayoutAt('/fine')

    await user.click(screen.getByRole('link', { name: 'Break it' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong on this page.')
  })

  it('Reload reloads the page', async () => {
    const reload = vi.fn()
    vi.spyOn(window, 'location', 'get').mockReturnValue({ ...window.location, reload })
    const { user } = renderLayoutAt('/boom')

    await user.click(screen.getByRole('button', { name: 'Reload' }))

    expect(reload).toHaveBeenCalled()
  })
})
