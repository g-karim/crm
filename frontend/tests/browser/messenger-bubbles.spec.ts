import { expect, test, type Page } from '@playwright/test'

declare global {
  interface Window {
    messengerMediaFixture: {
      delta(status?: string): Promise<void>
      refresh(): Promise<void>
    }
  }
}

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

for (const viewport of [320, 840]) {
  test(`a short reply keeps readable metadata at ${viewport}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: viewport, height: 720 })
    await page.goto(
      '/tests/browser/messenger-bubbles.html?case=long-reply&shortReply=1',
    )
    const bubble = page.locator('[data-message-bubble]')
    await expect(bubble).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    const geometry = await bubble.evaluate((element) => {
      const metadata = element.querySelector('[data-message-metadata]')!
      const sender = metadata.querySelector('[data-message-labels] > span')!
      const source = metadata.querySelector(
        '[data-message-labels] > :nth-child(2)',
      )!
      return {
        width: element.getBoundingClientRect().width,
        senderHeight: sender.getBoundingClientRect().height,
        sourceHeight: source.getBoundingClientRect().height,
        senderLineHeight: parseFloat(getComputedStyle(sender).lineHeight),
        sourceLineHeight: parseFloat(getComputedStyle(source).lineHeight),
      }
    })
    expect(geometry.width).toBeGreaterThan(240)
    expect(geometry.senderHeight).toBeLessThanOrEqual(
      geometry.senderLineHeight + 1,
    )
    expect(geometry.sourceHeight).toBeLessThanOrEqual(
      geometry.sourceLineHeight + 8,
    )
  })
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

for (const provider of [
  'vk_direct',
  'telegram_bot',
  'max_direct',
  'avito_direct',
  'wazzup',
]) {
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

for (const platform of ['whatsapp', 'telegram']) {
  for (const direction of ['inbound', 'outbound']) {
    test(`framed sticker fits full channel names in ${platform} ${direction}`, async ({
      page,
    }, testInfo) => {
      await page.setViewportSize({ width: 400, height: 640 })
      const source =
        platform === 'whatsapp'
          ? 'WhatsApp Live Test 2'
          : `Личный Telegram — ${'ДлинноеНазваниеКанала'.repeat(8)}`.slice(
              0,
              140,
            )
      await page.goto(
        `/tests/browser/messenger-bubbles.html?wazzupMedia=1&case=image-sticker-inferred&platform=${platform}&direction=${direction}&channelLabel=${encodeURIComponent(source)}`,
      )
      await page.evaluate(() => {
        document.documentElement.style.zoom = '1.25'
      })
      const bubble = page.locator('[data-message-bubble]')
      await expect(bubble.locator('[data-sticker-image]')).toBeVisible()
      await expect(bubble).not.toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
      const label = bubble.locator('[data-message-source]')
      await expect(label).toHaveText(source)
      await expect(label).toHaveCSS('white-space', 'normal')
      const geometry = await bubble.evaluate((node) => {
        const bounds = node.getBoundingClientRect()
        const media = node
          .querySelector('[data-sticker-attachment]')!
          .getBoundingClientRect()
        const renderer = node
          .querySelector('[data-attachment-renderer]')!
          .getBoundingClientRect()
        const footer = node
          .querySelector('[data-message-footer]')!
          .getBoundingClientRect()
        const label = node.querySelector('[data-message-source]')!
        const labelBounds = label.getBoundingClientRect()
        return {
          bubble: { left: bounds.left, right: bounds.right },
          media: { left: media.left, right: media.right, width: media.width },
          rendererWidth: renderer.width,
          footer: {
            left: footer.left,
            right: footer.right,
            width: footer.width,
          },
          labelOverflow: label.scrollWidth - label.clientWidth,
          label: {
            left: labelBounds.left,
            right: labelBounds.right,
            height: labelBounds.height,
          },
        }
      })
      expect(geometry.media.width).toBeCloseTo(200, 0)
      expect(geometry.rendererWidth).toBeCloseTo(geometry.media.width, 0)
      expect(geometry.footer.left).toBeCloseTo(geometry.media.left, 0)
      expect(geometry.footer.right).toBeCloseTo(geometry.media.right, 0)
      expect(geometry.labelOverflow).toBeLessThanOrEqual(1)
      expect(geometry.label.left).toBeGreaterThanOrEqual(
        geometry.bubble.left + 14,
      )
      expect(geometry.label.right).toBeLessThanOrEqual(
        geometry.bubble.right - 14,
      )
      if (platform === 'whatsapp')
        expect(geometry.label.height).toBeLessThanOrEqual(30)
      const inset =
        direction === 'inbound'
          ? geometry.media.left - geometry.bubble.left
          : geometry.bubble.right - geometry.media.right
      expect(inset).toBeCloseTo(15, 0)
      await page.screenshot({
        path: testInfo.outputPath(`sticker-${platform}-${direction}.png`),
      })
    })
  }
  for (const width of [320, 840]) {
    test(`Wazzup ${platform} media survives initial/delta/refresh/reload at ${width}px`, async ({
      page,
    }, testInfo) => {
      await page.setViewportSize({ width, height: 900 })
      const errors: string[] = []
      page.on('pageerror', (error) => errors.push(error.message))
      await page.goto(
        `/tests/browser/messenger-bubbles.html?wazzupMedia=1&platform=${platform}`,
      )
      const document = page.locator('[data-case="document"]')
      await expect(document.locator('[data-attachment-card-title]')).toHaveText(
        'Договор.pdf',
      )
      await expect(document.locator('[data-message-text]')).toHaveCount(0)
      await expect(
        page.locator('[data-case="opaque-file"] [data-attachment-card-title]'),
      ).toHaveText('File')
      await expect(
        page.locator('[data-case="document-caption"] [data-message-text]'),
      ).toContainText('Реальная подпись')
      const voice = page.locator('[data-case="opus-voice"]')
      await expect(voice).toContainText('Voice message')
      await expect(voice.locator('[role="slider"]')).toHaveAttribute(
        'aria-label',
        'Playback Position',
      )
      await expect(voice).toContainText('0:00 / 0:01')
      await expect(
        page.locator('[data-case="gif"] [data-animated-image]'),
      ).toBeVisible()
      await expect(
        page.locator(
          '[data-case="tgs"] [data-sticker-attachment] svg[viewBox="0 0 64 64"]',
        ),
      ).toBeVisible()
      await expect(page.locator('[data-case="failed-file"]')).toContainText(
        'Attachment unavailable',
      )
      await expect(page.locator('[data-case="failed-file"]')).not.toContainText(
        'hidden',
      )
      await expect(
        page.locator('[data-case="unsupported-file"]'),
      ).toContainText('Unsupported')
      const portraitFrame = page.locator(
        '[data-case="portrait-image"] [data-single-image]',
      )
      const portraitGeometry = () =>
        portraitFrame.evaluate((node) => ({
          width: node.getBoundingClientRect().width,
          height: node.getBoundingClientRect().height,
        }))
      const portraitInitial = await portraitGeometry()
      expect(portraitInitial.height).toBeLessThanOrEqual(360)
      await expect(portraitFrame.locator('[data-media-backdrop]')).toHaveCount(
        1,
      )
      const pendingSticker = page.locator('[data-case="image-sticker-pending"]')
      const pendingBounds = await pendingSticker
        .locator('[data-sticker-attachment]')
        .boundingBox()
      expect(pendingBounds!.width).toBeLessThanOrEqual(160)
      expect(pendingBounds!.height).toBeLessThanOrEqual(160)
      expect(
        (await pendingSticker.locator('[data-message-bubble]').boundingBox())!
          .width,
      ).toBeLessThanOrEqual(184)
      for (const key of ['image-sticker', 'image-sticker-inferred']) {
        const container = page.locator(`[data-case="${key}"]`)
        await expect(container.locator('[data-sticker-image]')).toBeVisible()
        await expect(container.locator('[data-sticker-loading]')).toHaveCount(0)
        expect(
          (await container.locator('[data-message-bubble]').boundingBox())!
            .width,
        ).toBeLessThanOrEqual(184)
      }
      await expect(
        page.getByRole('button', { name: 'Refresh', exact: true }),
      ).toHaveCount(0)
      const sticker = page.locator(
        '[data-case="image-sticker"] [data-sticker-attachment]',
      )
      expect(
        await sticker.evaluate((node) => node.getBoundingClientRect().width),
      ).toBeLessThanOrEqual(160)
      const inferredSticker = page.locator(
        '[data-case="image-sticker-inferred"] [data-sticker-attachment]',
      )
      await expect(inferredSticker).toBeVisible()
      expect(
        await inferredSticker.evaluate(
          (node) => node.getBoundingClientRect().width,
        ),
      ).toBeLessThanOrEqual(160)
      const frame = page.locator(
        '[data-case="portrait-video"] [data-video-frame]',
      )
      const geometry = () =>
        frame.evaluate((node) => ({
          width: node.getBoundingClientRect().width,
          height: node.getBoundingClientRect().height,
          ratio: getComputedStyle(node).aspectRatio,
        }))
      const initial = await geometry()
      await frame.click()
      const video = page.locator('[data-case="portrait-video"] video[controls]')
      await expect(video).toBeVisible()
      await expect
        .poll(() => video.evaluate((node: HTMLVideoElement) => node.readyState))
        .toBeGreaterThanOrEqual(2)
      expect(await geometry()).toEqual(initial)
      await page.evaluate(() => window.messengerMediaFixture.delta('retrying'))
      await expect(page.locator('[data-case="document"]')).toContainText(
        'Retrying download',
      )
      await page.evaluate(() => window.messengerMediaFixture.delta('available'))
      await expect(document.locator('[data-attachment-card-title]')).toHaveText(
        'Договор.pdf',
      )
      expect(await geometry()).toEqual(initial)
      expect(await portraitGeometry()).toEqual(portraitInitial)
      await page.evaluate(() => window.messengerMediaFixture.refresh())
      expect(await geometry()).toEqual(initial)
      expect(await portraitGeometry()).toEqual(portraitInitial)
      await expect(portraitFrame.locator('[data-media-backdrop]')).toHaveCount(
        1,
      )
      for (const key of ['image-sticker', 'image-sticker-inferred']) {
        const container = page.locator(`[data-case="${key}"]`)
        await expect(container.locator('[data-sticker-loading]')).toHaveCount(0)
        await expect(container.locator('[data-sticker-fallback]')).toHaveCount(
          0,
        )
        await expect(container.locator('img')).toBeVisible()
      }
      await page.reload()
      await expect(frame).toBeVisible()
      expect(await geometry()).toEqual(initial)
      expect(await portraitGeometry()).toEqual(portraitInitial)

      const issues = await page
        .locator('[data-message-bubble]')
        .evaluateAll((bubbles) =>
          bubbles.flatMap((bubble) => {
            const bounds = bubble.getBoundingClientRect()
            const problems = []
            if (bubble.scrollWidth > bubble.clientWidth + 1)
              problems.push('bubble overflow')
            if (bounds.left < 0 || bounds.right > innerWidth)
              problems.push('bubble outside viewport')
            const card = bubble.querySelector('[data-attachment-card]')
            if (
              card &&
              bubble.closest('[data-case="document-caption"]') &&
              bounds.width - card.getBoundingClientRect().width > 28
            )
              problems.push('document does not fill bubble')
            return problems
          }),
        )
      expect(issues).toEqual([])
      expect(errors).toEqual([])
      await page.screenshot({
        path: testInfo.outputPath(`wazzup-${platform}-${width}.png`),
        fullPage: true,
      })
    })
  }
}
