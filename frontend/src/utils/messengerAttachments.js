const ACTIVE_STATUSES = new Set(['available', 'external', 'uploaded'])
const BUSY_STATUSES = new Set([
  'pending',
  'downloading',
  'retrying',
  'uploading',
])

const STATUS_LABELS = {
  pending: 'Ожидает загрузки',
  downloading: 'Загружается',
  retrying: 'Повторная загрузка',
  available: 'Доступно',
  external: 'Открыть во внешнем сервисе',
  uploading: 'Отправляется',
  uploaded: 'Загружено',
  failed: 'Ошибка загрузки',
  unsupported: 'Не поддерживается',
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

export function isSingleImageAttachmentSet(attachments = []) {
  return attachments.length === 1 && attachments[0]?.type === 'image'
}

export function getSingleImageBubbleWidthClass(image = {}) {
  let orientation = getImagePresentationOrientation(image)
  if (orientation === 'portrait') return 'w-[18rem]'
  if (orientation === 'landscape') return 'w-[29.5rem]'
  return 'w-[24rem]'
}

export function getSingleImageMediaWidthClass(image = {}) {
  let orientation = getImagePresentationOrientation(image)
  if (orientation === 'portrait') return 'w-[16.5rem]'
  if (orientation === 'landscape') return 'w-[28rem]'
  return 'w-[22.5rem]'
}

function getImagePresentationOrientation(image = {}) {
  let width = Number(image.width || 0)
  let height = Number(image.height || 0)
  if (!width || !height) return 'square'

  let ratio = width / height
  if (ratio < 0.9) return 'portrait'
  if (ratio > 1.1) return 'landscape'
  return 'square'
}

export function getAttachmentState(attachment = {}) {
  let status = attachment.status || 'unsupported'
  return {
    status,
    label: STATUS_LABELS[status] || status,
    busy: BUSY_STATUSES.has(status),
    failed: status === 'failed',
    unsupported: status === 'unsupported',
    active: ACTIVE_STATUSES.has(status),
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
    Boolean(attachment.url) &&
    attachment.mime_type?.startsWith('video/')
  )
}
