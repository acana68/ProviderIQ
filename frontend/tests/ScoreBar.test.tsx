import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ScoreBar } from '../src/components/results/ScoreBar'
import type { ProviderScore } from '../src/types/provider'

const SCORE: ProviderScore = {
  overall: 82.4,
  // Rounded separately by the API, so they sum to 82.3.
  components: [
    { name: 'quality', raw: 88.5, normalized: 0.885, weight: 0.35, contribution: 31.1 },
    { name: 'experience', raw: 15, normalized: 0.8, weight: 0.2, contribution: 16 },
    { name: 'cost', raw: 0.88, normalized: 0.705, weight: 0.2, contribution: 14.1 },
    { name: 'volume', raw: 0.6, normalized: 0.6, weight: 0.1, contribution: 6 },
    { name: 'distance', raw: 6.2, normalized: 1, weight: 0.15, contribution: 15.1 },
  ],
}

function segments(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>('[data-component]'))
}

describe('ScoreBar', () => {
  it('renders one segment per component, in order', () => {
    const { container } = render(<ScoreBar score={SCORE} />)

    expect(segments(container).map((s) => s.dataset.component)).toEqual([
      'quality',
      'experience',
      'cost',
      'volume',
      'distance',
    ])
  })

  it('labels the bar with every contribution', () => {
    render(<ScoreBar score={SCORE} />)

    expect(screen.getByRole('img')).toHaveAccessibleName(
      'Score breakdown, 82.4 out of 100: Quality 31.1, Experience 16.0, Cost 14.1, ' +
        'Volume 6.0, Distance 15.1',
    )
  })

  it('sizes segments by contribution, so they fill the overall score', () => {
    const { container } = render(<ScoreBar score={SCORE} />)

    const widths = segments(container).map((s) => parseFloat(s.style.width))
    expect(widths).toEqual([31.1, 16, 14.1, 6, 15.1])
    const total = widths.reduce((sum, width) => sum + width, 0)
    // Within the API's rounding of the separate contributions.
    expect(Math.abs(total - SCORE.overall)).toBeLessThanOrEqual(0.3)
  })

  it('has no distance segment without a location', () => {
    const score: ProviderScore = {
      overall: 70,
      components: SCORE.components
        .filter((c) => c.name !== 'distance')
        .map((c) => ({ ...c, contribution: 17.5 })),
    }
    const { container } = render(<ScoreBar score={score} />)

    expect(segments(container)).toHaveLength(4)
    expect(screen.getByRole('img')).not.toHaveAccessibleName(/Distance/)
  })
})
