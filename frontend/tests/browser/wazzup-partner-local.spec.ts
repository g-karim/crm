import { execFile } from 'node:child_process'
import { writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'
import { expect, test, type Page, type TestInfo } from '@playwright/test'
import { loadWazzupFixture } from './wazzup-local-fixture'

const fixture = loadWazzupFixture()
const execute = promisify(execFile)
const sendMethod = 'crm_messenger.api.messages.send_message'

type PartnerChannel = {
  name: string
  custom_display_name: string
  provider_channel_id: string
  enabled: number
  wazzup_status: string
}

async function channels(page: Page): Promise<PartnerChannel[]> {
  const response = await page.request.get(
    '/api/method/crm_messenger.api.settings.get_settings',
  )
  expect(response.ok()).toBeTruthy()
  return (await response.json()).message.channels
}

async function openMessageChannels(page: Page) {
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
}

async function completeQr(page: Page, platform: string) {
  const dialog = page.getByRole('dialog', {
    name: 'Channel Settings',
    exact: true,
  })
  await dialog
    .getByRole('button', { name: 'Simulate QR scan', exact: true })
    .click()
  if (platform === 'telegram') {
    await dialog
      .getByLabel('Two-factor authentication password', { exact: true })
      .fill('simulator-2fa-password')
    await dialog
      .getByRole('button', { name: 'Submit password', exact: true })
      .click()
  }
  await expect(
    dialog.getByText('Channel Connected', { exact: true }).first(),
  ).toBeVisible()
  await expect(dialog.locator('[data-wazzup-qr]')).toHaveCount(0)
}

async function incoming(
  channel: string,
  platform: string,
  text: string,
  chatId = platform === 'whatsapp' ? '79990000002' : '900000002',
) {
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
      chatId,
    ],
    { timeout: 60000, maxBuffer: 65536 },
  )
}

type FirstPhase = 'http' | 'status' | 'echo'
type FirstCase = {
  case_id: string
  lead: string
  channel: string
  channel_name: string
  expected_chat_id: string
  conversations: unknown[]
  messages: unknown[]
}
type FirstState = {
  http_completed: boolean
  conversations: {
    name: string
    channel: string
    external_chat_id: string | null
    provider_chat_key: string
    reference_name: string
  }[]
  messages: {
    name: string
    conversation: string
    channel: string
    direction: string
    text: string
    status: string
    delivery_status: string
    provider_request_id: string | null
    external_message_id: string | null
    external_chat_id: string | null
    attempt_count: number
  }[]
  calls: {
    request_id: string
    message_id: string
    channel_id: string
  }[]
  callbacks: {
    phase: string
    event: string | null
    chat_id: string | null
    http_status: number
  }[]
  webhooks: {
    status: string
    error: string | null
    event_type: string
    attempt_count: number
    encrypted_payload_present: boolean
  }[]
}

async function partnerControl<T>(
  page: Page,
  action: string,
  data: Record<string, unknown>,
): Promise<T> {
  const response = await page.request.post(
    `${fixture.simulator_origin}/control/${action}`,
    {
      headers: { Authorization: `Bearer ${fixture.control_token}` },
      data,
      timeout: 30000,
    },
  )
  expect(response.ok(), `isolated Partner control ${action}`).toBeTruthy()
  const result = await response.json()
  if (Object.hasOwn(result, 'ok')) expect(result.ok).toBeTruthy()
  return result as T
}

async function expectDelivery(page: Page, name: string, label: string) {
  const row = page.locator(`[data-message-id="${name}"]`)
  await expect(row).toBeVisible({ timeout: 30000 })
  await expect(async () => {
    await page.mouse.move(0, 0)
    await row.locator('[data-message-delivery]').hover()
    await expect(
      page
        .locator('[data-reka-popper-content-wrapper] .rounded')
        .filter({ hasText: label }),
    ).toBeVisible({ timeout: 1500 })
  }).toPass({ timeout: 30000 })
  await page.mouse.move(0, 0)
}

