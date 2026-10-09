import { test, expect, type Page } from '@playwright/test'
// All RPC responses are fixtures. No Frappe site or Wazzup account is contacted.

const whatsappId = 'b5436cae-2434-4b55-a477-99386aeeecb4'
const telegramId = '970899f7-82ca-4fd8-9404-565ce53c8d0a'

async function openFixture(page: Page) {
  const scriptFailure = new Promise<never>((_, reject) =>
    page.once('pageerror', reject),
  )
  await Promise.race([
    page
      .goto('/tests/browser/messenger-settings.html')
      .then(() =>
        page
          .getByRole('button', { name: 'New Channel', exact: true })
          .waitFor(),
      ),
    scriptFailure,
  ])
}

test('real settings controls select Wazzup channels, reuse a saved key, and keep configuration separate from delivery', async ({
  page,
}) => {
  const apiCalls: { method: string; params: Record<string, unknown> }[] = []
  let channels = [
    {
      name: 'wazzup-existing',
      provider: 'wazzup',
      platform: 'whatsapp',
      custom_display_name: 'Existing WhatsApp',
      provider_channel_id: whatsappId,
      api_token_configured: true,
      enabled: true,
      state: 'unchecked',
    },
  ]
  const connection = {
    last_checked_at: '2026-10-05 12:00:00',
    api: { status: 'verified' },
    remote_channel: { status: 'verified', state: 'active' },
    subscription: {
      status: 'verified',
      url_matches: true,
      messages_and_statuses: true,
    },
    local_config: {
      status: 'verified',
      public_https: true,
      secret_configured: true,
      integration_enabled: true,
      channel_enabled: true,
    },
    delivery: { status: 'unverified', last_received_at: null },
  }
  await page.route('**/api/method/**', async (route) => {
    const method = route.request().url().split('/api/method/')[1]
    const params = route.request().postDataJSON()
    apiCalls.push({ method, params })
    let result: unknown
    if (method === 'crm_messenger.api.settings.get_settings')
      result = {
        settings: {
          enabled: true,
          wazzup_legacy_ui_enabled: true,
          webhook_base_url_is_public_https: true,
          webhook_secret_configured: true,
        },
        channels,
      }
    else if (method === 'crm_messenger.api.diagnostics.get_health_summary')
      result = {
        channels: [
          {
            name: 'wazzup-new',
            provider: 'wazzup',
            webhook_queue: { queued: 2, failed: 1 },
            media: { pending: 1, failed: 0 },
          },
        ],
      }
    else if (method === 'crm_messenger.api.wazzup_connection.list_channels') {
      expect(params).toEqual({ channel: 'wazzup-existing' })
      result = {
        ok: true,
        channels: [
          {
            provider_channel_id: telegramId,
            platform: 'telegram',
            display_name: 'Telegram · @su***rt',
            remote_state: 'active',
          },
        ],
      }
    } else if (method === 'crm_messenger.api.settings.save_channel') {
      expect(params).toMatchObject({
        provider: 'wazzup',
        platform: 'telegram',
        provider_channel_id: telegramId,
        api_token_source_channel: 'wazzup-existing',
        enabled: true,
      })
      expect(params).not.toHaveProperty('api_token')
      const saved = { ...channels[0], ...params, name: 'wazzup-new' }
      channels = [...channels, saved]
      result = saved
    } else if (method === 'crm_messenger.api.wazzup_connection.check_channel') {
      expect(params).toEqual({ channel: 'wazzup-new' })
      channels = channels.map((channel) =>
        channel.name === 'wazzup-new'
          ? {
              ...channel,
              integration: {
                state: 'unchecked',
                token_status: 'valid',
                last_checked_at: connection.last_checked_at,
                wazzup_connection: connection,
              },
            }
          : channel,
      )
      result = {
        ok: true,
        state: 'unchecked',
        message:
          'Configuration verified. Webhook delivery has not been verified.',
        connection,
      }
    } else throw new Error(`Unexpected RPC: ${method}`)
    await route.fulfill({ json: { message: result } })
  })
  await openFixture(page)
  await page.getByRole('button', { name: 'New Channel', exact: true }).click()
  await page
    .getByRole('combobox', { name: /^Provider(?: \(required\))?$/ })
    .click()
  await page
    .getByRole('option', { name: 'Wazzup User API v3 (legacy)', exact: true })
    .click()
  await expect(
    page.getByRole('switch', { name: 'Active in CRM', exact: true }),
  ).not.toBeChecked()
  await page
    .getByRole('combobox', { name: 'API key source', exact: true })
    .click()
  await page
    .getByRole('option', { name: 'Existing WhatsApp', exact: true })
    .click()
  await expect(page.getByLabel('Wazzup API key')).toHaveValue('')
  await page
    .getByRole('button', { name: 'Load Wazzup channels', exact: true })
    .click()
  await page
    .getByRole('combobox', { name: 'Available Wazzup channels', exact: true })
    .click()
  await page
    .getByRole('option', { name: 'Telegram · @su***rt', exact: true })
    .click()
  await expect(page.getByLabel('Channel ID')).toHaveValue(telegramId)
  await expect(
    page.getByRole('combobox', { name: /^Platform(?: \(required\))?$/ }),
  ).toContainText('Telegram personal chats')
  await page.getByRole('switch', { name: 'Active in CRM', exact: true }).click()
  await page
    .getByRole('button', { name: 'Create Channel', exact: true })
    .click()
  await expect(
    page.getByRole('button', {
      name: 'Check saved configuration',
      exact: true,
    }),
  ).toBeEnabled()
  await page
    .getByRole('button', { name: 'Check saved configuration', exact: true })
    .click()
  await expect(page.locator('[data-diagnostic="api"]')).toContainText(
    'Verified',
  )
  await expect(page.locator('[data-diagnostic="delivery"]')).toContainText(
    'No event observed',
  )
  await expect(
    page.locator('[data-testid="wazzup-queue-diagnostics"]'),
  ).toContainText('Webhook events: 2 pending, 1 failed.')
  await expect(
    page.getByText('Channel Connected', { exact: true }),
  ).toHaveCount(0)
  await page.getByLabel('Wazzup API key').fill('replacement-draft')
  await expect(
    page.getByRole('button', {
      name: 'Check saved configuration',
      exact: true,
    }),
  ).toBeDisabled()
  expect(
    apiCalls.filter(
      ({ method }) =>
        method === 'crm_messenger.api.wazzup_connection.check_channel',
    ),
  ).toHaveLength(1)
})

