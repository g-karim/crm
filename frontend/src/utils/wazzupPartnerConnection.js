const API_PREFIX = 'crm_messenger.api.wazzup_partner'
const REQUEST_FIELDS = {
  start_connection: ['platform', 'custom_display_name', 'client_request_id'],
  get_onboarding_state: ['channel'],
  check_channel: ['channel'],
  save_channel_settings: ['channel', 'custom_display_name'],
  connect_channel: ['channel'],
  disconnect: ['channel'],
  submit_2fa: ['channel', 'password'],
  reconnect: ['channel'],
  delete_channel: ['channel'],
  simulator_scan: ['channel', 'require_2fa'],
}

const STATUS_PRESENTATION = {
  not_connected: { label: 'Channel Not Connected', theme: 'gray' },
  provisioning: { label: 'Preparing connection', theme: 'gray' },
  waiting_qr: { label: 'Waiting for QR scan', theme: 'orange' },
  waiting_2fa: { label: 'Two-factor authentication required', theme: 'orange' },
  active: { label: 'Channel Connected', theme: 'green' },
  unauthorized: { label: 'Authorization expired', theme: 'red' },
  error: { label: 'Needs Attention', theme: 'red' },
  unknown: { label: 'Result unknown', theme: 'orange' },
  reconnecting: { label: 'Reconnecting', theme: 'gray' },
  disabled: { label: 'Channel Disabled', theme: 'gray' },
  deleted: { label: 'Channel Deleted', theme: 'gray' },
}

const WEBHOOK_SUBSCRIPTION_PRESENTATION = {
  configured: { label: 'Configured', theme: 'green' },
  stale: { label: 'Needs Attention', theme: 'orange' },
  unknown: { label: 'Result unknown', theme: 'orange' },
  error: { label: 'Could not verify', theme: 'orange' },
  unverified: { label: 'Not checked', theme: 'gray' },
}

export function isWazzupPartnerChannel(channel) {
  return (
    channel?.provider === 'wazzup' &&
    channel?.wazzup_api_mode === 'partner_api_v2'
  )
}

export function wazzupPartnerStatus(status) {
  return Object.hasOwn(STATUS_PRESENTATION, status)
    ? STATUS_PRESENTATION[status]
    : status
      ? STATUS_PRESENTATION.unknown
      : STATUS_PRESENTATION.not_connected
}

export function normalizePartnerDiagnostics(integration) {
  const value = integration?.wazzup_partner
  if (!value || typeof value !== 'object') return null
  const status = (candidate, allowed, fallback) =>
    allowed.includes(candidate) ? candidate : fallback
  const timestamp = (candidate) =>
    typeof candidate === 'string' &&
    candidate.length <= 40 &&
    Number.isFinite(Date.parse(candidate))
      ? candidate
      : ''
  return {
    status: Object.hasOwn(STATUS_PRESENTATION, value.status)
      ? value.status
      : 'unknown',
    last_checked_at: timestamp(value.last_checked_at),
    reconciliation: {
      status: status(
        value.reconciliation?.status,
        ['verified', 'error', 'unverified', 'stale'],
        'unverified',
      ),
      ...(value.reconciliation?.reason === 'channel_not_returned'
        ? { reason: 'channel_not_returned' }
        : {}),
    },
    account: {
      status: status(
        value.account?.status,
        ['ready', 'pending', 'provisioning', 'unknown', 'failed'],
        'unknown',
      ),
      enabled: value.account?.enabled === true,
    },
    webhook_subscription: {
      status: status(
        value.webhook_subscription?.status,
        ['configured', 'stale', 'unknown', 'error', 'unverified'],
        'unverified',
      ),
      last_checked_at: timestamp(value.webhook_subscription?.last_checked_at),
    },
    delivery: {
      status: value.delivery?.status === 'received' ? 'received' : 'unverified',
      last_received_at: timestamp(value.delivery?.last_received_at),
      event_type: status(
        value.delivery?.event_type,
        [
          'message.add',
          'message.status_update',
          'channel.status_update',
          'channel.qr_update',
        ],
        '',
      ),
    },
  }
}

