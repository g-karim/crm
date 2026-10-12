import {
  applyMessengerProviderDefaults,
  buildMessengerChannelPayload,
  makeMessengerChannelDraft,
  MESSENGER_PROVIDER_OPTIONS,
  messengerChannelState,
  validateMessengerChannelDraft,
  wazzupConnectionMessage,
  wazzupConnectionRows,
  wazzupOperationalCounts,
} from '@/utils/messengerSettings'

describe('messengerSettings', () => {
  it('allows administering an unchanged saved Wazzup legacy ID without sending its validation snapshot', () => {
    const draft = makeMessengerChannelDraft({
      name: 'legacy-wazzup',
      provider: 'wazzup',
      provider_channel_id: 'legacy-channel-id',
      api_token_configured: true,
      enabled: true,
    })
    draft.enabled = false
    draft.custom_display_name = 'Renamed legacy channel'
    expect(validateMessengerChannelDraft(draft)).toBe('')
    expect(buildMessengerChannelPayload(draft)).toMatchObject({
      channel: 'legacy-wazzup',
      provider_channel_id: 'legacy-channel-id',
      enabled: false,
      custom_display_name: 'Renamed legacy channel',
    })
    expect(buildMessengerChannelPayload(draft)).not.toHaveProperty(
      'original_wazzup_identity',
    )
  })

  it('requires a UUID for changed legacy IDs and does not reuse another saved channel identity', () => {
    const draft = makeMessengerChannelDraft({
      name: 'legacy-wazzup',
      provider: 'wazzup',
      provider_channel_id: 'legacy-channel-id',
      api_token_configured: true,
    })
    draft.provider_channel_id = 'another-invalid-id'
    expect(validateMessengerChannelDraft(draft)).toBe(
      'Enter a Wazzup channel UUID.',
    )
    draft.provider_channel_id = 'legacy-channel-id'
    draft.channel = 'another-channel'
    expect(validateMessengerChannelDraft(draft)).toBe(
      'Enter a Wazzup channel UUID.',
    )
    draft.channel = 'legacy-wazzup'
    draft.provider_channel_id = 'b5436cae-2434-4b55-a477-99386aeeecb4'
    expect(validateMessengerChannelDraft(draft)).toBe('')
    applyMessengerProviderDefaults(draft)
    expect(draft.original_wazzup_identity).toBeNull()
  })
  it.each(['unverified', 'received'])(
    'keeps a checked Wazzup configuration neutral when event delivery is %s',
    (status) => {
      expect(
        messengerChannelState({
          enabled: true,
          provider: 'wazzup',
          state: 'unchecked',
          integration: {
            wazzup_connection: {
              last_checked_at: '2026-10-05 12:00:00',
              delivery: { status },
            },
          },
        }),
      ).toEqual({ label: 'Configuration Checked', theme: 'gray' })
    },
  )
  it('uses a saved Wazzup key only for new Wazzup channels and prefers explicit credentials', () => {
    let draft = makeMessengerChannelDraft({ provider: 'wazzup' })
    draft.provider_channel_id = 'b5436cae-2434-4b55-a477-99386aeeecb4'
    draft.api_token_source_channel = 'saved-wazzup'
    expect(validateMessengerChannelDraft(draft)).toBe('')
    expect(buildMessengerChannelPayload(draft)).toMatchObject({
      api_token_source_channel: 'saved-wazzup',
    })
    draft.api_token = 'replacement-key'
    expect(buildMessengerChannelPayload(draft)).toMatchObject({
      api_token: 'replacement-key',
    })
    expect(buildMessengerChannelPayload(draft)).not.toHaveProperty(
      'api_token_source_channel',
    )
    draft.api_token = ''
    draft.channel = 'existing-wazzup'
    expect(buildMessengerChannelPayload(draft)).not.toHaveProperty(
      'api_token_source_channel',
    )
    expect(validateMessengerChannelDraft(draft)).toBe('Enter an API token.')
    draft.channel = ''
    draft.provider = 'telegram_bot'
    expect(validateMessengerChannelDraft(draft)).toBe('Enter an API token.')
    expect(buildMessengerChannelPayload(draft)).not.toHaveProperty(
      'api_token_source_channel',
    )
  })

  it.each([
    '79999999999',
    '@support',
    'channel-1',
    'b5436cae-2434-1b55-a477-99386aeeecb4',
  ])(
    'rejects a Wazzup plainId or non-v4 channel ID %s before saving',
    (provider_channel_id) => {
      let draft = makeMessengerChannelDraft({
        provider: 'wazzup',
        provider_channel_id,
        api_token_configured: true,
      })
      expect(validateMessengerChannelDraft(draft)).toBe(
        'Enter a Wazzup channel UUID.',
      )
    },
  )

  it('keeps connection checks independent from actual event receipt and sanitizes unknown diagnostics', () => {
    let rows = wazzupConnectionRows({
      api: { status: 'verified' },
      remote_channel: { status: 'verified' },
      subscription: { status: 'invalid' },
      local_config: { status: 'arbitrary-secret' },
      delivery: { status: 'unverified', last_received_at: null },
    })
    expect(rows.find((row) => row.key === 'api')).toMatchObject({
      label: 'Verified',
      theme: 'green',
    })
    expect(rows.find((row) => row.key === 'subscription')).toMatchObject({
      label: 'Needs Attention',
      theme: 'orange',
    })
    expect(rows.find((row) => row.key === 'local_config')).toMatchObject({
      label: 'Not checked',
      theme: 'gray',
    })
    expect(rows.find((row) => row.key === 'delivery')).toMatchObject({
      label: 'No event observed',
      theme: 'gray',
    })
    expect(
      wazzupConnectionRows({
        delivery: {
          status: 'received',
          last_received_at: '2026-10-05 12:00:00',
          event_type: 'status',
        },
      }).at(-1),
    ).toMatchObject({
      label: 'Event received',
      event_label: 'Message status',
      theme: 'green',
    })
    expect(
      wazzupConnectionRows({ delivery: { status: 'received' } }).at(-1).theme,
    ).toBe('gray')
    expect(wazzupConnectionMessage('The Wazzup API key is invalid.')).toBe(
      'The Wazzup API key is invalid.',
    )
    expect(wazzupConnectionMessage('Authorization: Bearer leaked-secret')).toBe(
      'The provider operation failed.',
    )
  })

  it('projects only valid operation counts without exposing errors or converting missing diagnostics to success', () => {
    expect(wazzupOperationalCounts(null)).toBeNull()
    expect(
      wazzupOperationalCounts({
        webhook_queue: {
          queued: 2,
          processing: 1,
          retrying: 3,
          failed: 4,
          error: 'private',
        },
        media: { pending: 1, downloading: 2, retrying: 1, failed: -1 },
      }),
    ).toEqual({
      events_pending: 6,
      events_failed: 4,
      media_pending: 4,
      media_failed: 0,
    })
  })
  it('names Wazzup separately from the direct messenger providers', () => {
    const gateway = MESSENGER_PROVIDER_OPTIONS.find(
      (option) => option.value === 'wazzup',
    )

    expect(gateway.label).toBe('Wazzup')
    expect(
      MESSENGER_PROVIDER_OPTIONS.filter((option) => option.value !== 'wazzup'),
    ).toEqual([
      { label: 'Telegram Bot', value: 'telegram_bot' },
      { label: 'VK', value: 'vk_direct' },
      { label: 'MAX', value: 'max_direct' },
      { label: 'Avito', value: 'avito_direct' },
    ])
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
      legacy.custom_display_name = 'Renamed channel'
      expect(buildMessengerChannelPayload(legacy).avito_import_to_date).toBe('')
      legacy.avito_import_from_date = '2026-08-01'
      expect(buildMessengerChannelPayload(legacy).avito_import_to_date).toBe(
        '2026-09-04',
      )
      expect(buildMessengerChannelPayload(legacy)).not.toHaveProperty(
        'original_avito_import_selection',
      )
      legacy.avito_import_from_date = '2026-09-01'
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

  it.each([undefined, '', 'new', 'unknown'])(
    'does not claim an enabled Wazzup channel is connected with state %s',
    (state) => {
      expect(
        messengerChannelState({ enabled: 1, provider: 'wazzup', state }),
      ).toEqual({ label: 'Connection Not Checked', theme: 'gray' })
    },
  )

  it.each([
    ['not_connected', 'Channel Not Connected', 'gray'],
    ['provisioning', 'Preparing connection', 'gray'],
    ['waiting_qr', 'Waiting for QR scan', 'orange'],
    ['waiting_2fa', 'Two-factor authentication required', 'orange'],
    ['active', 'Channel Connected', 'green'],
    ['unauthorized', 'Authorization expired', 'red'],
    ['error', 'Needs Attention', 'red'],
    ['unknown', 'Result unknown', 'orange'],
    ['reconnecting', 'Reconnecting', 'gray'],
    ['deleted', 'Channel Deleted', 'gray'],
  ])(
    'shows Partner lifecycle %s before the local enable flag',
    (status, label, theme) => {
      expect(
        messengerChannelState({
          provider: 'wazzup',
          wazzup_api_mode: 'partner_api_v2',
          wazzup_status: status,
          enabled: false,
        }),
      ).toEqual({ label, theme })
    },
  )

  it.each([
    ['connected', 'Channel Connected', 'green'],
    ['degraded', 'Needs Attention', 'orange'],
    ['error', 'Needs Attention', 'orange'],
    ['disconnected', 'Channel Not Connected', 'red'],
  ])('uses the validated Wazzup state %s', (state, label, theme) => {
    expect(
      messengerChannelState({ enabled: 1, provider: 'wazzup', state }),
    ).toEqual({ label, theme })
    expect(
      messengerChannelState({ enabled: 0, provider: 'wazzup', state }),
    ).toEqual({ label: 'Channel Disabled', theme: 'gray' })
  })
})
