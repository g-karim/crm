import { expect, test, type Page } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/*', (route) => {
    const url = new URL(route.request().url())
    return url.hostname === '127.0.0.1' ? route.continue() : route.abort()
  })
})

test('sizes a document with two images by its content', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 840, height: 720 })
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/tests/browser/messenger-bubbles.html?case=file-images')
  await expect(page.locator('[data-message-bubble]')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  const sizes = await page
    .locator('[data-message-bubble]')
    .evaluate((element) => ({
      bubble: element.getBoundingClientRect().width,
      renderer: element
        .querySelector('[data-attachment-renderer]')!
        .getBoundingClientRect().width,
      card: element
        .querySelector('[data-attachment-card]')!
        .getBoundingClientRect().width,
      grid: element.querySelector('[data-image-grid]')!.getBoundingClientRect()
        .width,
      maxWidth: getComputedStyle(
        element.querySelector('[data-attachment-renderer]')!,
      ).maxWidth,
      display: getComputedStyle(
        element.querySelector('[data-attachment-renderer]')!,
      ).display,
    }))
  await page.screenshot({ path: testInfo.outputPath('file-images.png') })
  expect(errors).toEqual([])
  expect(sizes.display).toBe('grid')
  expect(sizes.maxWidth).toBe('320px')
  expect(sizes.card).toBeLessThanOrEqual(320)
  expect(sizes.grid).toBeLessThanOrEqual(320)
  expect(sizes.bubble - Math.max(sizes.card, sizes.grid)).toBeLessThanOrEqual(
    28,
  )
})

async function expectBubblesFit(page: Page) {
  await expect(page.locator('[data-case]')).toHaveCount(28)
  await page.evaluate(() => document.fonts.ready)
  await expect(
    page.locator('[data-case="file-images"] [data-attachment-renderer]'),
  ).toHaveCSS('display', 'grid')
  const overflow = await page.locator('[data-case]').evaluateAll((cases) =>
    cases.flatMap((container) => {
      const bubble = container.querySelector('[data-message-bubble]')!
      const bounds = bubble.getBoundingClientRect()
      const row = bubble.parentElement!.getBoundingClientRect()
      const cap = window.innerWidth >= 640 ? 0.78 : 0.94
      const problems = []
      if (bubble.scrollWidth > bubble.clientWidth + 1)
        problems.push(
          `bubble overflow ${bubble.scrollWidth}/${bubble.clientWidth}`,
        )
      if (bounds.left < row.left - 1 || bounds.right > row.right + 1)
        problems.push('bubble outside row')
      if (bounds.width > row.width * cap + 1)
        problems.push('bubble exceeds responsive width cap')
      for (const child of bubble.querySelectorAll(
        '[data-attachment-renderer] > *, [data-attachment-card], [data-image-grid], [data-single-image], [data-message-reply-quote], [data-forward-item], [data-message-metadata]',
      )) {
        const childBounds = child.getBoundingClientRect()
        if (
          childBounds.left < bounds.left + 11 ||
          childBounds.right > bounds.right - 11
        )
          problems.push(
            `${child.getAttributeNames().find((name) => name.startsWith('data-')) || child.tagName} outside bubble content`,
          )
      }
      for (const body of bubble.querySelectorAll(
        '[data-message-reply-quote] .line-clamp-2',
      )) {
        if (body.scrollWidth > body.clientWidth + 1)
          problems.push('quoted text overflows horizontally')
      }
      return problems.length
        ? [
            {
              key: container.getAttribute('data-case'),
              width: bounds.width,
              problems,
            },
          ]
        : []
    }),
  )
  expect(overflow).toEqual([])
}

for (const viewport of [320, 360, 840]) {
  for (const longLabels of [false, true]) {
    test(`all bubbles fit at ${viewport}px with ${longLabels ? 'long' : 'normal'} labels`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: viewport, height: 900 })
      await page.goto(
        `/tests/browser/messenger-bubbles.html${longLabels ? '?longLabels=1' : ''}`,
      )
      await expectBubblesFit(page)
    })
  }
}

for (const provider of ['vk_direct', 'telegram_bot', 'max_direct', 'wazzup']) {
  for (const direction of ['inbound', 'outbound']) {
    test(`${provider} ${direction} bubbles stay compact on mobile`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: 360, height: 900 })
      await page.goto(
        `/tests/browser/messenger-bubbles.html?provider=${provider}&direction=${direction}&longLabels=1`,
      )
      await expectBubblesFit(page)
      const width = await page
        .locator('[data-case="file-only-short"] [data-message-bubble]')
        .evaluate((bubble) => bubble.getBoundingClientRect().width)
      expect(width).toBeLessThan(220)
    })
  }
}
