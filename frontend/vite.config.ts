import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The app always calls relative "/api/v1/..." URLs, never a hardcoded host. In development
// Vite forwards them to FastAPI; in production CloudFront routes /api/* to the backend on
// the same domain. Same origin in both cases, so there's no CORS to configure and nothing
// environment-specific in the frontend code.
const apiProxy = {
  '/api': { target: 'http://localhost:8000' },
}

// https://vite.dev/config/ (vitest/config's defineConfig also accepts the `test` block)
export default defineConfig({
  plugins: [react()],
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.{ts,tsx}'],
    setupFiles: ['./tests/setup.ts'],
    // Undo every vi.spyOn (e.g. on fetch) after each test.
    restoreMocks: true,
  },
})