export function wazzupPartnerDiagnosticRows(diagnostics) {
  const value = diagnostics || {}
  const reconciliation = value.reconciliation?.status
  const subscription = value.webhook_subscription?.status
  const received =
    value.delivery?.status === 'received' && value.delivery.last_received_at
  return [
    {
      key: 'remote_channel',
      title: 'Provider channel status',
      ...(reconciliation === 'verified'
        ? wazzupPartnerStatus(value.status)
        : reconciliation === 'unverified' &&
            value.reconciliation?.reason === 'channel_not_returned'
          ? { label: 'No channel data', theme: 'gray' }
          : reconciliation === 'error'
            ? { label: 'Could not verify', theme: 'orange' }
            : { label: 'Not checked', theme: 'gray' }),
    },
    {
      key: 'account',
      title: 'Account connection',
      ...(value.account?.status === 'ready' && value.account.enabled
        ? { label: 'Verified', theme: 'green' }
        : value.account?.status === 'ready'
          ? { label: 'Channel Disabled', theme: 'gray' }
          : ['pending', 'provisioning'].includes(value.account?.status)
            ? { label: 'Preparing connection', theme: 'gray' }
            : !value.account
              ? { label: 'Not checked', theme: 'gray' }
              : { label: 'Could not verify', theme: 'orange' }),
    },
    {
      key: 'subscription',
      title: 'Account webhook subscription',
      ...(Object.hasOwn(WEBHOOK_SUBSCRIPTION_PRESENTATION, subscription)
        ? WEBHOOK_SUBSCRIPTION_PRESENTATION[subscription]
        : WEBHOOK_SUBSCRIPTION_PRESENTATION.unverified),
      checked_at: value.webhook_subscription?.last_checked_at || '',
    },
    {
      key: 'delivery',
      title: 'Actual incoming event',
      label: received ? 'Event received' : 'No event observed',
      theme: received ? 'green' : 'gray',
      received_at: received ? value.delivery.last_received_at : '',
      event_label: received
        ? {
            'message.add': 'Incoming message',
            'message.status_update': 'Message status',
            'channel.status_update': 'Channel update',
            'channel.qr_update': 'Channel update',
          }[value.delivery.event_type] || ''
        : '',
    },
  ]
}

export function wazzupPartnerConnectionWarning(diagnostics) {
  if (
    diagnostics?.reconciliation?.status === 'unverified' &&
    diagnostics.reconciliation.reason === 'channel_not_returned'
  )
    return 'The provider returned no channel information. Refresh the status and test the connection again.'
  if (diagnostics?.reconciliation?.status !== 'verified')
    return 'The channel could not be verified. Test the connection again.'
  if (!['active', 'waiting_qr', 'waiting_2fa'].includes(diagnostics.status))
    return 'Refresh the channel status or restore the connection to regain access.'
  if (diagnostics.account?.status !== 'ready' || !diagnostics.account.enabled)
    return 'The connected account could not be verified. Test the connection again.'
  if (diagnostics.webhook_subscription?.status !== 'configured')
    return 'Incoming events are not configured or could not be verified. Test the connection again.'
  return ''
}

export function safeWazzupQrImage(value) {
  return typeof value === 'string' &&
    value.length <= 1024 * 1024 &&
    /^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(value)
    ? value
    : ''
}

