import { createHash } from 'node:crypto'
import { chmodSync, writeFileSync } from 'node:fs'
import { expect, request as playwrightRequest, test } from '@playwright/test'
import { loadWazzupFixture } from './wazzup-local-fixture'

const fixture = loadWazzupFixture()
const sendMethod = 'crm_messenger.api.messages.send_message'
const uploadMethod = 'crm_messenger.api.attachments.upload_temporary_file'

function scriptDiagnostic(error: Error) {
  const kind = error.message.match(
    /\b(?:CSRFTokenError|AuthenticationError|PermissionError|RangeError|TypeError)\b/,
  )?.[0]
  const frames = (error.stack || '')
    .split('\n')
    .slice(1)
    .map(
      (line) =>
        line.match(
          /\/(?:src|node_modules)\/[A-Za-z0-9_./-]+(?::\d+:\d+)?/,
        )?.[0],
    )
    .filter(Boolean)
    .slice(0, 6)
  // Keep error types and source paths; omit arbitrary messages, tokens and URL
  // query strings from browser artifacts.
  return [error.name, kind, ...frames].filter(Boolean).join(' | ')
}

type Message = {
  name: string
  direction: string
  text: string
  status: string
  delivery_status: string
  attempt_count: number
  external_message_id: string | null
  next_retry_at: string | null
  attachment_count: number
  files: {
    name: string
    file_name: string
    is_private: number
    file_size: number
  }[]
}

type State = {
  lead: string | null
  conversation: string | null
  messages: Message[]
  simulator: {
    count: number
    calls: {
      message_id: string
      crm_message_id: string
      mode: string
      authorized: boolean
      is_media: boolean
      fetch_status?: number
      fetch_size?: number
      fetch_sha256?: string
    }[]
    http_callbacks: { kind: string; status: number }[]
  }
  queue: { queued: number; started: number; failed: number }
}

