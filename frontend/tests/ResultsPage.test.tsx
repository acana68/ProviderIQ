import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAppAt } from './utils'

/** The summary as { label: value }. */
function summary(): Record<string, string> {
  const rows: Record<string, string> = {}
  for (const term of screen.queryAllByRole('term')) {
    rows[term.textContent ?? ''] = term.nextElementSibling?.textContent ?? ''
  }
  return rows
}

describe('ResultsPage', () => {
  it('summarizes the criteria in the URL', () => {
    renderAppAt(
      '/results?specialty=cardiology&condition=heart-failure&city=New+York&state=NY' +
        '&radius_miles=10&min_quality_score=80&min_years_experience=15' +
        '&accepting_new_patients=true&priority=distance&source=nl&parser_used=llm',
    )

    expect(screen.getByRole('heading', { name: 'Results' })).toBeInTheDocument()
    expect(summary()).toEqual({
      Specialty: 'Cardiology',
      Condition: 'Heart failure',
      Location: 'New York, NY (within 10 mi)',
      'Minimum quality score': '80',
      'Minimum years of experience': '15',
      'Accepting new patients': 'Yes',
      Priority: 'Distance',
      From: 'Your description (interpreted by AI)',
    })
    expect(screen.getByRole('link', { name: 'Change search' })).toHaveAttribute('href', '/')
  })

  it('labels manual and keyword-matched searches', () => {
    renderAppAt('/results?priority=cost&source=manual')
    expect(summary()).toEqual({ Priority: 'Cost', From: 'Manual criteria' })
  })

  it('ignores garbage parameters', () => {
    renderAppAt('/results?specialty=<script>&radius_miles=-1&priority=distance&page=abc&x=1')

    expect(summary()).toEqual({})
    expect(screen.getByText('No filters: all providers.')).toBeInTheDocument()
  })
})
