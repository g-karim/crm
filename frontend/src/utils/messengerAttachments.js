const ACTIVE_STATUSES = new Set(['available', 'external', 'uploaded'])
const BUSY_STATUSES = new Set([
  'pending',
  'processing',
  'downloading',
  'retrying',
  'uploading',
])

const STATUS_LABELS = {
  pending: 'Ожидает загрузки',
  processing: 'Обрабатывается',
  downloading: 'Загружается',
  retrying: 'Повторная загрузка',
  available: 'Доступно',
  external: 'Открыть во внешнем сервисе',
  uploading: 'Отправляется',
  uploaded: 'Загружено',
  failed: 'Ошибка загрузки',
  unsupported: 'Не поддерживается',
}

const REPLY_ATTACHMENT_TYPE_ALIASES = {
  photo: 'image',
  doc: 'file',
  document: 'file',
  audio_message: 'audio',
  geo: 'location',
}

const REPLY_ATTACHMENT_LABELS = {
  image: ['Изображение', 'Изображения'],
  video: ['Видео', 'Видео'],
  audio: ['Аудио', 'Аудио'],
  file: ['Документ', 'Документы'],
  link: ['Ссылка', 'Ссылки'],
  sticker: ['Стикер', 'Стикеры'],
  location: ['Геолокация', 'Геолокации'],
  contact: ['Контакт', 'Контакты'],
  unsupported: ['Вложение', 'Вложения'],
}

export function getMessengerReplyAttachmentLabel(snapshot = {}) {
  let attachmentTypes = Array.isArray(snapshot.attachment_types)
    ? snapshot.attachment_types.filter(Boolean)
    : []
  if (!attachmentTypes.length && snapshot.message_type !== 'text') {
    attachmentTypes = snapshot.message_type ? [snapshot.message_type] : []
  }
  if (!attachmentTypes.length) return ''

  let normalizedTypes = attachmentTypes.map((type) => {
    type = String(type).trim().toLowerCase()
    type = REPLY_ATTACHMENT_TYPE_ALIASES[type] || type
    return REPLY_ATTACHMENT_LABELS[type] ? type : 'unsupported'
  })
  if (new Set(normalizedTypes).size > 1) return 'Вложения'

  let labels = REPLY_ATTACHMENT_LABELS[normalizedTypes[0]]
  return labels[attachmentTypes.length > 1 ? 1 : 0]
}

export function groupMessengerAttachments(attachments = []) {
  return attachments.reduce(
    (groups, attachment) => {
      let type = attachment?.type || 'unsupported'
      if (type === 'image') groups.images.push(attachment)
      else if (type === 'sticker') groups.stickers.push(attachment)
      else groups.other.push(attachment)
      return groups
    },
    { images: [], stickers: [], other: [] },
  )
}

export function buildMessengerAttachmentSegments(attachments = []) {
  let segments = []
  attachments.forEach((attachment, index) => {
    if (attachment?.type === 'image') {
      let previous = segments.at(-1)
      if (previous?.type === 'images') previous.items.push(attachment)
      else
        segments.push({
          type: 'images',
          key: `images-${attachment.id || index}`,
          items: [attachment],
        })
      return
    }
    segments.push({
      type: attachment?.type || 'unsupported',
      key: `${attachment?.id || attachment?.type || 'attachment'}-${index}`,
      attachment,
    })
  })
  return segments
}

export function isSingleImageAttachmentSet(attachments = []) {
  return attachments.length === 1 && attachments[0]?.type === 'image'
}

export function getSingleImageBubbleWidthClass(image = {}) {
  return 'w-fit max-w-full'
}

export function getSingleImageMediaWidthClass(image = {}) {
  return 'max-w-full'
}

export function getCompactMediaDimensions(
  media = {},
  maxWidth = 320,
  maxHeight = 360,
) {
  let width = Number(media.width || 0)
  let height = Number(media.height || 0)
  let ratio = width > 0 && height > 0 ? width / height : 16 / 9
  if (!Number.isFinite(ratio) || ratio <= 0) ratio = 16 / 9
  ratio = Math.min(Math.max(ratio, 0.4), 4)
  let displayWidth = Math.min(maxWidth, maxHeight * ratio)
  return {
    ratio,
    width: Math.round(displayWidth * 100) / 100,
    height: Math.round((displayWidth / ratio) * 100) / 100,
  }
}

export function getAttachmentState(attachment = {}) {
  let status = attachment.status || 'unsupported'
  let playableFailedVoice =
    status === 'failed' && attachment.is_voice && Boolean(attachment.url)
  return {
    status,
    label: STATUS_LABELS[status] || status,
    busy: BUSY_STATUSES.has(status),
    failed: status === 'failed',
    unsupported: status === 'unsupported',
    active: ACTIVE_STATUSES.has(status) || playableFailedVoice,
  }
}

export function getAttachmentAction(attachment = {}) {
  if (!getAttachmentState(attachment).active) return ''
  return attachment.open_url || attachment.url || ''
}

export function getImageGridCellClass(count, index) {
  if (count === 2) return 'aspect-square'
  if (count === 3 && index === 0) return 'row-span-2 min-h-56'
  return 'aspect-square'
}

export function visibleImageAttachments(attachments = []) {
  return attachments.slice(0, 4)
}

export function formatAttachmentSize(bytes) {
  let value = Number(bytes || 0)
  if (!value) return ''
  if (value < 1024) return `${value} Б`
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} КБ`
  return `${(value / 1024 / 1024).toFixed(1)} МБ`
}

export function formatAttachmentDuration(milliseconds) {
  let seconds = Math.max(Math.round(Number(milliseconds || 0) / 1000), 0)
  if (!seconds) return ''
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function canRenderInlineVideo(attachment = {}) {
  return (
    attachment.type === 'video' &&
    getAttachmentState(attachment).active &&
    (!attachment.video_source || attachment.video_source === 'local_file') &&
    Boolean(attachment.playback_url || attachment.url) &&
    attachment.mime_type?.startsWith('video/')
  )
}

export function getVideoPlaybackUrl(attachment = {}) {
  return canRenderInlineVideo(attachment)
    ? attachment.playback_url || attachment.url || ''
    : ''
}
