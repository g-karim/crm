import {
  applyMessengerProviderDefaults,
  buildMessengerChannelPayload,
  makeMessengerChannelDraft,
  MESSENGER_PROVIDER_OPTIONS,
  messengerChannelState,
  validateMessengerChannelDraft,
} from '@/utils/messengerSettings'

describe('messengerSettings', () => {
  it('keeps the gateway brand out of customer-facing provider labels', () => {
    const gateway = MESSENGER_PROVIDER_OPTIONS.find(
      (option) => option.value === 'wazzup',
    )

    expect(gateway.label).toBe('WhatsApp & Telegram')
    expect(
      MESSENGER_PROVIDER_OPTIONS.map((option) => option.label).join(' '),
    ).not.toContain('Wazzup')
  })

  it('creates provider-aware drafts without exposing saved secrets', () => {
    expect(
      makeMessengerChannelDraft({
        name: 'telegram-1',
        provider: 'telegram_bot',
        enabled: 1,
        api_token_configured: true,
      }),
    ).toMatchObject({
      channel: 'telegram-1',
      platform: 'telegram',
      auth_type: 'api_token',
      api_token: '',
      api_token_configured: true,
    })
  })

  it('resets provider-owned fields when the provider changes', () => {
    let draft = makeMessengerChannelDraft()
    draft.provider = 'wazzup'
    draft.external_account_id = 'old'
    applyMessengerProviderDefaults(draft)
    expect(draft).toMatchObject({
      platform: 'whatsapp',
      auth_type: 'api_token',
      external_account_id: '',
      enabled: false,
    })
  })

  it('omits blank secrets so updates preserve encrypted values', () => {
    let draft = makeMessengerChannelDraft({
      name: 'wazzup-1',
      provider: 'wazzup',
      platform: 'whatsapp',
      provider_channel_id: 'channel-1',
      enabled: 1,
      api_token_configured: true,
    })
    expect(buildMessengerChannelPayload(draft)).toEqual({
      channel: 'wazzup-1',
      provider: 'wazzup',
      custom_display_name: '',
      platform: 'whatsapp',
      auth_type: 'api_token',
      provider_channel_id: 'channel-1',
      external_account_id: '',
      public_chat_url: '',
      api_base_url: '',
      client_id: '',
      enabled: true,
    })
  })

  it('validates required credentials for each provider', () => {
    expect(validateMessengerChannelDraft(makeMessengerChannelDraft())).toBe(
      'Enter an API token.',
    )

    let wazzup = makeMessengerChannelDraft({ provider: 'wazzup' })
    wazzup.api_token = 'secret'
    expect(validateMessengerChannelDraft(wazzup)).toBe('Enter a channel ID.')

    let avito = makeMessengerChannelDraft({ provider: 'avito_direct' })
    expect(validateMessengerChannelDraft(avito)).toBe(
      'Enter the Avito Client ID.',
    )
    avito.client_id = 'client-id'
    expect(validateMessengerChannelDraft(avito)).toBe(
      'Enter the Avito Client Secret.',
    )
    avito.client_secret = 'client-secret'
    expect(validateMessengerChannelDraft(avito)).toBe(
      'Enter the Avito import start date.',
    )
    avito.avito_import_from_date = '2025-01-01'
    expect(validateMessengerChannelDraft(avito)).toBe('')
    expect(buildMessengerChannelPayload(avito).external_account_id).toBe('')

    let legacyAvito = makeMessengerChannelDraft({
      name: 'legacy-avito',
      provider: 'avito_direct',
      auth_type: 'authorization_code',
      client_id: 'client-id',
      client_secret_configured: true,
    })
    expect(legacyAvito.auth_type).toBe('client_credentials')
    legacyAvito.auth_type = 'api_token'
    expect(buildMessengerChannelPayload(legacyAvito).auth_type).toBe(
      'client_credentials',
    )
  })

  it('defaults new Avito channels to a date range and preserves existing channels', () => {
    expect(
      makeMessengerChannelDraft({ provider: 'avito_direct' }).avito_import_mode,
    ).toBe('period')
    expect(
      makeMessengerChannelDraft({
        name: 'existing-avito',
        provider: 'avito_direct',
      }).avito_import_mode,
    ).toBe('all')
    let draft = makeMessengerChannelDraft()
    draft.provider = 'avito_direct'
    applyMessengerProviderDefaults(draft)
    expect(draft.avito_import_mode).toBe('period')
  })

  it('shows today as the default end date and sends the selected date', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-29T09:00:00Z'))
    try {
      let draft = makeMessengerChannelDraft({
        provider: 'avito_direct',
        client_id: 'client-id',
        client_secret_configured: true,
      })
      expect(draft.avito_import_to_date).toBe('2026-09-29')
      draft.avito_import_from_date = '2025-01-01'
      expect(validateMessengerChannelDraft(draft)).toBe('')
      expect(buildMessengerChannelPayload(draft)).toMatchObject({
        avito_import_mode: 'period',
        avito_import_from_date: '2025-01-01',
        avito_import_to_date: '2026-09-29',
      })
      draft.avito_import_to_date = '2025-02-01'
      expect(buildMessengerChannelPayload(draft).avito_import_to_date).toBe(
        '2025-02-01',
      )
      draft.avito_import_to_date = ''
      expect(validateMessengerChannelDraft(draft)).toBe(
        'Enter the Avito import end date.',
      )
      draft.avito_import_to_date = '2024-12-31'
      expect(validateMessengerChannelDraft(draft)).toBe(
        'The end date must be on or after the start date.',
      )
      draft.avito_import_to_date = '2026-09-30'
      expect(validateMessengerChannelDraft(draft)).toBe(
        'Avito import dates cannot be later than today.',
      )
      draft.avito_import_from_date = '2026-09-30'
      draft.avito_import_to_date = '2026-09-30'
      expect(validateMessengerChannelDraft(draft)).toBe(
        'Avito import dates cannot be later than today.',
      )
      draft.avito_import_mode = 'new_activity'
      expect(buildMessengerChannelPayload(draft)).toMatchObject({
        avito_import_mode: 'new_activity',
        avito_import_from_date: '',
        avito_import_to_date: '',
      })
    } finally {
      vi.useRealTimers()
    }
  })

  it('uses the CRM system time zone for the default end date', () => {
    let previousTimezone = window.timezone
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-29T12:00:00Z'))
    window.timezone = { system: 'Pacific/Kiritimati' }
    try {
      expect(
        makeMessengerChannelDraft({ provider: 'avito_direct' })
          .avito_import_to_date,
      ).toBe('2026-09-30')
    } finally {
      window.timezone = previousTimezone
      vi.useRealTimers()
    }
  })

  it('shows the effective legacy end date without changing an untouched import policy', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-29T09:00:00Z'))
    try {
      let legacy = makeMessengerChannelDraft({
        name: 'legacy-period',
        provider: 'avito_direct',
        avito_import_mode: 'period',
        avito_import_from_date: '2026-09-01',
        avito_import_to_date: '',
        avito_import_started_at: '2026-09-04 12:00:00',
      })
      expect(legacy.avito_import_to_date).toBe('2026-09-04')
      expect(buildMessengerChannelPayload(legacy).avito_import_to_date).toBe('')
      legacy.avito_import_to_date = '2026-09-10'
      expect(buildMessengerChannelPayload(legacy).avito_import_to_date).toBe(
        '2026-09-10',
      )
      let all = makeMessengerChannelDraft({
        name: 'existing-all',
        provider: 'avito_direct',
        avito_import_mode: 'all',
        avito_import_started_at: '2026-09-04 12:00:00',
      })
      expect(all.avito_import_to_date).toBe('2026-09-29')
    } finally {
      vi.useRealTimers()
    }
  })

  it('maps channel connection states for the list', () => {
    expect(messengerChannelState({ enabled: 0 })).toEqual({
      label: 'Channel Disabled',
      theme: 'gray',
    })
    expect(
      messengerChannelState({
        enabled: 1,
        provider: 'telegram_bot',
        state: 'connected',
      }),
    ).toEqual({ label: 'Channel Connected', theme: 'green' })
  })
})
