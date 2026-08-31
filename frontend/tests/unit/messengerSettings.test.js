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
    expect(validateMessengerChannelDraft(avito)).toBe('')
    avito.auth_type = 'client_credentials'
    expect(validateMessengerChannelDraft(avito)).toBe(
      'Enter an Avito account ID.',
    )
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
