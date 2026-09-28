/**
 * At 375px (a small phone), no page may scroll sideways: the document can be no wider than
 * the viewport. Wide content (tables) has to scroll inside its own container instead.
 * Every page, for both datasets.
 */
import { expect, test, type Page } from '@playwright/test'
import { DATASETS, type DatasetName } from './fixtures'
import { mockApi } from './mockApi'

const WIDTH = 375

test.use({
  viewport: { width: WIDTH, height: 812 },
  isMobile: true,
  hasTouch: true,
  deviceScaleFactor: 2,
})

/** The document's width, and what sticks out past the viewport outside a scroll box. */
async function measure(page: Page) {
  return page.evaluate((limit) => {
    const width = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)
    const insideScrollBox = (el: Element) => {
      for (let node = el.parentElement; node; node = node.parentElement) {
        if (['auto', 'scroll', 'hidden', 'clip'].includes(getComputedStyle(node).overflowX)) {
          return node !== document.body && node !== document.documentElement
        }
      }
      return false
    }
    const offenders = Array.from(document.querySelectorAll('body *'))
      .filter((el) => el.getBoundingClientRect().right > limit + 0.5 && !insideScrollBox(el))
      .slice(0, 10)
      .map((el) => {
        const cls = typeof el.className === 'string' && el.className ? `.${el.className}` : ''
        const text = (el.textContent ?? '').trim().slice(0, 40)
        return `${el.tagName.toLowerCase()}${cls} (${Math.round(el.getBoundingClientRect().right)}px) "${text}"`
      })
    return { width, offenders }
  }, WIDTH)
}

async function expectNoSidewaysScroll(page: Page) {
  const { width, offenders } = await measure(page)
  expect(offenders, `elements wider than ${WIDTH}px`).toEqual([])
  expect(width, 'document width').toBeLessThanOrEqual(WIDTH)
}

interface PageCase {
  name: string
  /** Navigate and wait until the page's content is in. */
  open: (page: Page) => Promise<void>
}

async function resultsWithLocation(page: Page, dataset: DatasetName) {
  const { city, state } = DATASETS[dataset].cities[0]!
  await page.goto(`/results?${new URLSearchParams({ specialty: 'cardiology', city, state })}`)
  await page.getByRole('article').first().waitFor()
}

/** The first result's own link, so the detail page gets the search's context. */
async function firstDetailUrl(page: Page, dataset: DatasetName): Promise<string> {
  await resultsWithLocation(page, dataset)
  const href = await page
    .getByRole('article')
    .first()
    .getByRole('link')
    .first()
    .getAttribute('href')
  expect(href).toBeTruthy()
  return href!
}

function pageCases(dataset: DatasetName): PageCase[] {
  const firstId = [...DATASETS[dataset].details.keys()][0]!
  return [
    {
      name: 'search',
      open: async (page) => {
        await page.goto('/')
        await page.getByRole('option', { name: /^Cardiology/ }).waitFor({ state: 'attached' })
      },
    },
    {
      name: 'search, after Interpret, with the crisis banner and notes',
      open: async (page) => {
        await page.goto('/')
        await page.getByRole('option', { name: /^Cardiology/ }).waitFor({ state: 'attached' })
        await page
          .getByRole('textbox', { name: "Describe the provider you're looking for" })
          .fill('I want to hurt myself, need a heart doctor nearby')
        await page.getByRole('button', { name: 'Interpret', exact: true }).click()
        await page.getByRole('alert', { name: 'Crisis support' }).waitFor()
        await page.getByRole('list', { name: 'Notes' }).waitFor()
      },
    },
    { name: 'results with a location', open: (page) => resultsWithLocation(page, dataset) },
    {
      name: 'results without a location',
      open: async (page) => {
        await page.goto('/results?specialty=cardiology')
        await page.getByRole('article').first().waitFor()
      },
    },
    {
      name: 'provider detail, scored',
      open: async (page) => {
        await page.goto(await firstDetailUrl(page, dataset))
        await page.getByRole('table', { name: 'Score breakdown' }).waitFor()
      },
    },
    {
      name: 'provider detail, unscored',
      open: async (page) => {
        await page.goto(`/providers/${firstId}`)
        await page.getByRole('heading', { level: 1 }).waitFor()
      },
    },
    {
      name: 'methodology',
      open: async (page) => {
        await page.goto('/methodology')
        await page.getByRole('table', { name: 'Weight of each factor, by priority' }).waitFor()
      },
    },
    {
      name: 'privacy',
      open: async (page) => {
        await page.goto('/privacy')
        await page.getByRole('heading', { level: 1, name: 'Privacy' }).waitFor()
      },
    },
    {
      name: 'not found',
      open: async (page) => {
        await page.goto('/no/such/page')
        await page.getByRole('heading', { level: 1, name: 'Page not found' }).waitFor()
      },
    },
  ]
}

for (const dataset of Object.keys(DATASETS) as DatasetName[]) {
  test.describe(`${dataset} data at ${WIDTH}px`, () => {
    for (const { name, open } of pageCases(dataset)) {
      test(`${name}: no sideways scrolling`, async ({ page }) => {
        const unexpected = await mockApi(page, DATASETS[dataset])

        await open(page)

        await expectNoSidewaysScroll(page)
        expect(unexpected, 'API requests the fixture does not answer').toEqual([])
      })
    }
  })
}

test.describe('the width check itself', () => {
  async function privacyPageWith(page: Page, html: string) {
    await mockApi(page, DATASETS.synthetic)
    await page.goto('/privacy')
    await page.getByRole('heading', { level: 1, name: 'Privacy' }).waitFor()
    await page.evaluate((markup) => {
      document.querySelector('main')!.insertAdjacentHTML('beforeend', markup)
    }, html)
    return measure(page)
  }

  test('catches content wider than the viewport', async ({ page }) => {
    const { width, offenders } = await privacyPageWith(
      page,
      '<div style="width: 600px">too wide</div>',
    )

    expect(width).toBeGreaterThan(WIDTH)
    expect(offenders.join('\n')).toContain('too wide')
  })

  test('allows wide content inside its own scroll box', async ({ page }) => {
    const { width, offenders } = await privacyPageWith(
      page,
      '<div style="overflow-x: auto"><div style="width: 600px">wide table</div></div>',
    )

    expect(offenders).toEqual([])
    expect(width).toBeLessThanOrEqual(WIDTH)
  })
})

for (const dataset of Object.keys(DATASETS) as DatasetName[]) {
  test(`${dataset} data at ${WIDTH}px: wide tables scroll in their own box, reachable by keyboard`, async ({
    page,
  }) => {
    await mockApi(page, DATASETS[dataset])
    // The numeric tables, whose columns can't wrap. (The factor table's prose wraps, so it
    // fits, and is then a plain div without a tab stop.)
    const tables = [
      { url: await firstDetailUrl(page, dataset), name: 'Score breakdown' },
      { url: '/methodology', name: 'Weight of each factor, by priority' },
    ]
    for (const { url, name } of tables) {
      await page.goto(url)
      const box = page.getByRole('region', { name })
      await expect(box, `${name} scrolls in its own box`).toBeVisible()
      await expect(box).toHaveAttribute('tabindex', '0')
      const { scrollWidth, clientWidth } = await box.evaluate((el) => ({
        scrollWidth: el.scrollWidth,
        clientWidth: el.clientWidth,
      }))
      expect(scrollWidth).toBeGreaterThan(clientWidth)
      expect(clientWidth).toBeLessThanOrEqual(WIDTH)
    }
  })
}
