function text(value) {
  return typeof value === 'string' ? value.trim() : ''
}

function safeUrl(value, listing = false) {
  try {
    let url = new URL(text(value))
    if (url.protocol !== 'https:' || url.username || url.password) return ''
    if (
      listing &&
      url.hostname !== 'avito.ru' &&
      !url.hostname.endsWith('.avito.ru')
    )
      return ''
    return url.href
  } catch {
    return ''
  }
}

export function getAvitoItem(conversation) {
  if (conversation?.provider !== 'avito_direct') return null
  let item = conversation.avito_item || {}
  let images = item.images_main
  let image =
    images && typeof images === 'object'
      ? Object.entries(images)
          .sort(([a], [b]) => imageArea(b) - imageArea(a))
          .map(([, url]) => safeUrl(url))
          .find(Boolean) || ''
      : ''
  return {
    id: text(item.id),
    title: text(item.title),
    price: text(item.price_string),
    url: safeUrl(item.url, true),
    image,
  }
}

function imageArea(size) {
  let match = /^(\d+)x(\d+)$/.exec(size)
  return match ? Number(match[1]) * Number(match[2]) : 0
}

export function avitoConversationLabel(conversation, translate = (s) => s) {
  let item = getAvitoItem(conversation)
  if (!item) return ''
  return [
    item.title || translate('Avito listing'),
    item.id ? `#${item.id}` : '',
    conversation.name,
  ]
    .filter(Boolean)
    .join(' · ')
}
