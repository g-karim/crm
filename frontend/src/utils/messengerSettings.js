export const DIRECT_MESSENGER_PROVIDERS = [
  'telegram_bot',
  'vk_direct',
  'max_direct',
]

export const MESSENGER_PROVIDER_OPTIONS = [
  { label: 'Telegram Bot', value: 'telegram_bot' },
  { label: 'VK', value: 'vk_direct' },
  { label: 'MAX', value: 'max_direct' },
  { label: 'Avito', value: 'avito_direct' },
  { label: 'WhatsApp & Telegram', value: 'wazzup' },
]

const PROVIDER_DEFAULTS = {
  telegram_bot: { platform: 'telegram', auth_type: 'api_token' },
  vk_direct: { platform: 'vk', auth_type: 'api_token' },
  max_direct: { platform: 'max', auth_type: 'api_token' },
  avito_direct: { platform: 'avito', auth_type: 'authorization_code' },
  wazzup: { platform: 'whatsapp', auth_type: 'api_token' },
}

export function isDirectMessengerProvider(provider) {
  return DIRECT_MESSENGER_PROVIDERS.includes(provider)
}

export function messengerProviderLabel(provider) {
  return (
    MESSENGER_PROVIDER_OPTIONS.find((option) => option.value === provider)
      ?.label || provider
  )
}

export function makeMessengerChannelDraft(channel = null) {
  let provider = channel?.provider || 'telegram_bot'
  let defaults = PROVIDER_DEFAULTS[provider] || {}
  return {
    channel: channel?.name || '',
    provider,
    custom_display_name: channel?.custom_display_name || '',
    platform: channel?.platform || defaults.platform || '',
    auth_type: channel?.auth_type || defaults.auth_type || '',
    provider_channel_id: channel?.provider_channel_id || '',
    external_account_id: channel?.external_account_id || '',
    public_chat_url: channel?.public_chat_url || '',
    api_base_url: channel?.api_base_url || '',
    client_id: channel?.client_id || '',
    enabled: Boolean(channel?.enabled),
    api_token: '',
    client_secret: '',
    api_token_configured: Boolean(channel?.api_token_configured),
    client_secret_configured: Boolean(channel?.client_secret_configured),
  }
}

export function applyMessengerProviderDefaults(draft) {
  let defaults = PROVIDER_DEFAULTS[draft.provider] || {}
  draft.platform = defaults.platform || ''
  draft.auth_type = defaults.auth_type || ''
  draft.external_account_id = ''
  draft.provider_channel_id = ''
  draft.client_id = ''
  draft.api_token = ''
  draft.client_secret = ''
  draft.enabled = false
  return draft
}

export function buildMessengerChannelPayload(draft) {
  let defaults = PROVIDER_DEFAULTS[draft.provider] || {}
  let payload = {
    provider: draft.provider,
    custom_display_name: clean(draft.custom_display_name),
    platform: clean(draft.platform) || defaults.platform || '',
    auth_type: clean(draft.auth_type) || defaults.auth_type || '',
    provider_channel_id: clean(draft.provider_channel_id),
    external_account_id: clean(draft.external_account_id),
    public_chat_url: clean(draft.public_chat_url),
    api_base_url: clean(draft.api_base_url),
    client_id: clean(draft.client_id),
    enabled: isDirectMessengerProvider(draft.provider)
      ? Boolean(draft.enabled && draft.channel)
      : Boolean(draft.enabled),
  }
  if (draft.channel) payload.channel = draft.channel
  if (clean(draft.api_token)) payload.api_token = clean(draft.api_token)
  if (clean(draft.client_secret)) {
    payload.client_secret = clean(draft.client_secret)
  }
  return payload
}

export function validateMessengerChannelDraft(draft) {
  if (!draft.provider) return 'Select a provider.'
  if (
    ['telegram_bot', 'vk_direct', 'max_direct', 'wazzup'].includes(
      draft.provider,
    ) &&
    !draft.api_token_configured &&
    !clean(draft.api_token)
  ) {
    return 'Enter an API token.'
  }
  if (draft.provider === 'vk_direct' && !clean(draft.external_account_id)) {
    return 'Enter a VK community ID or short name.'
  }
  if (draft.provider === 'wazzup') {
    if (!['whatsapp', 'telegram'].includes(draft.platform)) {
      return 'Select a messaging platform.'
    }
    if (!clean(draft.provider_channel_id)) {
      return 'Enter a channel ID.'
    }
  }
  if (draft.provider === 'avito_direct') {
    if (
      draft.auth_type !== 'authorization_code' &&
      !clean(draft.external_account_id)
    ) {
      return 'Enter an Avito account ID.'
    }
    if (draft.auth_type === 'client_credentials') {
      if (!clean(draft.client_id)) return 'Enter the Avito Client ID.'
      if (!draft.client_secret_configured && !clean(draft.client_secret)) {
        return 'Enter the Avito Client Secret.'
      }
    }
    if (
      draft.auth_type === 'api_token' &&
      !draft.api_token_configured &&
      !clean(draft.api_token)
    ) {
      return 'Enter an Avito API token.'
    }
  }
  return ''
}

export function messengerChannelState(channel = {}) {
  if (!channel.enabled) {
    return { label: 'Channel Disabled', theme: 'gray' }
  }
  if (isDirectMessengerProvider(channel.provider)) {
    if (channel.state === 'connected') {
      return { label: 'Channel Connected', theme: 'green' }
    }
    if (channel.state === 'degraded') {
      return { label: 'Needs Attention', theme: 'orange' }
    }
    return { label: 'Channel Not Connected', theme: 'red' }
  }
  return { label: 'Channel Enabled', theme: 'green' }
}

function clean(value) {
  return String(value || '').trim()
}