test('draft-key exception responses stay silent with real frappe-ui controls', async ({
  page,
}) => {
  const logs: string[] = []
  page.on('console', (message) => logs.push(message.text()))
  await page.route('**/api/method/**', async (route) => {
    const method = route.request().url().split('/api/method/')[1]
    if (method === 'crm_messenger.api.settings.get_settings')
      await route.fulfill({
        json: {
          message: {
            settings: { wazzup_legacy_ui_enabled: true },
            channels: [],
          },
        },
      })
    else if (method === 'crm_messenger.api.wazzup_connection.list_channels') {
      expect(route.request().postDataJSON()).toEqual({
        api_token: 'fixture-draft-secret',
      })
      await route.fulfill({
        json: {
          exc: '["raw provider exception fixture-draft-secret"]',
          _server_messages: '["private provider data"]',
        },
      })
    } else throw new Error(`Unexpected RPC: ${method}`)
  })
  await openFixture(page)
  await page.getByRole('button', { name: 'New Channel', exact: true }).click()
  await page
    .getByRole('combobox', { name: /^Provider(?: \(required\))?$/ })
    .click()
  await page
    .getByRole('option', { name: 'Wazzup User API v3 (legacy)', exact: true })
    .click()
  await page.getByLabel('Wazzup API key').fill('fixture-draft-secret')
  await page
    .getByRole('button', { name: 'Load Wazzup channels', exact: true })
    .click()
  await expect(page.getByTestId('channel-auth-error')).toHaveText(
    'The provider operation failed.',
  )
  expect(logs.join('\n')).not.toContain('fixture-draft-secret')
  expect(logs.join('\n')).not.toContain('private provider data')
  await expect(page.locator('[data-diagnostic="api"]')).toHaveCount(0)
})
