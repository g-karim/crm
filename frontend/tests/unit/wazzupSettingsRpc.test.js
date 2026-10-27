import { callWazzupSettings } from '@/utils/messengerSettings'

describe('Wazzup settings RPC credential privacy', () => {
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

  it('posts same-origin JSON with session credentials and CSRF without persisting the draft token', async () => {
    window.csrf_token = 'test-csrf'
    const result = { ok: true, channels: [] }
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ message: result }),
    })
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    expect(
      await callWazzupSettings(
        'crm_messenger.api.wazzup_connection.list_channels',
        { api_token: 'draft-secret' },
      ),
    ).toEqual(result)
    expect(fetch).toHaveBeenCalledWith(
      '/api/method/crm_messenger.api.wazzup_connection.list_channels',
      {
        method: 'POST',
        credentials: 'same-origin',
        redirect: 'error',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json; charset=utf-8',
          'X-Frappe-Site-Name': window.location.hostname,
          'X-Frappe-CSRF-Token': 'test-csrf',
        },
        body: JSON.stringify({ api_token: 'draft-secret' }),
      },
    )
    expect(setItem).not.toHaveBeenCalled()
  })

  it.each([
    {
      ok: true,
      data: { exc: '["raw exception draft-secret"]', message: { ok: true } },
    },
    {
      ok: false,
      data: {
        exc: '["private payload"]',
        _server_messages: '["raw provider draft-secret"]',
        _error_message: 'private error',
      },
    },
  ])(
    'discards raw server exceptions and messages without logging credentials',
    async ({ ok, data }) => {
      fetch.mockResolvedValue({ ok, json: async () => data })
      const spies = ['log', 'warn', 'error', 'groupCollapsed'].map((method) =>
        vi.spyOn(console, method).mockImplementation(() => {}),
      )
      await expect(
        callWazzupSettings(
          'crm_messenger.api.wazzup_connection.list_channels',
          { api_token: 'draft-secret' },
        ),
      ).rejects.toMatchObject({
        message: 'The provider operation failed.',
        messages: ['The provider operation failed.'],
      })
      spies.forEach((spy) => expect(spy).not.toHaveBeenCalled())
    },
  )

  it('keeps only an allowed server validation message and ignores exception details', async () => {
    fetch.mockResolvedValue({
      ok: false,
      json: async () => ({
        exc: 'private traceback',
        _server_messages: JSON.stringify([
          JSON.stringify({ message: 'Enter a Wazzup channel UUID.' }),
        ]),
      }),
    })
    await expect(
      callWazzupSettings('crm_messenger.api.settings.save_channel', {
        provider: 'wazzup',
        api_token: 'draft-secret',
      }),
    ).rejects.toMatchObject({
      message: 'Enter a Wazzup channel UUID.',
      messages: ['Enter a Wazzup channel UUID.'],
    })
  })

  it('normalizes network failures and rejects other methods without making a request', async () => {
    fetch.mockRejectedValue(new Error('private transport failure draft-secret'))
    await expect(
      callWazzupSettings('crm_messenger.api.wazzup_connection.check_channel', {
        channel: 'saved-channel',
      }),
    ).rejects.toThrow('The provider operation failed.')
    fetch.mockClear()
    await expect(
      callWazzupSettings('arbitrary.method', { api_token: 'draft-secret' }),
    ).rejects.toThrow('The provider operation failed.')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('omits an unresolved CSRF placeholder and sends a saved-key reference without a token', async () => {
    window.csrf_token = '{{ csrf_token }}'
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ message: { ok: true, channels: [] } }),
    })
    await callWazzupSettings(
      'crm_messenger.api.wazzup_connection.list_channels',
      { channel: 'saved-channel' },
    )
    expect(fetch.mock.calls[0][1].headers).not.toHaveProperty(
      'X-Frappe-CSRF-Token',
    )
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      channel: 'saved-channel',
    })
  })

  it('keeps Shared Webhook Secret setup failures silent and never forwards a direct channel save', async () => {
    const log = vi.spyOn(console, 'log').mockImplementation(() => {})
    fetch.mockResolvedValue({
      ok: false,
      json: async () => ({
        exc: '["private webhook-secret-value exception"]',
        _error_message: 'webhook-secret-value',
      }),
    })
    await expect(
      callWazzupSettings('crm_messenger.api.settings.save_settings', {
        webhook_secret: 'webhook-secret-value',
        enabled: true,
      }),
    ).rejects.toMatchObject({
      message: 'The provider operation failed.',
      messages: ['The provider operation failed.'],
    })
    expect(log).not.toHaveBeenCalled()
    expect(fetch.mock.calls[0][1].redirect).toBe('error')
    fetch.mockClear()
    await expect(
      callWazzupSettings('crm_messenger.api.settings.save_channel', {
        provider: 'telegram_bot',
        api_token: 'bot-secret',
      }),
    ).rejects.toThrow('The provider operation failed.')
    expect(fetch).not.toHaveBeenCalled()
  })
})
