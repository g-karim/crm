const PLATFORM_LABELS = {
  avito: 'Avito',
  whatsapp: 'WhatsApp',
  telegram: 'Telegram',
  vk: 'VK',
  max: 'MAX',
}

const DELIVERY_LABELS = {
  queued: 'В очереди',
  sending: 'Отправляется',
  retrying: 'Повторная попытка',
  unknown: 'Результат неизвестен',
  sent: 'Отправлено',
  delivered: 'Доставлено',
  read: 'Прочитано',
  failed: 'Ошибка',
}

const DELIVERY_STATES = Object.keys(DELIVERY_LABELS)

export function getMessengerChannelType(channel = {}) {
  if (channel?.provider === 'avito_direct') return 'avito'
  return normalizePlatform(
    channel?.platform || channel?.channel_type || channel?.chat_type || '',
  )
}

export function getMessengerPlatformLabel(channel = {}) {
  let type = getMessengerChannelType(channel)

  return (
    PLATFORM_LABELS[type] ||
    humanizePlatform(type) ||
    channel?.name ||
    'Messenger'
  )
}

export function buildMessengerChannelOptions(channels = []) {
  let baseLabels = channels.map((channel) => getMessengerPlatformLabel(channel))
  let totals = baseLabels.reduce((acc, label) => {
    acc[label] = (acc[label] || 0) + 1
    return acc
  }, {})
  let seen = {}

  return channels.map((channel, index) => {
    let baseLabel = baseLabels[index]
    seen[baseLabel] = (seen[baseLabel] || 0) + 1

    return {
      label:
        totals[baseLabel] > 1 && seen[baseLabel] > 1
          ? `${baseLabel} ${seen[baseLabel]}`
          : baseLabel,
      value: channel.name,
    }
  })
}

export function getMessengerDeliveryState(message = {}) {
  if (message?.direction !== 'outbound') return ''

  let status = normalizePlatform(
    message?.status || message?.delivery_status || '',
  )
  return DELIVERY_STATES.includes(status) ? status : ''
}

export function shouldShowMessengerText(message = {}) {
  if (message?.status === 'deleted') return true
  return Boolean(String(message?.text || '').trim())
}

export function getMessengerDeliveryLabel(message = {}) {
  return DELIVERY_LABELS[getMessengerDeliveryState(message)] || ''
}

export function getMessengerCapabilities(channel = {}) {
  return {
    can_start_conversation:
      channel?.capabilities?.can_start_conversation ?? true,
    requires_inbound: Boolean(channel?.capabilities?.requires_inbound),
    requires_phone: Boolean(channel?.capabilities?.requires_phone),
    supports_attachments: Boolean(
      channel?.capabilities?.supports_attachments,
    ),
    supported_attachment_types:
      channel?.capabilities?.supported_attachment_types || [],
  }
}

function normalizePlatform(value) {
  return `${value || ''}`.trim().toLowerCase()
}

function humanizePlatform(value) {
  return `${value || ''}`
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}