export function normalizePartnerConnection(value = {}) {
  const channel = value.channel || {}
  const onboarding = value.onboarding || {}
  const candidate = onboarding.status || channel.wazzup_status
  const status = Object.hasOwn(STATUS_PRESENTATION, candidate)
    ? candidate
    : candidate
      ? 'unknown'
      : 'not_connected'
  const diagnostics = normalizePartnerDiagnostics(
    value.integration || channel.integration,
  )
  const integration = diagnostics ? { wazzup_partner: diagnostics } : null
  const expiry = Date.parse(onboarding.qr_expires_at || '')
  return {
    ok: value.ok === true,
    reason: [
      'two_factor_rejected',
      'provider_rejected',
      'provider_unknown',
      'not_configured',
      'channel_not_ready',
      'pending',
    ].includes(value.reason)
      ? value.reason
      : '',
    channel: {
      name: typeof channel.name === 'string' ? channel.name.slice(0, 140) : '',
      provider: 'wazzup',
      platform: channel.platform === 'telegram' ? 'telegram' : 'whatsapp',
      custom_display_name:
        typeof channel.custom_display_name === 'string'
          ? channel.custom_display_name.slice(0, 140)
          : '',
      provider_display_name:
        typeof channel.provider_display_name === 'string'
          ? channel.provider_display_name.slice(0, 140)
          : '',
      enabled: Boolean(channel.enabled),
      wazzup_api_mode: 'partner_api_v2',
      wazzup_status: status,
      state: ['unchecked', 'connected', 'degraded', 'disconnected'].includes(
        channel.state,
      )
        ? channel.state
        : 'unchecked',
      ...(integration ? { integration } : {}),
    },
    onboarding: {
      status,
      qr_code:
        status === 'waiting_qr' && Number.isFinite(expiry)
          ? safeWazzupQrImage(onboarding.qr_code)
          : '',
      qr_expires_at: Number.isFinite(expiry)
        ? new Date(expiry).toISOString()
        : '',
      qr_expired: Boolean(onboarding.qr_expired),
      has_error: Boolean(onboarding.error),
      can_submit_2fa: Boolean(onboarding.can_submit_2fa),
      can_reconnect: Boolean(onboarding.can_reconnect),
    },
    simulator: value.simulator === true,
    integration,
  }
}

export function wazzupPartnerError(reason, action = '') {
  if (reason === 'two_factor_rejected') {
    return 'The two-factor authentication password was rejected. Try again.'
  }
  if (reason === 'provider_unknown') {
    return 'The connection result is unknown. Refresh its status before trying again.'
  }
  if (action === 'submit_2fa')
    return 'Could not submit the password. Refresh the connection status.'
  if (action === 'save_channel_settings') return 'Could not save the channel.'
  if (action === 'disconnect')
    return 'Could not disconnect the channel. Refresh its status.'
  if (action === 'delete_channel')
    return 'Could not delete the channel. Refresh its status.'
  return 'Could not update the connection. Refresh its status and try again.'
}

// Password arguments must never pass through the generic RPC error logger.
// Retain only approved response fields and use fixed error copy.
export async function callWazzupPartner(action, args = {}) {
  if (!Object.hasOwn(REQUEST_FIELDS, action)) {
    throw new Error(wazzupPartnerError('', action))
  }
  const payload = Object.fromEntries(
    REQUEST_FIELDS[action]
      .filter((field) => args[field] !== undefined)
      .map((field) => [field, args[field]]),
  )
  const headers = {
    Accept: 'application/json',
    'Content-Type': 'application/json; charset=utf-8',
    'X-Frappe-Site-Name': window.location.hostname,
  }
  if (window.csrf_token && window.csrf_token !== '{{ csrf_token }}') {
    headers['X-Frappe-CSRF-Token'] = window.csrf_token
  }
  try {
    const response = await fetch(`/api/method/${API_PREFIX}.${action}`, {
      method: 'POST',
      credentials: 'same-origin',
      redirect: 'error',
      headers,
      body: JSON.stringify(payload),
    })
    const data = await response.json()
    if (
      !response.ok ||
      data.exc ||
      !data.message ||
      typeof data.message !== 'object'
    ) {
      throw new Error()
    }
    return normalizePartnerConnection(data.message)
  } catch {
    throw new Error(wazzupPartnerError('', action))
  }
}
