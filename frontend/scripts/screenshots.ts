/**
 * Captures the README screenshots from a running stack into docs/screenshots/.
 *
 *   docker compose up --build        (from the repo root, in another terminal)
 *   npm run screenshots              (from frontend/)
 *
 * It never starts anything itself. The search screenshot makes one real /ai/parse-query
 * call, so the stack needs AI_PROVIDER=anthropic and a key; with the keyword parser the
 * badge would read "Keyword matching" and the script stops instead of saving it.
 * Set SCREENSHOT_BASE_URL to point it somewhere other than http://localhost:8080. It only
 * captures synthetic data: against the real CMS dataset it stops.
 */
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium, type Page } from 'playwright'

const BASE_URL = (process.env.SCREENSHOT_BASE_URL ?? 'http://localhost:8080').replace(/\/$/, '')
const OUT_DIR = fileURLToPath(new URL('../../docs/screenshots/', import.meta.url))
const VIEWPORT = { width: 1280, height: 900 }

const RESULTS_QUERY = new URLSearchParams({
  specialty: 'cardiology',
  condition: 'heart-failure',
  city: 'New York',
  state: 'NY',
  radius_miles: '20',
  priority: 'quality',
})

async function assertStackIsUp() {
  try {
    const response = await fetch(`${BASE_URL}/api/v1/health/ready`, {
      signal: AbortSignal.timeout(5000),
    })
    if (response.ok) return
    throw new Error(`health check returned ${response.status}`)
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error)
    console.error(`The stack at ${BASE_URL} isn't reachable (${reason}).`)
    console.error('Start it from the repo root with `docker compose up --build`, then rerun.')
    process.exit(1)
  }
}

/**
 * The README screenshots show synthetic providers only. Real (CMS) data describes real
 * clinicians, so the script stops rather than publish pictures of them.
 */
async function assertSyntheticData() {
  const response = await fetch(`${BASE_URL}/api/v1/dataset`, { signal: AbortSignal.timeout(5000) })
  const dataset = (await response.json()) as { source?: string }
  if (dataset.source === 'synthetic') return
  console.error(`The stack is serving ${dataset.source ?? 'unknown'} data, not synthetic.`)
  console.error(
    'Switch back with: docker compose exec backend python -m scripts.seed_db --source synthetic',
  )
  process.exit(1)
}

/** `height`: crop to this many pixels from the top of the page instead of the viewport. */
async function save(page: Page, name: string, options: { fullPage?: boolean; height?: number }) {
  const path = `${OUT_DIR}${name}`
  const clip = options.height
    ? { x: 0, y: 0, width: VIEWPORT.width, height: options.height }
    : undefined
  await page.screenshot({
    path,
    fullPage: options.fullPage ?? clip !== undefined,
    clip,
    animations: 'disabled',
    caret: 'hide',
  })
  console.log(`saved ${name}`)
}

async function searchPage(page: Page) {
  await page.goto(`${BASE_URL}/`)
  await page.getByRole('button', { name: /cardiologist near New York/ }).click()
  await page.getByRole('button', { name: 'Interpret', exact: true }).click()

  const badge = page.getByText(/^(Interpreted by AI|Keyword matching)$/)
  await badge.waitFor({ timeout: 20_000 })
  if ((await badge.textContent()) !== 'Interpreted by AI') {
    throw new Error(
      'The keyword parser answered, not the AI. Set AI_PROVIDER=anthropic and ' +
        'ANTHROPIC_API_KEY in .env, restart the backend, and rerun.',
    )
  }
  // The filters the parse should have filled in.
  for (const label of ['Specialty', 'Condition', 'Location']) {
    const value = await page.getByLabel(label, { exact: true }).inputValue()
    if (!value) throw new Error(`Interpret left "${label}" empty`)
  }
  await page.mouse.move(0, 0)
  await save(page, 'search.png', { fullPage: true })
}

async function resultsPage(page: Page) {
  await page.goto(`${BASE_URL}/results?${RESULTS_QUERY}`)
  // End just below the second card rather than cutting it off at the viewport edge.
  const secondCard = await page.getByRole('article').nth(1).boundingBox()
  if (!secondCard) throw new Error('Expected at least two results')
  await save(page, 'results.png', { height: Math.ceil(secondCard.y + secondCard.height + 8) })
}

/** Opens the top result the way a user would, so the page carries the search context. */
async function detailPage(page: Page) {
  await page.getByRole('article').first().getByRole('link').click()
  await page.getByRole('table', { name: 'Score breakdown' }).waitFor()
  await save(page, 'detail.png', { fullPage: true })
}

async function methodologyPage(page: Page) {
  await page.goto(`${BASE_URL}/methodology`)
  await page.getByRole('heading', { name: 'Methodology', level: 1 }).waitFor()
  // The weight table is loaded from /ranking/weights; wait for it so the page is complete.
  await page.getByRole('table').first().waitFor()
  await save(page, 'methodology.png', {})
}

async function main() {
  await assertStackIsUp()
  await assertSyntheticData()
  await mkdir(OUT_DIR, { recursive: true })

  const browser = await chromium.launch()
  try {
    const page = await browser.newPage({ viewport: VIEWPORT, colorScheme: 'light' })
    await searchPage(page)
    await resultsPage(page)
    await detailPage(page)
    await methodologyPage(page)
  } finally {
    await browser.close()
  }
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error)
  process.exit(1)
})