async function firstOutbound(
  page: Page,
  testInfo: TestInfo,
  platform: string,
  channelName: string,
  order: FirstPhase[],
  temporaryNull = false,
) {
  const scenario = order.join('_')
  const setup = await partnerControl<FirstCase>(
    page,
    'partner-first-outbound',
    {
      platform,
      channel: channelName,
      scenario,
      temporary_null: temporaryNull,
    },
  )
  expect(setup.conversations).toEqual([])
  expect(setup.messages).toEqual([])
  const state = () =>
    partnerControl<FirstState>(page, 'partner-state', {
      case_id: setup.case_id,
    })
  const deliver = (phase: string) =>
    partnerControl(page, 'partner-deliver', {
      case_id: setup.case_id,
      phase,
    })
  const leadUrl = `/crm/leads/${encodeURIComponent(setup.lead)}#messenger`
  await page.goto(leadUrl, {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  })
  await expect(
    page.getByRole('tab', { name: 'Messages', exact: true }),
  ).toHaveAttribute('aria-selected', 'true', { timeout: 60000 })
  const channelSelect = page
    .getByRole('tabpanel', { name: 'Messages', exact: true })
    .getByRole('combobox')
    .first()
  await channelSelect.click()
  await page
    .getByRole('option', { name: setup.channel_name, exact: true })
    .click()
  await expect(channelSelect).toContainText(setup.channel_name)
  await expect(page.getByText('No messages yet', { exact: true })).toBeVisible()
  expect((await state()).conversations).toEqual([])

  async function send(text: string) {
    await page.locator('textarea[placeholder="Enter a message..."]').fill(text)
    const sent = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === `/api/method/${sendMethod}` &&
        response.request().method() === 'POST',
    )
    await page.getByRole('button', { name: 'Send', exact: true }).click()
    const response = await sent
    expect(response.ok()).toBeTruthy()
    expect(response.request().postDataJSON().channel).toBe(setup.channel)
    const result = (await response.json()).message
    expect(result.ok).toBeTruthy()
    expect(result.name).toBeTruthy()
    await expect(
      page.locator(`[data-message-id="${result.name}"]`),
    ).toBeVisible()
    return result.name as string
  }

  const text = `${platform} first outbound ${scenario}${temporaryNull ? ' temporary null' : ''}`
  const message = await send(text)
  await expect.poll(async () => (await state()).calls.length).toBe(1)
  let current = await state()
  expect(current.conversations).toHaveLength(1)
  expect(current.messages).toHaveLength(1)
  expect(current.conversations[0].external_chat_id).toBeFalsy()
  expect(current.messages[0]).toMatchObject({
    name: message,
    channel: setup.channel,
    status: 'sending',
    direction: 'outbound',
    attempt_count: 1,
  })
  expect(current.http_completed).toBe(false)
  const observedUiStatuses: string[] = []
  if (order[0] === 'http') {
    await expectDelivery(page, message, 'Sending')
    observedUiStatuses.push('sending')
  }
  const completed = new Set<FirstPhase>()
  for (const phase of order) {
    await deliver(phase)
    completed.add(phase)
    if (phase === 'http') {
      await expect.poll(async () => (await state()).http_completed).toBe(true)
      await expect
        .poll(async () => {
          const first = (await state()).messages.find(
            (row) => row.name === message,
          )
          return first?.provider_request_id
        })
        .toBeTruthy()
      if (!completed.has('echo')) {
        const accepted = await state()
        if (platform === 'whatsapp' && !temporaryNull) {
          expect(accepted.conversations[0].external_chat_id).toBe(
            setup.expected_chat_id,
          )
          expect(accepted.messages[0].external_chat_id).toBe(
            setup.expected_chat_id,
          )
        } else {
          expect(accepted.conversations[0].external_chat_id).toBeFalsy()
          expect(accepted.messages[0].external_chat_id).toBeFalsy()
        }
      }
      if (!completed.has('status')) {
        await expectDelivery(page, message, 'Awaiting provider status')
        observedUiStatuses.push('accepted')
      }
    } else if (!completed.has('http')) {
      // An ACK alone proves ingress. Wait until another real Redis worker has
      // attempted this callback while the first worker still awaits HTTP.
      await expect
        .poll(async () => {
          const beforeHttp = await state()
          return beforeHttp.webhooks.filter(
            (row) =>
              row.attempt_count > 0 &&
              ['retrying', 'processed'].includes(row.status),
          ).length
        })
        .toBe(completed.size)
      expect((await state()).http_completed).toBe(false)
    }
  }
  if (temporaryNull) {
    current = await state()
    expect(current.conversations[0].external_chat_id).toBeFalsy()
    await expect
      .poll(async () =>
        (await state()).webhooks.some(
          (row) => row.status === 'retrying' && row.encrypted_payload_present,
        ),
      )
      .toBe(true)
    expect((await state()).messages[0].external_chat_id).toBeFalsy()
    await deliver('late_echo')
  }
  await expect
    .poll(
      async () => {
        const latest = await state()
        return latest.conversations[0]?.external_chat_id
      },
      { timeout: 45000 },
    )
    .toBe(setup.expected_chat_id)
  await expect
    .poll(async () => (await state()).messages[0]?.status, {
      timeout: 45000,
    })
    .toBe('sent')
  await expectDelivery(page, message, 'Sent')
  observedUiStatuses.push('sent')
  for (const [phase, label] of [
    ['delivered', 'Delivered'],
    ['read', 'Read by recipient'],
  ]) {
    await deliver(phase)
    await expect
      .poll(async () => (await state()).messages[0]?.status)
      .toBe(phase)
    await expectDelivery(page, message, label)
    observedUiStatuses.push(phase)
  }
  current = await state()
  const conversation = current.conversations[0]
  expect(current.conversations).toHaveLength(1)
  expect(current.messages).toHaveLength(1)
  expect(conversation.channel).toBe(setup.channel)
  expect(conversation.reference_name).toBe(setup.lead)
  expect(conversation.provider_chat_key).toBeTruthy()
  expect(current.messages[0]).toMatchObject({
    conversation: conversation.name,
    external_chat_id: setup.expected_chat_id,
    provider_request_id: current.calls[0].request_id,
    external_message_id: current.calls[0].message_id,
    attempt_count: 1,
  })
  await expect
    .poll(async () =>
      (await state()).webhooks.every(
        (row) => row.status === 'processed' && !row.encrypted_payload_present,
      ),
    )
    .toBe(true)
  expect(current.webhooks.length).toBeGreaterThanOrEqual(4)
  expect(current.callbacks.map((row) => row.phase)).toEqual([
    ...order,
    ...(temporaryNull ? ['late_echo'] : []),
    'delivered',
    'read',
  ])
  expect(current.callbacks.find((row) => row.phase === 'http')?.chat_id).toBe(
    platform === 'whatsapp' && !temporaryNull ? setup.expected_chat_id : null,
  )
  expect(
    current.callbacks.every(
      (row) => row.http_status === (row.phase === 'http' ? 201 : 200),
    ),
  ).toBe(true)

  await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 })
  await expect(page.getByText(text, { exact: true })).toHaveCount(1)
  await expectDelivery(page, message, 'Read by recipient')
  expect((await state()).conversations).toHaveLength(1)
  const inbound = `${platform} follow-up incoming ${setup.case_id}`
  await incoming(channelName, platform, inbound, setup.expected_chat_id)
  await expect(page.getByText(inbound, { exact: true })).toBeVisible({
    timeout: 30000,
  })
  const followupText = `${platform} follow-up outgoing ${setup.case_id}`
  const followup = await send(followupText)
  await expect
    .poll(
      async () =>
        (await state()).messages.find((row) => row.name === followup)?.status,
    )
    .toBe('sent')
  await expectDelivery(page, followup, 'Sent')
  current = await state()
  expect(current.conversations).toHaveLength(1)
  expect(current.messages).toHaveLength(3)
  expect(current.calls).toHaveLength(2)
  expect(
    current.messages.every((row) => row.conversation === conversation.name),
  ).toBe(true)
  expect(
    current.messages.filter((row) => row.direction === 'inbound'),
  ).toHaveLength(1)
  expect(
    current.messages.filter((row) => row.direction === 'outbound'),
  ).toHaveLength(2)
  await expect(page.getByText(text, { exact: true })).toHaveCount(1)
  await expect(page.getByText(followupText, { exact: true })).toHaveCount(1)
  const evidenceName = `first-outbound-${platform}-${scenario}${temporaryNull ? '-null' : ''}`
  const evidencePath = testInfo.outputPath(`${evidenceName}.json`)
  await writeFile(
    evidencePath,
    JSON.stringify(
      {
        platform,
        order,
        temporary_null: temporaryNull,
        ui_statuses: observedUiStatuses,
        conversation_count: current.conversations.length,
        message_count: current.messages.length,
        provider_post_count: current.calls.length,
        first_message: message,
        conversation: conversation.name,
        callbacks: current.callbacks,
      },
      null,
      2,
    ),
    { encoding: 'utf8', mode: 0o600 },
  )
  await testInfo.attach(evidenceName, {
    path: evidencePath,
    contentType: 'application/json',
  })
}

