import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { routeFetch } from './fixtures'
import { renderAppAt } from './utils'

describe('PrivacyPage', () => {
  it('explains, in plain language, what happens to what people type', async () => {
    routeFetch()

    renderAppAt('/privacy')

    expect(await screen.findByRole('heading', { level: 1, name: 'Privacy' })).toBeInTheDocument()
    for (const heading of [
      'No accounts',
      'What you type',
      'What ProviderIQ records',
      'Where the provider data comes from',
      'Not medical advice',
    ]) {
      expect(screen.getByRole('heading', { level: 2, name: heading })).toBeInTheDocument()
    }
    const page = screen.getByRole('article')
    expect(page).toHaveTextContent("sent to Anthropic's API (Claude) for one purpose")
    expect(page).toHaveTextContent("ProviderIQ doesn't store or log that text")
    expect(page).toHaveTextContent('By default the providers are synthetic')
    expect(page).toHaveTextContent('nothing here is medical advice')
    expect(document.title).toBe('Privacy · ProviderIQ')
  })

  it('makes no claim of legal compliance', async () => {
    routeFetch()

    renderAppAt('/privacy')

    const text = (await screen.findByRole('article')).textContent ?? ''
    expect(text).not.toMatch(/HIPAA|GDPR|CCPA|complian/i)
  })
})
