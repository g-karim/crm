import { dayjsLocal } from 'frappe-ui'
import { isMaxForwardOnlyMessage } from '@/utils/messengerForwarding'

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

const RUSSIAN_MONTHS = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
]

export function getMessengerDayKey(messageDatetime) {
  if (!messageDatetime) return ''

  let date = getLocalDate(messageDatetime)
  return date?.isValid() ? date.format('YYYY-MM-DD') : ''
}

export function getMessengerDateLabel(messageDatetime, now = dayjsLocal()) {
  if (!messageDatetime) return ''

  let date = getLocalDate(messageDatetime)
  let currentDate = isDayjsValue(now) ? now : getLocalDate(now)
  if (!date?.isValid() || !currentDate?.isValid()) return ''

  let dayKey = date.format('YYYY-MM-DD')
  if (dayKey === currentDate.format('YYYY-MM-DD')) return 'Сегодня'
  if (dayKey === currentDate.subtract(1, 'day').format('YYYY-MM-DD')) {
    return 'Вчера'
  }

  let label = `${date.date()} ${RUSSIAN_MONTHS[date.month()]}`
  return date.year() === currentDate.year() ? label : `${label} ${date.year()}`
}

export function buildMessengerMessageItems(messages = [], now = dayjsLocal()) {
  let previousDayKey = ''
  let result = []

  messages.forEach((message) => {
    let dayKey = getMessengerDayKey(message?.message_datetime)
    let dateLabel =
      dayKey && dayKey !== previousDayKey
        ? getMessengerDateLabel(message.message_datetime, now)
        : ''
    previousDayKey = dayKey

    let previous = result.at(-1)
    let previousMessage = previous?.messages?.at(-1)
    if (
      previous &&
      previous.messages.length < 20 &&
      canGroupMaxForwards(previousMessage, message)
    ) {
      previous.messages.push(message)
      previous.message = message
      return
    }

    result.push({
      message,
      messages: [message],
      dayKey,
      dateLabel,
    })
  })

  return result
}

function canGroupMaxForwards(previous, current) {
  if (!isMaxForwardOnlyMessage(previous) || !isMaxForwardOnlyMessage(current)) {
    return false
  }
  if (
    previous.conversation !== current.conversation ||
    previous.direction !== current.direction ||
    forwardSender(previous) !== forwardSender(current) ||
    getMessengerDayKey(previous.message_datetime) !==
      getMessengerDayKey(current.message_datetime)
  ) {
    return false
  }
  let previousTime = getLocalDate(previous.message_datetime)
  let currentTime = getLocalDate(current.message_datetime)
  if (!previousTime?.isValid() || !currentTime?.isValid()) return false
  let difference = currentTime.diff(previousTime, 'millisecond')
  return difference >= 0 && difference <= 5000
}

function forwardSender(message) {
  return String(message?.sender_name || message?.client_name || '')
}

export function getMessengerChannelType(channel = {}) {
  if (channel?.provider === 'avito_direct') return 'avito'
  return normalizePlatform(
    channel?.platform || channel?.channel_type || channel?.chat_type || '',
  )
}

export function getMessengerPlatformLabel(channel = {}) {
  let displayLabel = String(channel?.label || '').trim()
  if (displayLabel) return displayLabel

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
  if (isMaxVideoProcessingMessage(message)) return 'MAX обрабатывает видео'
  if (
    message?.provider === 'telegram_bot' &&
    getMessengerDeliveryState(message) === 'sent'
  ) {
    return 'Отправлено в Telegram; статус прочтения недоступен'
  }
  return DELIVERY_LABELS[getMessengerDeliveryState(message)] || ''
}

export function isMaxVideoProcessingMessage(message = {}) {
  return Boolean(
    message?.provider === 'max_direct' &&
    getMessengerDeliveryState(message) === 'retrying' &&
    message?.provider_status === 'attachment.not.ready' &&
    (message?.message_type === 'video' ||
      message?.attachments?.some((attachment) => attachment?.type === 'video')),
  )
}

export function getMessengerConversationNotice(conversation = {}) {
  if (conversation?.provider !== 'max_direct') {
    return { type: '', message: '', blocksSend: false }
  }
  if (conversation?.provider_state === 'removed') {
    return {
      type: 'warning',
      message:
        'Клиент удалил диалог MAX. Отправка недоступна до повторного запуска бота.',
      blocksSend: true,
    }
  }
  if (conversation?.provider_state === 'stopped') {
    return {
      type: 'warning',
      message:
        'Клиент остановил бота MAX. Отправка недоступна до возобновления диалога.',
      blocksSend: true,
    }
  }
  if (conversation?.provider_history_cleared_at) {
    return {
      type: 'info',
      message: 'Клиент очистил историю диалога в MAX. История в CRM сохранена.',
      blocksSend: false,
    }
  }
  return { type: '', message: '', blocksSend: false }
}

export function getMessengerCapabilities(channel = {}) {
  let video = channel?.capabilities?.video || {}
  let voice = channel?.capabilities?.voice || {}
  let reactions = channel?.capabilities?.reactions || {}
  let location = channel?.capabilities?.location || {}
  let contact = channel?.capabilities?.contact || {}
  let typing = channel?.capabilities?.typing || {}
  return {
    can_start_conversation:
      channel?.capabilities?.can_start_conversation ?? true,
    requires_inbound: Boolean(channel?.capabilities?.requires_inbound),
    requires_phone: Boolean(channel?.capabilities?.requires_phone),
    supports_attachments: Boolean(channel?.capabilities?.supports_attachments),
    reactions: {
      receive: Boolean(reactions.receive),
      send: Boolean(reactions.send),
    },
    location: {
      receive: Boolean(location.receive),
      send: Boolean(location.send),
    },
    contact: {
      receive: Boolean(contact.receive),
      send: Boolean(contact.send),
    },
    typing: {
      receive: Boolean(
        typing.receive ?? channel?.capabilities?.supports_typing_events,
      ),
      send: Boolean(typing.send),
    },
    supported_attachment_types:
      channel?.capabilities?.supported_attachment_types || [],
    max_attachment_count: Math.max(
      1,
      Number(channel?.capabilities?.max_attachment_count || 10),
    ),
    voice: {
      send: Boolean(voice.send),
      max_duration_seconds: Number(voice.max_duration_seconds || 300),
      max_size_bytes: Number(voice.max_size_bytes || 10 * 1024 * 1024),
    },
    video: {
      receive: Boolean(video.receive),
      download: Boolean(video.download_to_private ?? video.download),
      inline_playback: Boolean(video.inline_playback),
      embed: Boolean(video.embed),
      native_send: Boolean(video.native_send),
      send_fallback: video.send_fallback || '',
    },
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

function isDayjsValue(value) {
  return Boolean(value?.isValid && value?.format)
}

function getLocalDate(value) {
  try {
    return dayjsLocal(value)
  } catch {
    return null
  }
}
