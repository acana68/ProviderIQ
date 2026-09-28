/**
 * Link crawl: follows every internal link from the app's pages and fails on one that leads
 * to a "not found" page or to a #fragment that doesn't exist. Every GitHub link is also
 * requested for real (the only external links checked; others would make CI depend on
 * third-party sites). Both datasets, since their pages link to different sections.
 */
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { DATASETS, type DatasetName } from './fixtures'
import { mockApi } from './mockApi'

/** Pages to start from; the rest are found by following links. */
function seeds(dataset: DatasetName): string[] {
  const { city, state } = DATASETS[dataset].cities[0]!
  return [
    '/',
    `/results?${new URLSearchParams({ specialty: 'cardiology', city, state })}`,
    '/methodology',
    '/privacy',
    // Not a broken link itself: it's here so its own links get checked.
    '/no/such/page',
  ]
}
const NOT_FOUND = /^(Page|Provider) not found$/
const MAX_PAGES = 60

interface FoundLink {
  href: string
  text: string
}

async function linksOn(page: Page): Promise<FoundLink[]> {
  return page.locator('a[href]').evaluateAll((anchors) =>
    anchors.map((a) => ({
      href: (a as HTMLAnchorElement).href,
      text: (a.textContent ?? '').trim().slice(0, 60),
    })),
  )
}

/** Visit a URL and wait until its content (not a loading state) is in. */
async function open(page: Page, url: string) {
  await page.goto(url)
  await page.waitForLoadState('networkidle')
  await page.getByRole('heading', { level: 1 }).first().waitFor()
}

/**
 * A GitHub link's HTTP status. GitHub answers 429 to bursts of unauthenticated requests
 * (both datasets' crawls run at once), so a 429 is retried after a pause and, if it
 * persists, reported as rate-limited rather than broken.
 */
async function githubStatus(request: APIRequestContext, href: string) {
  for (let attempt = 0; attempt < 4; attempt++) {
    const response = await request.head(href, { maxRedirects: 5, timeout: 20_000 })
    if (response.status() !== 429) return response.status()
    const retryAfter = Number(response.headers()['retry-after'])
    await new Promise((resolve) =>
      setTimeout(
        resolve,
        1000 * (retryAfter > 0 && retryAfter <= 30 ? retryAfter : 5 * (attempt + 1)),
      ),
    )
  }
  return 'rate-limited' as const
}

async function fragmentExists(page: Page, hash: string): Promise<boolean> {
  const id = decodeURIComponent(hash.slice(1))
  return page.evaluate((target) => document.getElementById(target) !== null, id)
}

for (const dataset of Object.keys(DATASETS) as DatasetName[]) {
  test(`${dataset} data: no broken internal or GitHub links`, async ({
    page,
    request,
    baseURL,
  }) => {
    test.setTimeout(120_000)
    const unexpected = await mockApi(page, DATASETS[dataset])
    const origin = new URL(baseURL!).origin
    const queue = [...seeds(dataset)]
    const visited = new Set<string>()
    const github = new Map<string, string>() // href -> the page it was found on
    const crossPageAnchors = new Map<string, string>() // path#id -> the page linking to it
    const broken: string[] = []

    while (queue.length > 0 && visited.size < MAX_PAGES) {
      const pagePath = queue.shift()!
      if (visited.has(pagePath)) continue
      visited.add(pagePath)

      await open(page, pagePath)
      const heading = (await page.getByRole('heading', { level: 1 }).first().textContent()) ?? ''
      if (NOT_FOUND.test(heading.trim()) && pagePath !== '/no/such/page') {
        broken.push(`${pagePath}: shows "${heading.trim()}"`)
        continue
      }

      for (const { href, text } of await linksOn(page)) {
        const url = new URL(href)
        if (url.hostname === 'github.com') {
          if (!github.has(href)) github.set(href, pagePath)
          continue
        }
        if (url.origin !== origin) continue // tel:, sms:, other sites
        const target = `${url.pathname}${url.search}`
        if (url.hash && target === pagePath) {
          if (!(await fragmentExists(page, url.hash))) {
            broken.push(`${pagePath}: "${text}" -> ${url.hash} (no such id)`)
          }
        } else if (url.hash && !crossPageAnchors.has(`${target}${url.hash}`)) {
          crossPageAnchors.set(`${target}${url.hash}`, pagePath)
        }
        if (!visited.has(target)) queue.push(target)
      }
    }

    // Anchors into other pages ("About the real data" -> /methodology#real-data).
    for (const [anchor, foundOn] of crossPageAnchors) {
      const hashAt = anchor.indexOf('#')
      await open(page, anchor.slice(0, hashAt))
      if (!(await fragmentExists(page, anchor.slice(hashAt)))) {
        broken.push(`${foundOn}: -> ${anchor} (no such id)`)
      }
    }

    for (const [href, foundOn] of github) {
      const status = await githubStatus(request, href)
      if (status === 'rate-limited') {
        // Says nothing about the link either way; noted in the report, not failed.
        test.info().annotations.push({ type: 'warning', description: `${href}: rate limited` })
      } else if (status >= 400) {
        broken.push(`${foundOn}: ${href} -> HTTP ${status}`)
      }
    }

    expect(broken, 'broken links').toEqual([])
    expect(github.size, 'GitHub links found').toBeGreaterThan(0)
    expect(visited.size, 'pages crawled').toBeGreaterThan(5)
    expect(unexpected, 'API requests the fixture does not answer').toEqual([])
  })
}
