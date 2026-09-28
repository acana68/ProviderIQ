import { defineConfig, devices } from '@playwright/test'

/**
 * Browser checks (e2e/): layout at phone width and a link crawl, on the built app served
 * by `vite preview`, with the API mocked from e2e/fixtures.ts. No backend needed.
 *
 *   npx playwright install chromium   (once)
 *   npm run test:e2e
 */
const PORT = 4173

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run build && npx vite preview --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
