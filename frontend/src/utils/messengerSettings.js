import {
  isWazzupPartnerChannel,
  wazzupPartnerStatus,
} from '@/utils/wazzupPartnerConnection'

export const DIRECT_MESSENGER_PROVIDERS = [
  'telegram_bot',
  'vk_direct',
  'max_direct',
  'avito_direct',
]

export const MESSENGER_PROVIDER_OPTIONS = [
  { label: 'Telegram Bot', value: 'telegram_bot' },
  { label: 'VK', value: 'vk_direct' },
  { label: 'MAX', value: 'max_direct' },
  { label: 'Avito', value: 'avito_direct' },
  { label: 'Wazzup', value: 'wazzup' },
]

export function messengerChannelCreationOptions(legacyEnabled = false) {
  return [
    { label: 'WhatsApp', value: 'partner_whatsapp', platform: 'whatsapp' },
    {
      label: 'Telegram personal chats',
      value: 'partner_telegram',
      platform: 'telegram',
    },
    ...MESSENGER_PROVIDER_OPTIONS.filter(
      (option) => option.value !== 'wazzup' || legacyEnabled,
    ).map((option) => ({
      label:
        option.value === 'wazzup'
          ? 'Wazzup User API v3 (legacy)'
          : option.label,
      provider: option.value,
      value: option.value,
    })),
  ]
}

const PROVIDER_DEFAULTS = {
  telegram_bot: { platform: 'telegram', auth_type: 'api_token' },
  vk_direct: { platform: 'vk', auth_type: 'api_token' },
  max_direct: { platform: 'max', auth_type: 'api_token' },
  avito_direct: { platform: 'avito', auth_type: 'client_credentials' },
  wazzup: { platform: 'whatsapp', auth_type: 'api_token' },
}

export function isDirectMessengerProvider(provider) {
  return DIRECT_MESSENGER_PROVIDERS.includes(provider)
}

export function messengerProviderLabel(provider) {
  if (provider === 'partner_whatsapp') return 'WhatsApp'
  if (provider === 'partner_telegram') return 'Telegram personal chats'
  return (
    MESSENGER_PROVIDER_OPTIONS.find((option) => option.value === provider)
      ?.label || provider
  )
}

