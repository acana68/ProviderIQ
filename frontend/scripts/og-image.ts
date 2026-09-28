/**
 * Generates the link-preview image (Open Graph / Twitter card) into public/og-image.png:
 * the name, what it does, and a score bar in the app's own colors.
 *
 *   npm run og-image              (from frontend/; needs `npx playwright install chromium`)
 *
 * Rendered from the HTML below, so it's rebuilt, not hand-edited. index.html points at the
 * copy on GitHub, since link previews need an absolute URL.
 */
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const OUT = fileURLToPath(new URL('../public/og-image.png', import.meta.url))
// The size link previews expect (1.91:1).
const SIZE = { width: 1200, height: 630 }

// Colors from src/styles/tokens.css; segment widths are a balanced score's points.
const SEGMENTS = [
  ['#2563a8', 30],
  ['#2f9e8f', 18],
  ['#d08a1e', 14],
  ['#8a63b8', 10],
  ['#5b8c3a', 9],
] as const

const HTML = `<!doctype html>
<html>
<head>
<style>
  * { box-sizing: border-box; margin: 0; }
  body {
    width: ${SIZE.width}px; height: ${SIZE.height}px;
    display: flex; flex-direction: column; justify-content: center;
    padding: 0 96px;
    background: #f6f8fa;
    border-top: 16px solid #2563a8;
    color: #1b2430;
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  }
  h1 { font-size: 104px; font-weight: 600; letter-spacing: -0.02em; }
  p.tagline { margin-top: 20px; font-size: 40px; line-height: 1.3; color: #56626f; max-width: 900px; }
  .bar { display: flex; height: 28px; margin-top: 56px; width: 760px; border-radius: 14px;
         overflow: hidden; background: #e6ebf0; }
  .bar span { height: 100%; }
  p.note { margin-top: 48px; font-size: 26px; color: #56626f; }
</style>
</head>
<body>
  <h1>ProviderIQ</h1>
  <p class="tagline">Find and compare healthcare providers by quality, experience, cost and distance.</p>
  <div class="bar">${SEGMENTS.map(([color, points]) => `<span style="width:${points}%;background:${color}"></span>`).join('')}</div>
  <p class="note">Educational portfolio project · Scores explained, factor by factor</p>
</body>
</html>`

const browser = await chromium.launch()
try {
  const page = await browser.newPage({ viewport: SIZE, deviceScaleFactor: 1 })
  await page.setContent(HTML)
  await page.screenshot({ path: OUT, type: 'png' })
  console.log(`saved ${OUT}`)
} finally {
  await browser.close()
}