// Both platforms use the complete CRM application, actual Frappe HTTP and RQ.
// There is intentionally no page.route(), mocked RPC or test-only Vue entry.
for (const platform of ['whatsapp', 'telegram']) {
  test(`Wazzup ${platform}: real CRM, HTTP worker, private media and ambiguous delivery`, async ({
    page,
  }, testInfo) => {
    const traffic: Record<string, number> = {}
    const clientRequestIds = new Map<string, string>()
    let externalResponses = 0
    const embeddedResponseProtocols: Record<string, number> = {}
    const externalResponseOrigins: Record<string, number> = {}
    const scriptErrors: string[] = []
    const moduleErrors: string[] = []
    let socketConnected = false
    // Observe the real Socket.IO namespace acknowledgement, including either
    // polling or WebSocket transport. Never persist its session identifier.
    const observeSocketFrames = (payload: string | Buffer) => {
      if (
        payload
          .toString()
          .split('\x1e')
          .some((frame) => frame.startsWith('40/'))
      ) {
        socketConnected = true
      }
    }
    page.on('websocket', (socket) => {
      if (new URL(socket.url()).pathname !== '/socket.io/') return
      socket.on('framereceived', ({ payload }) => observeSocketFrames(payload))
    })
    page.on('pageerror', (error) => {
      const diagnostic = scriptDiagnostic(error)
      scriptErrors.push(diagnostic)
      testInfo.annotations.push({
        type: 'crm-script-error',
        description: diagnostic,
      })
    })
    page.on('response', async (response) => {
      const url = new URL(response.url())
      if (url.protocol === 'http:' || url.protocol === 'https:') {
        if (url.hostname !== '127.0.0.1') {
          externalResponses += 1
          externalResponseOrigins[url.origin] =
            (externalResponseOrigins[url.origin] || 0) + 1
        }
      } else {
        // Browser-generated blob/data responses are local media, not HTTP I/O.
        embeddedResponseProtocols[url.protocol] =
          (embeddedResponseProtocols[url.protocol] || 0) + 1
      }
      if (
        url.pathname === '/socket.io/' &&
        url.searchParams.get('transport') === 'polling' &&
        response.ok()
      ) {
        try {
          observeSocketFrames(await response.body())
        } catch {
          // Socket.IO polling may close while upgrading to WebSocket.
        }
      }
      if (
        url.hostname === '127.0.0.1' &&
        response.status() >= 400 &&
        /\.(js|ts|vue)$/.test(url.pathname)
      ) {
        const diagnostic = `${response.status()} ${url.pathname}`
        moduleErrors.push(diagnostic)
        testInfo.annotations.push({
          type: 'crm-module-http-error',
          description: diagnostic,
        })
      }
    })
    page.on('request', (request) => {
      const match = new URL(request.url()).pathname.match(
        /^\/api\/method\/(.+)$/,
      )
      if (!match) return
      const method = match[1]
      if (
        method.startsWith('crm_messenger.') ||
        method === 'crm.www.crm.get_context_for_dev'
      ) {
        traffic[method] = (traffic[method] || 0) + 1
      }
    })

    async function control<T = unknown>(action: string, data = {}): Promise<T> {
      const response = await page.request.post(
        `${fixture.simulator_origin}/control/${action}`,
        {
          headers: { Authorization: `Bearer ${fixture.control_token}` },
          data,
        },
      )
      expect(
        response.ok(),
        `isolated control ${action} must succeed`,
      ).toBeTruthy()
      const result = await response.json()
      if (Object.hasOwn(result, 'ok')) {
        expect(
          result.ok,
          `isolated control ${action} must complete its HTTP operation`,
        ).toBeTruthy()
      }
      return result
    }

    const state = () => control<State>('state')
    const login = await page.request.post('/api/method/login', {
      form: { usr: fixture.user, pwd: fixture.password },
    })
    expect(login.ok(), 'real Frappe login must succeed').toBeTruthy()
    await control('select', { platform })
    await control('mode', { mode: 'accepted' })
    const authProbes = await control('auth-probes')
    expect(authProbes).toEqual({
      valid: 200,
      invalid: 403,
      missing: 403,
      other_rpc: 401,
      cmd_override: 401,
    })

    // Let the current production Lead intake policy handle the first event.
    await control('inbound')
    await expect
      .poll(async () => Boolean((await state()).conversation))
      .toBe(true)
    const initial = await state()
    expect(initial.lead).toBeTruthy()
    const leadUrl = `/crm/leads/${encodeURIComponent(initial.lead!)}?messenger_conversation=${encodeURIComponent(initial.conversation!)}#messenger`
    const startupFailure = new Promise<never>((_, reject) => {
      page.once('pageerror', (error) =>
        reject(
          new Error(`CRM UI startup failed (${scriptDiagnostic(error)}).`),
        ),
      )
    })
    await Promise.race([
      (async () => {
        await page.goto(leadUrl, {
          waitUntil: 'domcontentloaded',
          timeout: 60000,
        })
        await expect(
          page.getByRole('tab', { name: 'Messages', exact: true }),
        ).toHaveAttribute('aria-selected', 'true', { timeout: 60000 })
      })(),
      startupFailure,
    ])
    await expect(
      page.getByText(fixture.inbound_text, { exact: true }),
    ).toBeVisible()
    await expect(
      page.locator('textarea[placeholder="Enter a message..."]'),
    ).toBeEnabled()
    await expect
      .poll(() => socketConnected, {
        message: 'real Frappe Socket.IO authentication must complete',
      })
      .toBe(true)

    // The exact dev UI origin is trusted through native Frappe configuration.
    // A foreign origin with the same authenticated cookie still requires CSRF.
    const beforeCsrf = await state()
    const csrfProbe = await page.request.post(`/api/method/${sendMethod}`, {
      headers: {
        Origin: 'https://foreign.example.invalid',
        Referer: 'https://foreign.example.invalid/',
      },
      data: {
        conversation: initial.conversation,
        text: 'This request must be rejected by CSRF validation.',
        client_request_id: `local-csrf-probe-${platform}`,
        reference_doctype: 'CRM Lead',
        reference_name: initial.lead,
      },
    })
    expect([400, 403]).toContain(csrfProbe.status())
    expect((await csrfProbe.json()).exc_type).toBe('CSRFTokenError')
    const afterCsrf = await state()
    expect(afterCsrf.simulator.count).toBe(beforeCsrf.simulator.count)
    expect(afterCsrf.messages.map((row) => row.name)).toEqual(
      beforeCsrf.messages.map((row) => row.name),
    )

    // A second real webhook arrives after the UI has mounted. The normal sync
    // controller must bring it into the existing page without a manual refresh.
    const liveInbound = `${fixture.inbound_text} — ${platform} live update`
    await control('inbound', { text: liveInbound })
    await expect(page.getByText(liveInbound, { exact: true })).toBeVisible({
      timeout: 30000,
    })

    async function sendText(text: string) {
      await page
        .locator('textarea[placeholder="Enter a message..."]')
        .fill(text)
      return sendFromComposer()
    }

    async function sendFromComposer() {
      const responsePromise = page.waitForResponse(
        (response) =>
          new URL(response.url()).pathname === `/api/method/${sendMethod}` &&
          response.request().method() === 'POST',
      )
      await page.getByRole('button', { name: 'Send', exact: true }).click()
      const response = await responsePromise
      expect(
        response.ok(),
        'UI send must cross the real Frappe HTTP handler',
      ).toBeTruthy()
      const result = (await response.json()).message
      expect(result.ok).toBeTruthy()
      expect(result.name).toBeTruthy()
      expect(result.client_request_id).toBeTruthy()
      clientRequestIds.set(result.name, result.client_request_id)
      await expect(
        page.locator(`[data-message-id="${result.name}"]`),
      ).toBeVisible()
      return result.name as string
    }

    async function waitMessage(name: string, status: string) {
      await expect
        .poll(
          async () =>
            (await state()).messages.find((row) => row.name === name)
              ?.delivery_status,
          { timeout: 45000 },
        )
        .toBe(status)
      const current = await state()
      return current.messages.find((row) => row.name === name)!
    }

    async function publicMessage(name: string) {
      const response = await page.request.get(
        '/api/method/crm_messenger.api.messages.get_message',
        { params: { message: name } },
      )
      expect(response.ok()).toBeTruthy()
      const projection = (await response.json()).message.message
      const serialized = JSON.stringify(projection)
      expect(
        /contentUri|provider_response|api_token|webhook_secret|store\.wazzup24\.com|crm_messenger\.api\.wazzup_media\.download/.test(
          serialized,
        ),
        'public message must not expose credentials, provider payloads or grants',
      ).toBe(false)
      return projection
    }

    async function expectUiStatus(name: string, label: string) {
      const row = page.locator(`[data-message-id="${name}"]`)
      const icon = row.locator('[data-message-delivery]')
      await expect(icon).toHaveClass(
        label === 'Read by recipient' ? /text-ink-blue-5/ : /text-ink-red-8/,
        { timeout: 30000 },
      )
      await expect(async () => {
        await page.mouse.move(0, 0)
        await icon.hover()
        // Reka renders role=tooltip on a hidden accessibility description.
        // Assert the visible popover instead, re-hovering if sync remounts it.
        await expect(
          page
            .locator('[data-reka-popper-content-wrapper] .rounded')
            .filter({ hasText: label }),
        ).toBeVisible({ timeout: 1500 })
      }).toPass({ timeout: 30000 })
      await page.mouse.move(0, 0)
    }

    const beforeText = (await state()).simulator.count
    const outboundText = `${platform} real UI outbound text`
    const textMessage = await sendText(outboundText)
    await waitMessage(textMessage, 'sent')
    let current = await state()
    expect(current.simulator.count).toBe(beforeText + 1)
    expect(current.simulator.calls.at(-1)?.authorized).toBe(true)
    expect(current.simulator.calls.at(-1)?.crm_message_id).toBe(
      clientRequestIds.get(textMessage),
    )
    await control('echo', {
      index: current.simulator.count - 1,
      status: 'read',
    })
    const readText = await waitMessage(textMessage, 'read')
    expect(readText.external_message_id).toBe(
      current.simulator.calls.at(-1)?.message_id,
    )
    current = await state()
    expect(
      current.messages.filter((row) => row.text === outboundText),
    ).toHaveLength(1)
    await expectUiStatus(textMessage, 'Read by recipient')
    await publicMessage(textMessage)

    // This is the production private multipart upload control and send button.
    const bytes = Buffer.from(fixture.file_content, 'utf8')
    const uploadPromise = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === `/api/method/${uploadMethod}` &&
        response.request().method() === 'POST',
    )
    await page
      .getByRole('tabpanel', { name: 'Messages', exact: true })
      .locator('input[type="file"]')
      .setInputFiles({
        name: fixture.file_name,
        mimeType: 'text/plain',
        buffer: bytes,
      })
    expect((await uploadPromise).ok()).toBeTruthy()
    await expect(page.getByText('Ready', { exact: true })).toBeVisible()
    const beforeFile = (await state()).simulator.count
    const fileMessage = await sendFromComposer()
    await waitMessage(fileMessage, 'sent')
    current = await state()
    expect(current.simulator.count).toBe(beforeFile + 1)
    const mediaCall = current.simulator.calls.at(-1)!
    expect(mediaCall.is_media).toBe(true)
    expect(mediaCall.fetch_status).toBe(200)
    expect(mediaCall.fetch_size).toBe(bytes.length)
    expect(mediaCall.fetch_sha256).toBe(
      createHash('sha256').update(bytes).digest('hex'),
    )
    const fileRow = current.messages.find((row) => row.name === fileMessage)!
    expect(fileRow.attachment_count).toBe(1)
    expect(fileRow.files).toHaveLength(1)
    expect(fileRow.files[0].is_private).toBe(1)
    await control('echo', {
      index: current.simulator.count - 1,
      status: 'read',
    })
    await waitMessage(fileMessage, 'read')
    current = await state()
    expect(
      current.messages.filter(
        (row) => row.external_message_id === mediaCall.message_id,
      ),
    ).toHaveLength(1)
    await expect(
      page.locator(
        `[data-message-id="${fileMessage}"] [data-attachment-card-title]`,
      ),
    ).toHaveText(fixture.file_name)
    await expectUiStatus(fileMessage, 'Read by recipient')
    const projection = await publicMessage(fileMessage)
    expect(projection.attachments).toHaveLength(1)
    const downloadUrl = projection.attachments[0].download_url
    expect(downloadUrl).toBeTruthy()
    const authenticatedDownload = await page.request.get(downloadUrl)
    expect(authenticatedDownload.ok()).toBeTruthy()
    expect((await authenticatedDownload.body()).equals(bytes)).toBe(true)
    const disposition = authenticatedDownload.headers()['content-disposition']
    expect(disposition).toMatch(/^attachment; filename\*=UTF-8''/)
    expect(decodeURIComponent(disposition.split("UTF-8''")[1])).toBe(
      fixture.file_name,
    )
    const guest = await playwrightRequest.newContext({
      baseURL: fixture.base_url,
    })
    try {
      const denied = await guest.get(downloadUrl, { maxRedirects: 0 })
      expect([401, 403]).toContain(denied.status())
      expect(
        (await denied.body()).equals(bytes),
        'a guest must not receive private bytes',
      ).toBe(false)
    } finally {
      await guest.dispose()
    }

    const ambiguous: { mode: string; message: string; attempts: number }[] = []
    for (const mode of [
      'timeout',
      'http_5xx',
      'invalid_response',
      'disconnect',
    ]) {
      await control('mode', { mode })
      const before = (await state()).simulator.count
      const message = await sendText(`${platform} ambiguous ${mode}`)
      const unknown = await waitMessage(message, 'unknown')
      expect(unknown.attempt_count).toBe(1)
      expect(unknown.next_retry_at).toBeNull()
      expect((await state()).simulator.count).toBe(before + 1)
      await expectUiStatus(message, 'Result unknown')
      const publicUnknown = await publicMessage(message)
      expect(publicUnknown.delivery_status).toBe('unknown')
      expect(publicUnknown.can_retry).toBe(false)
      const actions = page
        .locator(`[data-message-id="${message}"]`)
        .getByRole('button', { name: 'Message Actions', exact: true })
      if (await actions.count()) {
        await actions.click()
        await expect(
          page.getByRole('menuitem', { name: 'Retry Sending', exact: true }),
        ).toHaveCount(0)
        await page.keyboard.press('Escape')
      }

      // Run the real recovery scan and worker guard for the same persisted row.
      // Neither operation is permitted to dispatch a second provider request.
      await control('recover')
      await control('reprocess', { message })
      await expect
        .poll(async () => {
          const queued = (await state()).queue
          return queued.queued + queued.started
        })
        .toBe(0)
      await page.reload()
      await expect(page.locator(`[data-message-id="${message}"]`)).toBeVisible()
      await expectUiStatus(message, 'Result unknown')
      current = await state()
      expect(current.simulator.count).toBe(before + 1)
      expect(
        current.messages.find((row) => row.name === message)?.attempt_count,
      ).toBe(1)
      expect(
        current.messages.find((row) => row.name === message)?.delivery_status,
      ).toBe('unknown')
      expect(
        current.messages.find((row) => row.name === message)?.next_retry_at,
      ).toBeNull()
      expect(current.queue.failed).toBe(0)
      ambiguous.push({ mode, message, attempts: 1 })
    }

    expect(traffic[sendMethod]).toBe(6)
    expect(traffic[uploadMethod]).toBe(1)
    expect(
      scriptErrors,
      'the real CRM must finish without script failures',
    ).toHaveLength(0)
    expect(
      moduleErrors,
      'the real CRM must load its actual source modules',
    ).toHaveLength(0)
    expect(
      externalResponses,
      `the isolated browser must not receive external HTTP responses: ${JSON.stringify(externalResponseOrigins)}`,
    ).toBe(0)
    expect(traffic['crm.www.crm.get_context_for_dev']).toBeGreaterThan(0)
    expect(
      traffic['crm_messenger.api.messages.get_message_page'],
    ).toBeGreaterThan(0)
    expect(
      traffic['crm_messenger.api.messages.get_message_changes'],
    ).toBeGreaterThan(0)
    current = await state()
    expect(
      current.simulator.http_callbacks
        .filter((row) => row.kind === 'webhook')
        .every((row) => row.status === 200),
    ).toBe(true)
    const evidence = {
      platform,
      traffic,
      externalResponses,
      embeddedResponseProtocols,
      socketConnected,
      csrfProbe: csrfProbe.status(),
      authProbes,
      inbound: 2,
      textMessage,
      fileMessage,
      privateFile: true,
      grantSha256: mediaCall.fetch_sha256,
      ambiguous,
      queue: current.queue,
    }
    // The list reporter keeps Buffer attachments in memory. Persist the safe
    // evidence ourselves, then attach its path so every successful run retains
    // reviewable HTTP counts and safety checks with owner-only permissions.
    const evidencePath = testInfo.outputPath('real-http-evidence.json')
    chmodSync(testInfo.outputDir, 0o700)
    writeFileSync(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`, {
      mode: 0o600,
      flag: 'wx',
    })
    await testInfo.attach('real-http-evidence', {
      contentType: 'application/json',
      path: evidencePath,
    })
    const attachment = testInfo.attachments.find(
      (item) => item.name === 'real-http-evidence',
    )
    if (attachment?.path) chmodSync(attachment.path, 0o600)
  })
}
