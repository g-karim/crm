const PLATFORM_LABELS = {
  avito: 'Avito',
  whatsapp: 'WhatsApp',
  telegram: 'Telegram',
}

const DELIVERY_LABELS = {
  queued: 'В очереди',
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

  return PLATFORM_LABELS[type] || humanizePlatform(type) || channel?.name || 'Messenger'
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

  let status = normalizePlatform(message?.delivery_status || message?.status || '')
  return DELIVERY_STATES.includes(status) ? status : ''
}

export function getMessengerDeliveryLabel(message = {}) {
  return DELIVERY_LABELS[getMessengerDeliveryState(message)] || ''
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
