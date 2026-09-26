import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  // Testing Library only cleans up automatically when test globals are enabled; they aren't.
  cleanup()
  vi.useRealTimers()
})
