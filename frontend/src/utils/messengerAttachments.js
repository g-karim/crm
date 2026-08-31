const ACTIVE_STATUSES = new Set(['available', 'external', 'uploaded'])
const BUSY_STATUSES = new Set([
  'pending',
  'processing',
  'downloading',
  'retrying',
  'uploading',
])

const STATUS_LABELS = {
  pending: 'Pending download',
  processing: 'Processing',
  downloading: 'Downloading',
  retrying: 'Retrying download',
  available: 'Available',
  external: 'Open in external service',
  uploading: 'Uploading',
  uploaded: 'Uploaded',
  failed: 'Upload failed',
  unsupported: 'Unsupported',
}

const REPLY_ATTACHMENT_TYPE_ALIASES = {
  photo: 'image',
  doc: 'file',
  document: 'file',
  audio_message: 'voice',
  geo: 'location',
}

const REPLY_ATTACHMENT_LABELS = {
  image: ['Image', 'Images'],
  video: ['Video', 'Videos'],
  audio: ['Audio', 'Audio files'],
  voice: ['Voice message', 'Voice messages'],
  file: ['Document', 'Documents'],
  link: ['Link', 'Links'],
  sticker: ['Sticker', 'Stickers'],
  location: ['Location', 'Locations'],
  contact: ['Contact', 'Contacts'],
  unsupported: ['Attachment', 'Attachments'],
}

const ATTACHMENT_TITLES = {
  image: 'Image',
  video: 'Video',
  audio: 'Audio',
  voice: 'Voice message',
  file: 'File',
  link: 'Link',
  sticker: 'Sticker',
  location: 'Location',
  contact: 'Contact',
  unsupported: 'Unsupported attachment',
}

const TECHNICAL_FILENAMES = new Set([
  'attachment',
  'audio',
  'audio.mp3',
  'audio.ogg',
  'animation.mp4',
  'contact',
  'document',
  'live-photo.mp4',
  'location',
  'photo.jpg',
  'sticker',
  'sticker.json',
  'sticker.tgs',
  'sticker.webm',
  'sticker.webp',
  'unsupported',
  'video.mp4',
  'video-note.mp4',
  'voice.ogg',
  'voice-recording.m4a',
  'voice-recording.ogg',
])

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
  if (new Set(normalizedTypes).size > 1) return 'Attachments'

  let labels = REPLY_ATTACHMENT_LABELS[normalizedTypes[0]]
  return labels[attachmentTypes.length > 1 ? 1 : 0]
}

export function getMessengerAttachmentTitle(attachment = {}) {
  if (attachment.display_title) return String(attachment.display_title)
  let type = attachment.is_voice ? 'voice' : attachment.type || 'unsupported'
  if (
    type === 'sticker' &&
    ['failed', 'unsupported'].includes(attachment.status)
  ) {
    return 'Sticker unavailable'
  }
  if (
    [
      'voice',
      'image',
      'sticker',
      'link',
      'location',
      'contact',
      'unsupported',
    ].includes(type)
  ) {
    return ATTACHMENT_TITLES[type]
  }
  if (attachment.title && !isTechnicalAttachmentName(attachment.title)) {
    return String(attachment.title)
  }
  if (
    attachment.file_name &&
    !isTechnicalAttachmentName(attachment.file_name)
  ) {
    return String(attachment.file_name)
  }
  return ATTACHMENT_TITLES[type] || ATTACHMENT_TITLES.unsupported
}

export function getMessengerMessagePreview(message = {}) {
  if (message.display_text) return String(message.display_text)
  if (String(message.text || '').trim()) return String(message.text).trim()
  return ATTACHMENT_TITLES[message.message_type] || 'Attachment'
}

export function isTechnicalAttachmentName(value) {
  let name = String(value || '')
    .split('/')
    .at(-1)
    .trim()
    .toLowerCase()
  return (
    TECHNICAL_FILENAMES.has(name) ||
    /^vk-(audio|photo|sticker|video)(-|\.|$)/i.test(name) ||
    /^max-(audio|file|image|sticker|video)(-|\.|$)/i.test(name)
  )
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
    if (
      attachment?.is_animated &&
      ['image', 'video'].includes(attachment?.type)
    ) {
      segments.push({
        type: 'animation',
        key: `${attachment?.id || 'animation'}-${index}`,
        attachment,
      })
      return
    }
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

export function isSingleStickerAttachmentSet(attachments = []) {
  return attachments.length === 1 && attachments[0]?.type === 'sticker'
}

export function isSingleLocationAttachmentSet(attachments = []) {
  return attachments.length === 1 && attachments[0]?.type === 'location'
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
  return getMediaFrameDimensions(media, maxWidth, maxHeight)
}

export function getCompactPreviewDimensions(
  media = {},
  maxWidth = 320,
  maxHeight = 280,
) {
  return getMediaFrameDimensions(media, maxWidth, maxHeight)
}

function getMediaFrameDimensions(media, maxWidth, maxHeight) {
  let width = Number(media.width || 0)
  let height = Number(media.height || 0)
  let ratio = width > 0 && height > 0 ? width / height : 16 / 9
  if (!Number.isFinite(ratio) || ratio <= 0) ratio = 16 / 9
  ratio = Math.min(Math.max(ratio, 0.1), 10)

  let portrait = ratio < 1
  let naturalHeight = maxWidth / ratio
  let displayWidth = portrait ? maxWidth : Math.min(maxWidth, maxHeight * ratio)
  let displayHeight = Math.min(displayWidth / ratio, maxHeight)
  let frameRatio = displayWidth / displayHeight
  return {
    ratio: frameRatio,
    width: Math.round(displayWidth * 100) / 100,
    height: Math.round(displayHeight * 100) / 100,
    letterboxed: portrait && naturalHeight > maxHeight,
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

export function getVideoExternalAction(attachment = {}) {
  if (
    attachment.type === 'video' &&
    ['external', 'provider_embed'].includes(attachment.video_source) &&
    attachment.open_url
  ) {
    return attachment.open_url
  }
  return getAttachmentAction(attachment)
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
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
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
