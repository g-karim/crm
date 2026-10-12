import { find } from 'linkifyjs'

export function getMessengerTextSegments(value = '') {
  let text = String(value ?? '')
  let segments = []
  let cursor = 0

  for (let link of find(text, 'url')) {
    // Linkify handles ASCII punctuation; closing typographic quotes and an
    // ellipsis also belong to the surrounding message rather than the URL.
    let url = link.value.replace(/[»”’…]+$/u, '')
    if (!isSafeHttpUrl(url)) continue

    if (link.start > cursor) {
      segments.push({ text: text.slice(cursor, link.start) })
    }
    segments.push({ text: url, href: url })
    cursor = link.start + url.length
  }

  if (cursor < text.length) segments.push({ text: text.slice(cursor) })
  return segments
}

function isSafeHttpUrl(value) {
  if (!/^https?:\/\//iu.test(value) || /[\p{Cc}\p{Cf}\\]/u.test(value)) {
    return false
  }
  try {
    let url = new URL(value)
    return Boolean(
      ['http:', 'https:'].includes(url.protocol) &&
      url.hostname &&
      !url.username &&
      !url.password,
    )
  } catch {
    return false
  }
}