export function makeMessengerChannelDraft(channel = null) {
  let provider = channel?.provider || 'telegram_bot'
  let defaults = PROVIDER_DEFAULTS[provider] || {}
  let implicitAvitoEnd = Boolean(
    channel?.name &&
    channel?.avito_import_mode === 'period' &&
    !channel?.avito_import_to_date,
  )
  let avitoEnd =
    channel?.avito_import_to_date ||
    (provider === 'avito_direct'
      ? implicitAvitoEnd && channel?.avito_import_started_at
        ? String(channel.avito_import_started_at).slice(0, 10)
        : todayInCrmTimezone()
      : '')
  return {
    channel: channel?.name || '',
    provider,
    custom_display_name: channel?.custom_display_name || '',
    platform: channel?.platform || defaults.platform || '',
    auth_type:
      provider === 'avito_direct'
        ? 'client_credentials'
        : channel?.auth_type || defaults.auth_type || '',
    provider_channel_id: channel?.provider_channel_id || '',
    original_wazzup_identity:
      channel?.name && provider === 'wazzup'
        ? {
            channel: channel.name,
            provider_channel_id: channel.provider_channel_id || '',
          }
        : null,
    external_account_id: channel?.external_account_id || '',
    public_chat_url: channel?.public_chat_url || '',
    api_base_url: channel?.api_base_url || '',
    client_id: channel?.client_id || '',
    avito_import_mode: channel?.name
      ? channel.avito_import_mode || 'all'
      : provider === 'avito_direct'
        ? 'period'
        : 'all',
    avito_import_from_date: channel?.avito_import_from_date || '',
    avito_import_to_date: avitoEnd,
    avito_import_to_date_implicit: implicitAvitoEnd ? avitoEnd : '',
    original_avito_import_selection: implicitAvitoEnd
      ? {
          channel: channel.name,
          from_date: channel.avito_import_from_date || '',
        }
      : null,
    enabled: Boolean(channel?.enabled),
    api_token: '',
    api_token_source_channel: '',
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
  draft.original_wazzup_identity = null
  draft.client_id = ''
  draft.avito_import_mode = draft.provider === 'avito_direct' ? 'period' : 'all'
  draft.avito_import_from_date = ''
  draft.avito_import_to_date =
    draft.provider === 'avito_direct' ? todayInCrmTimezone() : ''
  draft.avito_import_to_date_implicit = ''
  draft.original_avito_import_selection = null
  draft.api_token = ''
  draft.api_token_source_channel = ''
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
    auth_type:
      draft.provider === 'avito_direct'
        ? 'client_credentials'
        : clean(draft.auth_type) || defaults.auth_type || '',
    provider_channel_id: clean(draft.provider_channel_id),
    external_account_id: clean(draft.external_account_id),
    public_chat_url: clean(draft.public_chat_url),
    api_base_url: clean(draft.api_base_url),
    client_id: clean(draft.client_id),
    enabled: isDirectMessengerProvider(draft.provider)
      ? Boolean(draft.enabled && draft.channel)
      : Boolean(draft.enabled),
  }
  if (draft.provider === 'avito_direct') {
    payload.avito_import_mode = draft.avito_import_mode
    payload.avito_import_from_date =
      draft.avito_import_mode === 'period'
        ? clean(draft.avito_import_from_date)
        : ''
    let end = clean(draft.avito_import_to_date)
    const original = draft.original_avito_import_selection
    const unchangedImplicitEnd = Boolean(
      original?.channel === draft.channel &&
      original?.from_date === payload.avito_import_from_date &&
      end === draft.avito_import_to_date_implicit,
    )
    payload.avito_import_to_date =
      draft.avito_import_mode === 'period' && !unchangedImplicitEnd ? end : ''
  }
  if (draft.channel) payload.channel = draft.channel
  if (clean(draft.api_token)) payload.api_token = clean(draft.api_token)
  else if (
    draft.provider === 'wazzup' &&
    !draft.channel &&
    clean(draft.api_token_source_channel)
  ) {
    payload.api_token_source_channel = clean(draft.api_token_source_channel)
  }
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
    !clean(draft.api_token) &&
    !(
      draft.provider === 'wazzup' &&
      !draft.channel &&
      clean(draft.api_token_source_channel)
    )
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
    const original = draft.original_wazzup_identity
    const unchangedSavedId = Boolean(
      draft.channel &&
      original?.channel === draft.channel &&
      clean(draft.provider_channel_id) === original.provider_channel_id,
    )
    if (
      !unchangedSavedId &&
      !/^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/i.test(
        clean(draft.provider_channel_id),
      )
    ) {
      return 'Enter a Wazzup channel UUID.'
    }
  }
  if (draft.provider === 'avito_direct') {
    if (!clean(draft.client_id)) return 'Enter the Avito Client ID.'
    if (!draft.client_secret_configured && !clean(draft.client_secret)) {
      return 'Enter the Avito Client Secret.'
    }
    if (!['all', 'period', 'new_activity'].includes(draft.avito_import_mode)) {
      return 'Select how to import Avito chats.'
    }
    if (draft.avito_import_mode === 'period') {
      let start = clean(draft.avito_import_from_date)
      let end = clean(draft.avito_import_to_date)
      if (!isValidDate(start)) return 'Enter the Avito import start date.'
      if (!isValidDate(end)) {
        return 'Enter the Avito import end date.'
      }
      if (end < start) return 'The end date must be on or after the start date.'
      let today = todayInCrmTimezone()
      if (start > today || end > today)
        return 'Avito import dates cannot be later than today.'
    }
  }
  return ''
}

