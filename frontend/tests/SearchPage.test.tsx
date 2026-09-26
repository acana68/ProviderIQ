import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { SearchPage } from '../src/pages/SearchPage'
import type { SpecialtySummary } from '../src/types/provider'
import { errorBody, hangingFetch, jsonResponse, mockFetch } from './utils'

const SPECIALTIES: SpecialtySummary[] = [
  { id: 1, slug: 'cardiology', name: 'Cardiology', provider_count: 162 },
  { id: 3, slug: 'dermatology', name: 'Dermatology', provider_count: 134 },
]

describe('SearchPage', () => {
  it('shows loading, then the specialties from the API', async () => {
    let respond: (response: Response) => void = () => {}
    const fetchSpy = mockFetch().mockReturnValue(
      new Promise<Response>((resolve) => {
        respond = resolve
      }),
    )

    render(<SearchPage />)

    expect(screen.getByRole('status')).toHaveTextContent('Loading specialties…')
    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/specialties', expect.anything())

    respond(jsonResponse(SPECIALTIES))

    const select = await screen.findByRole('combobox', { name: 'Specialty' })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    const options = within(select)
      .getAllByRole('option')
      .map((option) => option.textContent)
    expect(options).toEqual(['Any specialty', 'Cardiology (162)', 'Dermatology (134)'])
  })

  it('lets the user pick a specialty', async () => {
    mockFetch().mockResolvedValue(jsonResponse(SPECIALTIES))
    const user = userEvent.setup()
    render(<SearchPage />)

    const select = await screen.findByRole('combobox', { name: 'Specialty' })
    await user.selectOptions(select, 'Cardiology (162)')

    expect(select).toHaveValue('cardiology')
  })

  it('shows the error and its request ID when the API fails', async () => {
    mockFetch().mockResolvedValue(
      jsonResponse(errorBody('INTERNAL_ERROR', 'An unexpected error occurred', 'req-500'), {
        status: 500,
      }),
    )

    render(<SearchPage />)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("Couldn't load specialties")
    expect(alert).toHaveTextContent('An unexpected error occurred')
    expect(alert).toHaveTextContent('Request ID: req-500')
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('shows an empty state when there are no specialties', async () => {
    mockFetch().mockResolvedValue(jsonResponse([]))

    render(<SearchPage />)

    expect(await screen.findByText('No specialties yet')).toBeInTheDocument()
  })

  it('aborts the request when it unmounts', () => {
    const fetchSpy = mockFetch().mockImplementation(hangingFetch)

    const { unmount } = render(<SearchPage />)
    const signal = fetchSpy.mock.calls[0]![1]!.signal!
    expect(signal.aborted).toBe(false)
    unmount()

    expect(signal.aborted).toBe(true)
  })
})