// Full CRM, real login/RPC/database/worker and the manual simulator launcher.
// No page.route(), fake RPC responses or alternative simulator UI entry.
for (const [label, platform] of [
  ['WhatsApp', 'whatsapp'],
  ['Telegram personal chats', 'telegram'],
]) {
  test(`${label}: shared channel modal, QR/2FA and real incoming/outgoing messages`, async ({
    page,
  }, testInfo) => {
    test.setTimeout(platform === 'telegram' ? 600000 : 300000)
    const login = await page.request.post('/api/method/login', {
      form: { usr: fixture.user, pwd: fixture.password },
    })
    expect(login.ok()).toBeTruthy()
    // The first complete CRM visit compiles the Vite module graph. Readiness
    // is the actual navigation control, not completion of every page asset.
    await openMessageChannels(page)
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
    const initialName = `Manual Partner ${platform}`
    const name = `${initialName} renamed`
    await page.getByLabel('Channel Name', { exact: true }).fill(initialName)
    await expect(
      dialog.getByRole('button', { name: 'Connect / Restore', exact: true }),
    ).toHaveCount(0)
    await dialog
      .getByRole('button', { name: 'Create Channel', exact: true })
      .click()
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
    ).toBeEnabled()
    await expect(
      settingsDialog.getByRole('combobox', { name: /^Provider/ }),
    ).toBeDisabled()
    const nameInput = settingsDialog.getByLabel('Channel Name', { exact: true })
    await nameInput.fill(name)
    const polled = await page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname ===
        '/api/method/crm_messenger.api.wazzup_partner.get_onboarding_state',
      { timeout: 15000 },
    )
    expect(polled.ok()).toBeTruthy()
    await polled.finished()
    await expect(nameInput).toHaveValue(name)
    expect(
      (await channels(page)).find(
        (channel) => channel.custom_display_name === initialName,
      ),
    ).toBeTruthy()
    expect(
      (await channels(page)).some(
        (channel) => channel.custom_display_name === name,
      ),
    ).toBe(false)
    await expect(nameInput).toHaveValue(name)
    if (process.env.WAZZUP_E2E_ARTIFACTS)
      await settingsDialog.screenshot({
        path: join(
          process.env.WAZZUP_E2E_ARTIFACTS,
          `partner-${platform}-qr.png`,
        ),
      })
    await completeQr(page, platform)
    await expect(nameInput).toHaveValue(name)
    await settingsDialog
      .getByRole('button', { name: 'Save', exact: true })
      .click()
    await expect
      .poll(async () =>
        (await channels(page)).some(
          (channel) => channel.custom_display_name === name,
        ),
      )
      .toBe(true)
    await settingsDialog
      .getByRole('button', { name: 'Close', exact: true })
      .last()
      .click()
    const channel = (await channels(page)).find(
      (row) => row.custom_display_name === name,
    )
    expect(channel).toMatchObject({
      provider: 'wazzup',
      platform,
      wazzup_api_mode: 'partner_api_v2',
      wazzup_status: 'active',
      enabled: 1,
      api_token_configured: false,
    })
    expect(channel).toBeTruthy()
    if (!channel) throw new Error('The renamed Partner channel was not saved.')
    expect(channel.provider_channel_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    )
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
      settingsDialog.getByRole('button', { name: 'Test', exact: true }),
    ).toBeVisible()
    await expect(
      settingsDialog.getByRole('button', {
        name: 'Connect / Restore',
        exact: true,
      }),
    ).toBeVisible()
    await expect(
      settingsDialog.getByRole('button', { name: 'Disconnect', exact: true }),
    ).toBeVisible()
    await expect(nameInput).toHaveValue(name)
    await expect(
      settingsDialog
        .getByText('Channel Connected', { exact: true })
        .and(settingsDialog.locator(':visible')),
    ).toHaveCount(1)
    await expect(
      settingsDialog.getByText('The messenger account is connected.', {
        exact: true,
      }),
    ).toHaveCount(0)
    await expect(
      settingsDialog.getByText('Connection status', { exact: true }),
    ).toHaveCount(0)
    await expect(settingsDialog.locator('[data-wazzup-qr]')).toHaveCount(0)
    await expect(settingsDialog.locator('[data-wazzup-2fa]')).toHaveCount(0)
    await expect(
      settingsDialog.getByRole('button', { name: 'Save', exact: true }),
    ).toBeVisible()
    await expect(settingsDialog).not.toContainText('Wazzup')
    await settingsDialog
      .getByRole('button', { name: 'Refresh Status', exact: true })
      .click()
    await expect(
      settingsDialog
        .getByText('Channel Connected', { exact: true })
        .and(settingsDialog.locator(':visible')),
    ).toHaveCount(1)
    const diagnostics = settingsDialog.locator(
      '[data-wazzup-partner-diagnostics]',
    )
    await expect(diagnostics).toHaveJSProperty('open', false)
    await expect(diagnostics.locator('dl')).not.toBeVisible()
    await expect(
      settingsDialog.getByRole('button', {
        name: 'Delete Channel',
        exact: true,
      }),
    ).not.toBeVisible()
    const checkedResponse = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname ===
          '/api/method/crm_messenger.api.wazzup_partner.check_channel' &&
        response.request().method() === 'POST',
    )
    await settingsDialog
      .getByRole('button', { name: 'Test', exact: true })
      .click()
    const checked = await checkedResponse
    expect(checked.ok()).toBeTruthy()
    expect(checked.request().postDataJSON()).toEqual({ channel: channel.name })
    expect(
      (await checked.json()).message.integration.wazzup_partner.reconciliation
        .status,
    ).toBe('verified')
    await expect(
      page.getByText('Connection settings verified.', { exact: true }),
    ).toBeVisible()
    await expect(diagnostics).toHaveJSProperty('open', false)
    await expect(
      settingsDialog.locator('[data-wazzup-connection-warning]'),
    ).toHaveCount(0)
    if (process.env.WAZZUP_E2E_ARTIFACTS)
      await settingsDialog.screenshot({
        path: join(
          process.env.WAZZUP_E2E_ARTIFACTS,
          `partner-${platform}-active.png`,
        ),
      })
    await settingsDialog
      .getByText('Connection details', { exact: true })
      .click()
    await expect(diagnostics).toHaveJSProperty('open', true)
    await expect(diagnostics.locator('dl')).toBeVisible()
    await expect(
      diagnostics.locator('[data-diagnostic="remote_channel"]'),
    ).toContainText('Channel Connected')
    await expect(
      diagnostics.locator('[data-diagnostic="account"]'),
    ).toContainText('Verified')
    await expect(
      diagnostics.locator('[data-diagnostic="subscription"]'),
    ).toContainText('Configured')
    await expect(diagnostics).toContainText(/\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}/)
    await expect(diagnostics).not.toContainText(/\d{2}:\d{2}:\d{2}\.\d+/)
    if (process.env.WAZZUP_E2E_ARTIFACTS)
      await settingsDialog.screenshot({
        path: join(
          process.env.WAZZUP_E2E_ARTIFACTS,
          `partner-${platform}-details.png`,
        ),
      })
    await settingsDialog
      .getByRole('button', { name: 'Reauthorize account', exact: true })
      .click()
    await expect(settingsDialog.locator('[data-wazzup-qr]')).toHaveCount(0)
    await settingsDialog.locator('[data-wazzup-confirm-reauthorize]').click()
    await expect(settingsDialog.locator('[data-wazzup-qr]')).toBeVisible()
    await expect(
      page
        .getByRole('dialog')
        .filter({ has: page.locator('[data-wazzup-partner-connection]') }),
    ).toHaveCount(1)
    await completeQr(page, platform)
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
      { waitUntil: 'domcontentloaded', timeout: 60000 },
    )
    await expect(
      page.getByRole('tab', { name: 'Messages', exact: true }),
    ).toHaveAttribute('aria-selected', 'true', { timeout: 60000 })
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
    const orders: FirstPhase[][] =
      platform === 'whatsapp'
        ? [['http', 'status', 'echo']]
        : [
            ['http', 'status', 'echo'],
            ['http', 'echo', 'status'],
            ['status', 'http', 'echo'],
            ['status', 'echo', 'http'],
            ['echo', 'http', 'status'],
            ['echo', 'status', 'http'],
          ]
    for (const order of orders) {
      await test.step(`First outbound: ${order.join(' → ')}`, async () => {
        await firstOutbound(page, testInfo, platform, name, order)
      })
    }
    await test.step('Temporary null echo followed by the exact late chat identity', async () => {
      await firstOutbound(
        page,
        testInfo,
        platform,
        name,
        ['echo', 'status', 'http'],
        true,
      )
    })

    await test.step('Disconnect preserves history and the other channel; restore keeps authorization', async () => {
      async function history() {
        const response = await page.request.get(
          '/api/resource/Messenger Message',
          {
            params: {
              fields: JSON.stringify([
                'name',
                'conversation',
                'direction',
                'text',
              ]),
              filters: JSON.stringify([['channel', '=', channel.name]]),
              order_by: 'name asc',
              limit_page_length: '100',
            },
          },
        )
        expect(response.ok()).toBeTruthy()
        return (await response.json()).data
      }

      const historyBefore = await history()
      const conversationsBefore = await conversations()
      expect(historyBefore.length).toBeGreaterThanOrEqual(3)
      await openMessageChannels(page)
      await page
        .getByRole('button', { name: 'New Channel', exact: true })
        .click()
      await dialog.getByRole('combobox', { name: /^Provider/ }).click()
      await page.getByRole('option', { name: label, exact: true }).click()
      const siblingName = `Manual Partner ${platform} sibling`
      await dialog.getByLabel('Channel Name', { exact: true }).fill(siblingName)
      await dialog
        .getByRole('button', { name: 'Create Channel', exact: true })
        .click()
      await expect(settingsDialog.locator('[data-wazzup-qr]')).toBeVisible()
      await completeQr(page, platform)
      await settingsDialog
        .getByRole('button', { name: 'Close', exact: true })
        .last()
        .click()
      const sibling = (await channels(page)).find(
        (row) => row.custom_display_name === siblingName,
      )
      expect(sibling).toMatchObject({ enabled: 1, wazzup_status: 'active' })
      if (!sibling)
        throw new Error('The independent second channel was not created.')

      await page.getByRole('button').filter({ hasText: name }).click()
      await settingsDialog
        .getByRole('button', { name: 'Disconnect', exact: true })
        .click()
      await expect(
        settingsDialog.getByText('Channel Disabled', { exact: true }),
      ).toBeVisible()
      await expect(settingsDialog.locator('[data-wazzup-qr]')).toHaveCount(0)
      expect(
        (await channels(page)).find((row) => row.name === channel.name),
      ).toMatchObject({
        enabled: 0,
        wazzup_status: 'active',
        provider_channel_id: channel.provider_channel_id,
      })
      expect(
        (await channels(page)).find((row) => row.name === sibling.name),
      ).toMatchObject({
        enabled: 1,
        wazzup_status: 'active',
        provider_channel_id: sibling.provider_channel_id,
      })
      await settingsDialog
        .getByRole('button', { name: 'Close', exact: true })
        .last()
        .click()

      const conversationUrl = `/crm/leads/${encodeURIComponent(conversation.reference_name)}?messenger_conversation=${encodeURIComponent(conversation.name)}#messenger`
      await page.goto(conversationUrl, {
        waitUntil: 'domcontentloaded',
        timeout: 60000,
      })
      await expect(page.getByText(inboundText, { exact: true })).toBeVisible()
      await expect(page.getByText(outboundText, { exact: true })).toBeVisible()
      await expect(
        page.locator('textarea[placeholder="Enter a message..."]'),
      ).toBeDisabled()
      await expect(
        page.getByRole('button', { name: 'Send', exact: true }),
      ).toBeDisabled()
      expect(await history()).toEqual(historyBefore)
      expect(await conversations()).toEqual(conversationsBefore)

      // Account subscriptions must stay active when one local channel is paused.
      const siblingText = `${platform} independent channel remains connected`
      await incoming(siblingName, platform, siblingText)
      await expect
        .poll(
          async () => {
            const response = await page.request.get(
              '/api/resource/Messenger Message',
              {
                params: {
                  fields: JSON.stringify(['name']),
                  filters: JSON.stringify([
                    ['channel', '=', sibling.name],
                    ['text', '=', siblingText],
                  ]),
                },
              },
            )
            expect(response.ok()).toBeTruthy()
            return (await response.json()).data.length
          },
          { timeout: 45000 },
        )
        .toBe(1)

      await openMessageChannels(page)
      await page.getByRole('button').filter({ hasText: name }).click()
      await expect(
        settingsDialog.getByText('Channel Disabled', { exact: true }),
      ).toBeVisible()
      await settingsDialog
        .getByRole('button', { name: 'Refresh Status', exact: true })
        .click()
      await expect(
        settingsDialog.getByText('Channel Disabled', { exact: true }),
      ).toBeVisible()
      await settingsDialog
        .getByRole('button', { name: 'Connect / Restore', exact: true })
        .click()
      await expect(
        settingsDialog
          .getByText('Channel Connected', { exact: true })
          .and(settingsDialog.locator(':visible')),
      ).toHaveCount(1)
      await expect(settingsDialog.locator('[data-wazzup-qr]')).toHaveCount(0)
      await expect(settingsDialog.locator('[data-wazzup-2fa]')).toHaveCount(0)
      expect(
        (await channels(page)).find((row) => row.name === channel.name),
      ).toMatchObject({
        enabled: 1,
        wazzup_status: 'active',
        provider_channel_id: channel.provider_channel_id,
      })
      expect(await history()).toEqual(historyBefore)
      expect(await conversations()).toEqual(conversationsBefore)
      await settingsDialog
        .getByRole('button', { name: 'Close', exact: true })
        .last()
        .click()
      await page.goto(conversationUrl, {
        waitUntil: 'domcontentloaded',
        timeout: 60000,
      })
      await expect(
        page.locator('textarea[placeholder="Enter a message..."]'),
      ).toBeEnabled()
      const resumedText = `${platform} incoming after restore without a new QR`
      await incoming(name, platform, resumedText)
      await expect(page.getByText(resumedText, { exact: true })).toBeVisible({
        timeout: 30000,
      })
      await expect(page.getByText(inboundText, { exact: true })).toHaveCount(1)
      await expect(page.getByText(outboundText, { exact: true })).toHaveCount(1)

      // Destructive provider removal stays behind the collapsed details and a
      // separate confirmation. Cancel must preserve the channel and history.
      const historyBeforeDelete = await history()
      await openMessageChannels(page)
      await page.getByRole('button').filter({ hasText: name }).click()
      await expect(
        settingsDialog.locator('[data-wazzup-partner-diagnostics]'),
      ).toHaveJSProperty('open', false)
      await settingsDialog
        .getByText('Connection details', { exact: true })
        .click()
      await settingsDialog
        .getByRole('button', { name: 'Delete Channel', exact: true })
        .click()
      await expect(
        settingsDialog.locator('[data-wazzup-confirm-delete]'),
      ).toBeVisible()
      await settingsDialog
        .getByRole('button', { name: 'Cancel', exact: true })
        .click()
      await expect(
        settingsDialog.locator('[data-wazzup-confirm-delete]'),
      ).toHaveCount(0)
      expect(
        (await channels(page)).some((row) => row.name === channel.name),
      ).toBe(true)
      expect(await history()).toEqual(historyBeforeDelete)
      await settingsDialog
        .getByRole('button', { name: 'Delete Channel', exact: true })
        .click()
      await settingsDialog.locator('[data-wazzup-confirm-delete]').click()
      await expect(settingsDialog).not.toBeVisible()
      await expect
        .poll(async () =>
          (await channels(page)).some((row) => row.name === channel.name),
        )
        .toBe(false)
      expect(await history()).toEqual(historyBeforeDelete)
      expect(
        (await channels(page)).find((row) => row.name === sibling.name),
      ).toMatchObject({
        enabled: 1,
        wazzup_status: 'active',
      })
    })
  })
}