export function messengerChannelState(channel = {}) {
  if (isWazzupPartnerChannel(channel)) {
    return channel.enabled === false || channel.enabled === 0
      ? { label: 'Channel Disabled', theme: 'gray' }
      : wazzupPartnerStatus(channel.wazzup_status)
  }
  if (!channel.enabled) {
    return { label: 'Channel Disabled', theme: 'gray' }
  }
  if (channel.provider === 'wazzup') {
    if (channel.state === 'connected') {
      return { label: 'Channel Connected', theme: 'green' }
    }
    if (channel.state === 'degraded' || channel.state === 'error') {
      return { label: 'Needs Attention', theme: 'orange' }
    }
    if (channel.state === 'disconnected') {
      return { label: 'Channel Not Connected', theme: 'red' }
    }
    if (
      channel.state === 'unchecked' &&
      channel.integration?.wazzup_connection?.last_checked_at
    ) {
      return { label: 'Configuration Checked', theme: 'gray' }
    }
    return { label: 'Connection Not Checked', theme: 'gray' }
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

export const WAZZUP_CONNECTION_MESSAGES = [
  'The API token is not configured.',
  'The Wazzup API key is invalid.',
  'The Wazzup API request is not permitted.',
  'The Wazzup API is temporarily unavailable. Try checking again.',
  'The Wazzup API rate limit was reached. Try checking again.',
  'The Wazzup API returned an unexpected response.',
  'The Wazzup API endpoint is not supported.',
  'Enter the Wazzup channel UUID, not its phone number or username.',
  'Enter a Wazzup channel UUID.',
  'Select a messaging platform.',
  'This channel supports only WhatsApp and Telegram.',
  'The selected channel is not available for this Wazzup API key.',
  'The selected Wazzup channel uses a different messenger.',
  'The selected Wazzup channel is not active.',
  'The Wazzup channel state could not be verified.',
  'The messenger channel is unavailable.',
  'The Wazzup webhook address or message subscription does not match this CRM.',
  'Configure a public HTTPS site URL and webhook secret before receiving Wazzup events.',
  'Channel settings changed during verification. Check the channel again.',
  'Configuration verified. Webhook delivery has not been verified.',
  'Select a Wazzup channel.',
  'Select a Wazzup channel for the API key.',
  'Wazzup channels support API keys only.',
  'The messenger identity of a Wazzup channel with conversations cannot be changed. Create a separate channel.',
]

export function wazzupConnectionMessage(message) {
  return WAZZUP_CONNECTION_MESSAGES.includes(message)
    ? message
    : 'The provider operation failed.'
}

// The generic frappe-ui RPC helper logs request arguments on some exception
// responses. Wazzup setup carries draft credentials, so keep this boundary silent.
export async function callWazzupSettings(method, args = {}) {
  const allowed = [
    'crm_messenger.api.wazzup_connection.list_channels',
    'crm_messenger.api.wazzup_connection.check_channel',
    'crm_messenger.api.settings.save_channel',
    'crm_messenger.api.settings.save_settings',
  ]
  let message = 'The provider operation failed.'
  try {
    if (!allowed.includes(method)) throw new Error(message)
    if (
      method === 'crm_messenger.api.settings.save_channel' &&
      args.provider !== 'wazzup'
    )
      throw new Error(message)
    const headers = {
      Accept: 'application/json',
      'Content-Type': 'application/json; charset=utf-8',
      'X-Frappe-Site-Name': window.location.hostname,
    }
    if (window.csrf_token && window.csrf_token !== '{{ csrf_token }}') {
      headers['X-Frappe-CSRF-Token'] = window.csrf_token
    }
    const response = await fetch(`/api/method/${method}`, {
      method: 'POST',
      credentials: 'same-origin',
      redirect: 'error',
      headers,
      body: JSON.stringify(args),
    })
    const data = await response.json()
    if (
      response.ok &&
      !data.exc &&
      data.message &&
      typeof data.message === 'object'
    )
      return data.message
    let candidates = [data.message, data._error_message]
    if (typeof data._server_messages === 'string') {
      try {
        let serverMessages = JSON.parse(data._server_messages)
        if (Array.isArray(serverMessages))
          candidates.push(
            ...serverMessages.map((value) => {
              try {
                return JSON.parse(value).message
              } catch {
                return value
              }
            }),
          )
      } catch {
        /* Ignore unrecognized provider/server payloads. */
      }
    }
    message =
      candidates.find((value) => WAZZUP_CONNECTION_MESSAGES.includes(value)) ||
      message
  } catch {
    /* Never propagate or log request arguments or server exceptions. */
  }
  const error = new Error(message)
  error.messages = [message]
  throw error
}

export function wazzupConnectionRows(connection = {}) {
  const statuses = {
    verified: { label: 'Verified', theme: 'green' },
    invalid: { label: 'Needs Attention', theme: 'orange' },
    error: { label: 'Could not verify', theme: 'orange' },
  }
  let rows = [
    { key: 'api', label: 'API access' },
    { key: 'remote_channel', label: 'Selected Wazzup channel' },
    { key: 'subscription', label: 'Webhook subscription' },
    { key: 'local_config', label: 'CRM webhook configuration' },
  ].map((row) => ({
    ...row,
    ...(statuses[connection[row.key]?.status] || {
      label: 'Not checked',
      theme: 'gray',
    }),
    title: row.label,
  }))
  const delivery = connection.delivery || {}
  let received =
    ['received', 'observed'].includes(delivery.status) &&
    Boolean(delivery.last_received_at)
  rows.push({
    key: 'delivery',
    title: 'Actual incoming event',
    label: received ? 'Event received' : 'No event observed',
    theme: received ? 'green' : 'gray',
    received_at: received ? delivery.last_received_at : null,
    event_label: received
      ? {
          message: 'Incoming message',
          status: 'Message status',
          channel_update: 'Channel update',
        }[delivery.event_type] || ''
      : '',
  })
  return rows
}

export function wazzupOperationalCounts(channel) {
  if (!channel) return null
  const count = (value) =>
    Number.isSafeInteger(value) && value >= 0 ? value : 0
  const queue = channel.webhook_queue || {}
  const media = channel.media || {}
  return {
    events_pending: ['queued', 'processing', 'retrying'].reduce(
      (sum, key) => sum + count(queue[key]),
      0,
    ),
    events_failed: count(queue.failed),
    media_pending: ['pending', 'downloading', 'retrying'].reduce(
      (sum, key) => sum + count(media[key]),
      0,
    ),
    media_failed: count(media.failed),
  }
}

function clean(value) {
  return String(value || '').trim()
}

function isValidDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  let date = new Date(`${value}T00:00:00Z`)
  return (
    !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value
  )
}

function todayInCrmTimezone() {
  let timezone = globalThis.window?.timezone?.system
  let parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone || undefined,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  let date = Object.fromEntries(parts.map(({ type, value }) => [type, value]))
  return `${date.year}-${date.month}-${date.day}`
}
