const API_PREFIX = 'crm_messenger.api.wazzup_partner'
const REQUEST_FIELDS = {
  start_connection: ['platform', 'custom_display_name', 'client_request_id'],
  get_onboarding_state: ['channel'],
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
  deleted: { label: 'Channel Deleted', theme: 'gray' },
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
    : STATUS_PRESENTATION.not_connected
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
  const status = Object.hasOwn(STATUS_PRESENTATION, onboarding.status)
    ? onboarding.status
    : Object.hasOwn(STATUS_PRESENTATION, channel.wazzup_status)
      ? channel.wazzup_status
      : 'not_connected'
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
