import {
  callWazzupPartner,
  normalizePartnerConnection,
  safeWazzupQrImage,
  wazzupPartnerDiagnosticRows,
  wazzupPartnerStatus,
} from '@/utils/wazzupPartnerConnection'

const PNG = 'data:image/png;base64,aGVsbG8='

describe('Wazzup Partner onboarding RPC privacy', () => {
  let previousCsrf
  beforeEach(() => {
    previousCsrf = window.csrf_token
    vi.stubGlobal('fetch', vi.fn())
  })
  afterEach(() => {
    window.csrf_token = previousCsrf
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  function response(overrides = {}) {
    return {
      ok: true,
      channel: {
        name: 'PARTNER-1',
        platform: 'telegram',
        wazzup_api_mode: 'partner_api_v2',
        wazzup_status: 'waiting_2fa',
      },
      onboarding: { status: 'waiting_2fa', can_submit_2fa: true },
      simulator: true,
      ...overrides,
    }
  }

  it('sends a transient password only to the same-origin 2FA endpoint with CSRF', async () => {
    window.csrf_token = 'csrf-test'
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ message: response() }),
    })
    const store = vi.spyOn(Storage.prototype, 'setItem')
    await callWazzupPartner('submit_2fa', {
      channel: 'PARTNER-1',
      password: 'private-password',
      client_access_token: 'must-not-be-sent',
      partner_secret: 'must-not-be-sent',
    })
    expect(fetch.mock.calls[0]).toEqual([
      '/api/method/crm_messenger.api.wazzup_partner.submit_2fa',
      {
        method: 'POST',
        credentials: 'same-origin',
        redirect: 'error',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json; charset=utf-8',
          'X-Frappe-Site-Name': window.location.hostname,
          'X-Frappe-CSRF-Token': 'csrf-test',
        },
        body: JSON.stringify({
          channel: 'PARTNER-1',
          password: 'private-password',
        }),
      },
    ])
    expect(store).not.toHaveBeenCalled()
  })

  it('drops credential fields and arbitrary provider errors from a successful response', async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        message: response({
          client_access_token: 'client-private',
          machine_token: 'machine-private',
          channel: {
            name: 'PARTNER-1',
            platform: 'telegram',
            api_token: 'key-private',
          },
          onboarding: {
            status: 'waiting_2fa',
            error: 'raw-provider-private',
            password: 'password-private',
          },
        }),
      }),
    })
    const result = await callWazzupPartner('get_onboarding_state', {
      channel: 'PARTNER-1',
    })
    for (const secret of [
      'client-private',
      'machine-private',
      'key-private',
      'raw-provider-private',
      'password-private',
    ]) {
      expect(JSON.stringify(result)).not.toContain(secret)
    }
    expect(result.onboarding.has_error).toBe(true)
  })

  it('checks only the selected Partner channel and keeps safe account diagnostics', async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        message: response({
          integration: {
            wazzup_connection: { api_token: 'legacy-secret' },
            wazzup_partner: {
              status: 'waiting_2fa',
              last_checked_at: '2026-10-13 12:00:00',
              reconciliation: { status: 'verified', reason: 'private-error' },
              account: {
                status: 'ready',
                enabled: true,
                name: 'private-tenant',
              },
              webhook_subscription: {
                status: 'configured',
                last_checked_at: '2026-10-13 11:59:00',
                url: 'private-url',
                access_token: 'private-webhook-token',
              },
              delivery: { status: 'unverified', raw_data: 'private-payload' },
              client_access_token: 'private-token',
            },
          },
        }),
      }),
    })
    const result = await callWazzupPartner('check_channel', {
      channel: 'PARTNER-1',
      account: 'untrusted-tenant',
      api_token: 'untrusted-token',
    })
    expect(fetch.mock.calls[0][0]).toBe(
      '/api/method/crm_messenger.api.wazzup_partner.check_channel',
    )
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      channel: 'PARTNER-1',
    })
    expect(result.channel.integration).toEqual(result.integration)
    expect(JSON.stringify(result)).not.toMatch(/private-|legacy-secret/)
    const rows = wazzupPartnerDiagnosticRows(result.integration.wazzup_partner)
    expect(rows.find((row) => row.key === 'remote_channel').label).toBe(
      'Two-factor authentication required',
    )
    expect(rows.find((row) => row.key === 'subscription').label).toBe(
      'Configured',
    )
    expect(rows.find((row) => row.key === 'subscription').checked_at).toBe(
      '2026-10-13 11:59:00',
    )
    expect(rows.find((row) => row.key === 'delivery').label).toBe(
      'No event observed',
    )
  })

  it.each([
    ['configured', 'Configured', 'green'],
    ['stale', 'Needs Attention', 'orange'],
    ['unknown', 'Result unknown', 'orange'],
    ['error', 'Could not verify', 'orange'],
    ['unverified', 'Not checked', 'gray'],
    ['__proto__', 'Not checked', 'gray'],
  ])(
    'keeps %s webhook evidence separate from channel authorization and incoming delivery',
    (status, label, theme) => {
      const normalized = normalizePartnerConnection(
        response({
          integration: {
            wazzup_partner: {
              status: 'active',
              account: { status: 'ready', enabled: true },
              webhook_subscription: {
                status,
                last_checked_at: 'private-invalid-timestamp',
                callback_url: 'private-url',
                refresh_token: 'private-token',
              },
              delivery: {
                status: 'received',
                last_received_at: '2026-10-13 12:00:00',
                event_type: 'message.add',
              },
            },
          },
        }),
      )
      const rows = wazzupPartnerDiagnosticRows(
        normalized.integration.wazzup_partner,
      )
      expect(rows.find((row) => row.key === 'subscription')).toMatchObject({
        label,
        theme,
        checked_at: '',
      })
      expect(rows.find((row) => row.key === 'account').label).toBe('Verified')
      expect(rows.find((row) => row.key === 'delivery').label).toBe(
        'Event received',
      )
      expect(JSON.stringify(normalized)).not.toContain('private-')
    },
  )

  it.each([
    ['disabled', 'Channel Disabled'],
    ['deleted', 'Channel Deleted'],
    ['reconnecting', 'Reconnecting'],
    ['provisioning', 'Preparing connection'],
    ['provider-state-unrecognized', 'Result unknown'],
  ])(
    'keeps %s visible without claiming that the channel is connected',
    (status, label) => {
      const normalized = normalizePartnerConnection(
        response({
          onboarding: { status },
          channel: { name: 'PARTNER-1', wazzup_status: status },
        }),
      )
      expect(wazzupPartnerStatus(normalized.onboarding.status).label).toBe(
        label,
      )
      expect(normalized.onboarding.qr_code).toBe('')
    },
  )

  it('reports failed verification separately from observed delivery', () => {
    const normalized = normalizePartnerConnection(
      response({
        integration: {
          wazzup_partner: {
            status: 'active',
            reconciliation: { status: 'error' },
            account: { status: 'ready', enabled: true },
            delivery: {
              status: 'received',
              last_received_at: '2026-10-13 12:00:00',
              event_type: 'message.add',
            },
          },
        },
      }),
    )
    const rows = wazzupPartnerDiagnosticRows(
      normalized.integration.wazzup_partner,
    )
    expect(rows.find((row) => row.key === 'remote_channel').label).toBe(
      'Could not verify',
    )
    expect(rows.find((row) => row.key === 'delivery')).toMatchObject({
      label: 'Event received',
      event_label: 'Incoming message',
    })
  })

  it.each([
    {
      ok: false,
      data: {
        exc: 'private-password',
        _server_messages: 'raw private-password',
      },
    },
    { ok: true, data: { exc: 'private-password', message: response() } },
  ])(
    'never logs or renders exception details on rejected requests',
    async ({ ok, data }) => {
      fetch.mockResolvedValue({ ok, json: async () => data })
      const logs = ['log', 'error', 'warn', 'groupCollapsed'].map((name) =>
        vi.spyOn(console, name).mockImplementation(() => {}),
      )
      await expect(
        callWazzupPartner('submit_2fa', {
          channel: 'PARTNER-1',
          password: 'private-password',
        }),
      ).rejects.toThrow(
        'Could not submit the password. Refresh the connection status.',
      )
      logs.forEach((log) => expect(log).not.toHaveBeenCalled())
    },
  )

  it('rejects unknown operations before HTTP and omits an unresolved CSRF placeholder', async () => {
    await expect(callWazzupPartner('arbitrary_method')).rejects.toThrow()
    expect(fetch).not.toHaveBeenCalled()
    window.csrf_token = '{{ csrf_token }}'
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ message: response() }),
    })
    await callWazzupPartner('reconnect', { channel: 'PARTNER-1' })
    expect(fetch.mock.calls[0][1].headers).not.toHaveProperty(
      'X-Frappe-CSRF-Token',
    )
  })

  it('accepts only PNG data URI and removes QR data from other lifecycle states', () => {
    expect(safeWazzupQrImage(PNG)).toBe(PNG)
    for (const value of [
      'data:image/svg+xml,<svg onload="alert(1)"/>',
      'https://provider.test/qr.png',
      'data:text/html;base64,aGVsbG8=',
      'blob:https://crm.test/qr',
    ]) {
      expect(safeWazzupQrImage(value)).toBe('')
    }
    const value = response({
      onboarding: {
        status: 'waiting_qr',
        qr_code: PNG,
        qr_expires_at: '2026-10-07T23:00:00Z',
      },
    })
    expect(normalizePartnerConnection(value).onboarding.qr_code).toBe(PNG)
    value.onboarding.status = 'active'
    expect(normalizePartnerConnection(value).onboarding.qr_code).toBe('')
    expect(wazzupPartnerStatus('__proto__').label).toBe('Result unknown')
  })
})
