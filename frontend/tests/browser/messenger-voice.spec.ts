import { expect, test, type Page, type Route } from '@playwright/test'

const sendPath = '/api/method/crm_messenger.api.messages.send_voice_message'

test.use({
  permissions: ['microphone'],
  launchOptions: {
    args: [
      '--use-fake-device-for-media-stream',
      '--use-fake-ui-for-media-stream',
    ],
  },
})

async function voiceForm(route: Route) {
  const request = route.request()
  expect(request.method()).toBe('POST')
  return new Response(request.postDataBuffer(), {
    headers: { 'Content-Type': request.headers()['content-type'] },
  }).formData()
}

async function recordPreview(page: Page) {
  await page.getByRole('button', { name: 'Record a Voice Message' }).click()
  await expect(page.getByText('0:01', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Stop Recording' }).click()
  await expect(
    page.getByRole('button', { name: 'Send Voice Message' }),
  ).toBeEnabled()
  await expect(page.locator('[data-messenger-audio]')).toContainText(
    'Voice message',
  )
}

test.describe('Wazzup shared voice recorder', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/*', (route) => {
      const url = new URL(route.request().url())
      if (url.hostname !== '127.0.0.1' || url.pathname.startsWith('/api/'))
        return route.abort()
      return route.continue()
    })
  })

  for (const platform of ['whatsapp', 'telegram', 'max']) {
    test(`${platform} records Opus and submits through the existing voice API`, async ({
      page,
    }) => {
      const requests: FormData[] = []
      const errors: string[] = []
      page.on('pageerror', (error) => errors.push(error.message))
      await page.route(`**${sendPath}`, async (route) => {
        requests.push(await voiceForm(route))
        await route.fulfill({
          json: {
            message: {
              ok: true,
              name: 'SYNTHETIC-VOICE',
              status: 'queued',
            },
          },
        })
      })
      await page.goto(
        `/tests/browser/messenger-voice.html?platform=${platform}`,
      )
      expect(requests).toHaveLength(0)
      await recordPreview(page)
      expect(requests).toHaveLength(0)
      await page.getByRole('button', { name: 'Send Voice Message' }).click()
      await expect(page.locator('[data-queued-status]')).toHaveText('queued')
      await expect(
        page.getByRole('button', { name: 'Record a Voice Message' }),
      ).toBeVisible()
      expect(requests).toHaveLength(1)
      const form = requests[0]
      expect(form.get('conversation')).toBe('SYNTHETIC-CONVERSATION')
      expect(form.get('channel')).toBe(`WAZZUP-${platform}`)
      expect(form.get('reference_doctype')).toBe('CRM Lead')
      expect(form.get('reference_name')).toBe('SYNTHETIC-LEAD')
      expect(form.get('reply_to_message')).toBe('SYNTHETIC-REPLY')
      expect(form.get('client_request_id')).toEqual(expect.any(String))
      expect(`${form.get('client_request_id')}`.length).toBeGreaterThan(0)
      expect(Number(form.get('duration_ms'))).toBeGreaterThanOrEqual(1000)
      expect(Number(form.get('duration_ms'))).toBeLessThan(300000)
      const waveform = JSON.parse(`${form.get('waveform')}`)
      expect(waveform.length).toBeGreaterThan(0)
      expect(
        waveform.every((value: number) => value >= 0 && value <= 255),
      ).toBe(true)
      const file = form.get('file') as File
      expect(file.type).toMatch(/^audio\/(?:ogg|webm)/)
      expect(file.name).toMatch(/^voice\.(?:ogg|webm)$/)
      expect(file.size).toBeGreaterThan(0)
      expect(file.size).toBeLessThan(10 * 1024 * 1024)
      expect(Buffer.from(await file.arrayBuffer()).includes('OpusHead')).toBe(
        true,
      )
      expect(errors).toEqual([])
    })
  }

  test('keeps the recorded draft and request identity after an API error', async ({
    page,
  }) => {
    const requests: FormData[] = []
    await page.route(`**${sendPath}`, async (route) => {
      requests.push(await voiceForm(route))
      await route.fulfill({
        status: requests.length === 1 ? 400 : 200,
        json: {
          message:
            requests.length === 1
              ? { ok: false, error: 'Synthetic voice preparation failed.' }
              : { ok: true, name: 'SYNTHETIC-VOICE', status: 'queued' },
        },
      })
    })
    await page.goto('/tests/browser/messenger-voice.html?platform=telegram')
    await recordPreview(page)
    await page.getByRole('button', { name: 'Send Voice Message' }).click()
    await expect(
      page.getByText('Synthetic voice preparation failed.', { exact: true }),
    ).toBeVisible()
    await expect(page.locator('[data-messenger-audio]')).toBeVisible()
    await expect(page.locator('[data-queued-status]')).toHaveCount(0)
    await page.getByRole('button', { name: 'Send Voice Message' }).click()
    await expect(page.locator('[data-queued-status]')).toHaveText('queued')
    expect(requests).toHaveLength(2)
    expect(requests[1].get('client_request_id')).toBe(
      requests[0].get('client_request_id'),
    )
    const first = requests[0].get('file') as File
    const second = requests[1].get('file') as File
    expect(await second.arrayBuffer()).toEqual(await first.arrayBuffer())
  })

  test('respects the composer disabled state before microphone access', async ({
    page,
  }) => {
    await page.goto(
      '/tests/browser/messenger-voice.html?platform=max&disabled=1',
    )
    await expect(page.locator('[data-fixture-channel]')).toHaveText('max')
    await expect(
      page.getByRole('button', { name: 'Record a Voice Message' }),
    ).toBeDisabled()
    await expect(
      page.getByRole('button', { name: 'Stop Recording' }),
    ).toHaveCount(0)
  })
})
