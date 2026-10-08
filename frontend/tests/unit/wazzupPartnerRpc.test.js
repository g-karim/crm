import {
  callWazzupPartner,
  normalizePartnerConnection,
  safeWazzupQrImage,
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
    expect(wazzupPartnerStatus('__proto__').label).toBe('Channel Not Connected')
  })
})
