import { execFile } from 'node:child_process'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'
import { expect, test } from '@playwright/test'
import { loadWazzupFixture } from './wazzup-local-fixture'

const fixture = loadWazzupFixture()
const execute = promisify(execFile)
const sendMethod = 'crm_messenger.api.messages.send_message'

async function incoming(channel: string, platform: string, text: string) {
  const bench = process.env.WAZZUP_PARTNER_E2E_BENCH
  const site = process.env.WAZZUP_PARTNER_E2E_SITE
  const python = process.env.WAZZUP_PARTNER_E2E_PYTHON
  if (!bench || !site || !python)
    throw new Error(
      'The isolated runner must provide Partner CLI configuration.',
    )
  await execute(
    python,
    [
      fileURLToPath(
        new URL(
          '../../../../crm_messenger/scripts/run_wazzup_partner_simulator.py',
          import.meta.url,
        ),
      ),
      '--bench',
      bench,
      '--site',
      site,
      '--incoming',
      '--channel',
      channel,
      '--text',
      text,
      '--contact-name',
      `Partner ${platform} contact`,
      '--chat-id',
      platform === 'whatsapp' ? '79990000002' : '900000002',
    ],
    { timeout: 60000, maxBuffer: 65536 },
  )
}

// Full CRM, real login/RPC/database/worker and the manual simulator launcher.
// No page.route(), fake RPC responses or alternative simulator UI entry.
for (const [label, platform] of [
  ['WhatsApp', 'whatsapp'],
  ['Telegram personal chats', 'telegram'],
]) {
  test(`${label}: shared channel modal, QR/2FA and real incoming/outgoing messages`, async ({
    page,
  }) => {
    const login = await page.request.post('/api/method/login', {
      form: { usr: fixture.user, pwd: fixture.password },
    })
    expect(login.ok()).toBeTruthy()
    // The first complete CRM visit compiles the Vite module graph. Readiness
    // is the actual navigation control, not completion of every page asset.
    await page.goto('/crm', {
      waitUntil: 'domcontentloaded',
      timeout: 60000,
    })
    const administrator = page
      .getByRole('button')
      .filter({ hasText: 'Administrator' })
      .first()
    await expect(administrator).toBeVisible({ timeout: 30000 })
    await administrator.click()
    await page.getByText('Settings', { exact: true }).click()
    await page.getByText('Message Channels', { exact: true }).first().click()
    await page.getByRole('button', { name: 'New Channel', exact: true }).click()
    await expect(
      page.getByRole('option', {
        name: 'Wazzup User API v3 (legacy)',
        exact: true,
      }),
    ).toHaveCount(0)
    const dialog = page.getByRole('dialog', {
      name: 'New Channel',
      exact: true,
    })
    await expect(dialog).toBeVisible()
    await page.getByRole('combobox', { name: /^Provider/ }).click()
    await expect(page.getByRole('option')).toHaveCount(6)
    expect(await page.getByRole('option').allTextContents()).toEqual([
      'WhatsApp',
      'Telegram personal chats',
      'Telegram Bot',
      'VK',
      'MAX',
      'Avito',
    ])
    await page.getByRole('option', { name: label, exact: true }).click()
    await expect(page.getByLabel('Wazzup API key')).toHaveCount(0)
    await expect(page.getByLabel('Channel ID', { exact: true })).toHaveCount(0)
    await expect(page.getByRole('combobox', { name: /^Provider/ })).toHaveCount(
      1,
    )
    await expect(page.getByRole('combobox', { name: /^Platform/ })).toHaveCount(
      0,
    )
    await expect(
      dialog.locator('[data-wazzup-partner-connection]'),
    ).toHaveCount(1)
    await expect(
      page.getByRole('dialog', {
        name: 'Connect WhatsApp / Telegram',
        exact: true,
      }),
    ).toHaveCount(0)
    await expect(dialog).not.toContainText('Wazzup')
    const name = `Manual Partner ${platform}`
    await page.getByLabel('Channel Name', { exact: true }).fill(name)
    await page.getByRole('button', { name: 'Connect', exact: true }).click()
    const settingsDialog = page.getByRole('dialog', {
      name: 'Channel Settings',
      exact: true,
    })
    await expect(settingsDialog).toBeVisible()
    await expect(
      page.getByRole('dialog', { name: 'New Channel', exact: true }),
    ).toHaveCount(0)
    await expect(settingsDialog.locator('[data-wazzup-qr]')).toBeVisible()
    await expect(
      settingsDialog.getByLabel('Channel Name', { exact: true }),
    ).toBeDisabled()
    await expect(
      settingsDialog.getByRole('combobox', { name: /^Provider/ }),
    ).toBeDisabled()
    if (process.env.WAZZUP_E2E_ARTIFACTS)
      await settingsDialog.screenshot({
        path: join(
          process.env.WAZZUP_E2E_ARTIFACTS,
          `partner-${platform}-qr.png`,
        ),
      })
    await page
      .getByRole('button', { name: 'Simulate QR scan', exact: true })
      .click()
    if (platform === 'telegram') {
      await page
        .getByLabel('Two-factor authentication password', { exact: true })
        .fill('simulator-2fa-password')
      await page
        .getByRole('button', { name: 'Submit password', exact: true })
        .click()
    }
    await expect(
      page.getByText('The messenger account is connected.', { exact: true }),
    ).toBeVisible()
    const response = await page.request.get(
      '/api/method/crm_messenger.api.settings.get_settings',
    )
    expect(response.ok()).toBeTruthy()
    const { message } = await response.json()
    const channel = message.channels.find(
      (row: { custom_display_name: string }) =>
        row.custom_display_name === name,
    )
    expect(channel).toMatchObject({
      provider: 'wazzup',
      platform,
      wazzup_api_mode: 'partner_api_v2',
      wazzup_status: 'active',
      enabled: 1,
      api_token_configured: false,
    })
    expect(channel.provider_channel_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    )
    await settingsDialog
      .getByRole('button', { name: 'Close', exact: true })
      .last()
      .click()
    await expect(
      page.getByRole('button').filter({ hasText: name }),
    ).toBeVisible()
    await expect(
      page.getByText(channel.provider_channel_id, { exact: false }),
    ).toHaveCount(0)
    await page.getByRole('button').filter({ hasText: name }).click()
    await expect(settingsDialog).toBeVisible()
    await expect(
      settingsDialog.getByRole('button', {
        name: 'Refresh Status',
        exact: true,
      }),
    ).toBeVisible()
    await expect(
      settingsDialog.getByRole('button', { name: 'Reconnect', exact: true }),
    ).toBeVisible()
    await expect(
      settingsDialog.getByRole('button', {
        name: 'Delete Channel',
        exact: true,
      }),
    ).toBeVisible()
    await expect(settingsDialog.locator('[data-wazzup-qr]')).toHaveCount(0)
    await expect(settingsDialog.locator('[data-wazzup-2fa]')).toHaveCount(0)
    await expect(
      settingsDialog.getByRole('button', { name: 'Save Channel', exact: true }),
    ).toHaveCount(0)
    await expect(settingsDialog).not.toContainText('Wazzup')
    await settingsDialog
      .getByRole('button', { name: 'Refresh Status', exact: true })
      .click()
    await expect(
      settingsDialog.getByText('The messenger account is connected.', {
        exact: true,
      }),
    ).toBeVisible()
    if (process.env.WAZZUP_E2E_ARTIFACTS)
      await settingsDialog.screenshot({
        path: join(
          process.env.WAZZUP_E2E_ARTIFACTS,
          `partner-${platform}-active.png`,
        ),
      })
    await settingsDialog
      .getByRole('button', { name: 'Reconnect', exact: true })
      .click()
    await expect(settingsDialog.locator('[data-wazzup-qr]')).toBeVisible()
    await expect(
      page
        .getByRole('dialog')
        .filter({ has: page.locator('[data-wazzup-partner-connection]') }),
    ).toHaveCount(1)
    await settingsDialog
      .getByRole('button', { name: 'Simulate QR scan', exact: true })
      .click()
    if (platform === 'telegram') {
      await settingsDialog
        .getByLabel('Two-factor authentication password', { exact: true })
        .fill('simulator-2fa-password')
      await settingsDialog
        .getByRole('button', { name: 'Submit password', exact: true })
        .click()
    }
    await expect(
      settingsDialog.getByText('The messenger account is connected.', {
        exact: true,
      }),
    ).toBeVisible()
    await settingsDialog
      .getByRole('button', { name: 'Close', exact: true })
      .last()
      .click()

    // The same dev command used by an administrator submits a native provider
    // event. Lead and Conversation creation use the ordinary ingress worker.
    const inboundText = `${platform} simulator incoming through dev CLI`
    await incoming(name, platform, inboundText)
    async function conversations() {
      const response = await page.request.get(
        '/api/resource/Messenger Conversation',
        {
          params: {
            fields: JSON.stringify([
              'name',
              'reference_doctype',
              'reference_name',
            ]),
            filters: JSON.stringify([['channel', '=', channel.name]]),
          },
        },
      )
      expect(response.ok()).toBeTruthy()
      return (await response.json()).data as {
        name: string
        reference_doctype: string
        reference_name: string
      }[]
    }
    await expect
      .poll(async () => (await conversations()).length, {
        timeout: 45000,
      })
      .toBe(1)
    const conversation = (await conversations())[0]
    expect(conversation.reference_doctype).toBe('CRM Lead')
    expect(conversation.reference_name).toBeTruthy()
    await page.goto(
      `/crm/leads/${encodeURIComponent(conversation.reference_name)}?messenger_conversation=${encodeURIComponent(conversation.name)}#messenger`,
    )
    await expect(
      page.getByRole('tab', { name: 'Messages', exact: true }),
    ).toHaveAttribute('aria-selected', 'true')
    await expect(page.getByText(inboundText, { exact: true })).toBeVisible()
    const outboundText = `${platform} reply from the normal CRM composer`
    await page
      .locator('textarea[placeholder="Enter a message..."]')
      .fill(outboundText)
    const sentResponse = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === `/api/method/${sendMethod}` &&
        response.request().method() === 'POST',
    )
    await page.getByRole('button', { name: 'Send', exact: true }).click()
    const result = (await (await sentResponse).json()).message
    expect(result.ok).toBeTruthy()
    expect(result.name).toBeTruthy()
    await expect(
      page.locator(`[data-message-id="${result.name}"]`),
    ).toBeVisible()
    await expect
      .poll(
        async () => {
          const response = await page.request.get(
            '/api/method/crm_messenger.api.messages.get_message',
            {
              params: { message: result.name },
            },
          )
          expect(response.ok()).toBeTruthy()
          return (await response.json()).message.message.delivery_status
        },
        { timeout: 45000 },
      )
      .toBe('sent')
    const nextInboundText = `${platform} second incoming through the same dev CLI`
    await incoming(name, platform, nextInboundText)
    await expect(page.getByText(nextInboundText, { exact: true })).toBeVisible({
      timeout: 30000,
    })
    expect(await conversations()).toHaveLength(1)
    await expect(page.getByText(outboundText, { exact: true })).toHaveCount(1)
  })
}
