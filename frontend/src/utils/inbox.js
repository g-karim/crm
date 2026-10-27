import DOMPurify from 'dompurify'

export const inboxViews = [
  ['open', 'Все открытые'],
  ['mine', 'Мои'],
  ['unassigned', 'Без ответственного'],
  ['needs_reply', 'Ждут ответа'],
  ['waiting_customer', 'Ждём клиента'],
  ['unread', 'Непрочитанные'],
  ['snoozed', 'Отложенные'],
  ['closed', 'Закрытые'],
  ['all', 'Вся история'],
]

export const inboxStatuses = [
  { value: 'needs_reply', label: 'Ждёт нашего ответа' },
  { value: 'waiting_customer', label: 'Ждём клиента' },
  { value: 'snoozed', label: 'Отложен' },
  { value: 'closed', label: 'Закрыт' },
]

export function channelLabel(channel) {
  return (
    {
      email: 'Почта',
      telegram: 'Telegram',
      vk: 'ВКонтакте',
      max: 'MAX',
      avito: 'Авито',
      whatsapp: 'WhatsApp',
    }[channel] ||
    channel ||
    'Мессенджер'
  )
}

export function draftKey(viewer, id) {
  if (!viewer || viewer === 'Guest' || !id) return null
  return `crm:inbox:v1:${encodeURIComponent(viewer)}:${encodeURIComponent(id)}`
}

export function restoreInboxDraft(local, server) {
  if (!local) return { draft: server.draft, conflict: false }
  const draft = local.draft || local
  const changed = draftFingerprint(draft) !== draftFingerprint(server.draft)
  const hasText = Boolean(draft.text?.trim() || draft.attachments?.length)
  return {
    draft,
    conflict: Boolean(hasText && changed && local.revision !== server.revision),
  }
}

export function mergeMessages(previous, incoming) {
  const map = new Map(previous.map((m) => [m.name, m]))
  incoming.forEach((m) => map.set(m.name, m))
  return [...map.values()].sort((a, b) => {
    const left = [a.message_datetime || a.creation, a.creation, a.name].join(
      '\0',
    )
    const right = [b.message_datetime || b.creation, b.creation, b.name].join(
      '\0',
    )
    return left.localeCompare(right)
  })
}

export function draftFingerprint(value) {
  return JSON.stringify(value, (_, item) =>
    item && typeof item === 'object' && !Array.isArray(item)
      ? Object.fromEntries(
          Object.keys(item)
            .sort()
            .map((key) => [key, item[key]]),
        )
      : item,
  )
}

export function deliveryLabel(message, demo = false) {
  if (message.direction === 'inbound') return ''
  if (demo) return 'Локальный пример · не отправлено'
  return (
    {
      queued: 'В очереди',
      sending: 'Отправляется',
      sent: 'Отправлено',
      delivered: 'Доставлено',
      read: 'Прочитано',
      failed: 'Ошибка отправки',
      unknown: 'Доставка не подтверждена',
      retrying: 'Повторная попытка',
      'Not Sent': 'Не отправлено',
      Sent: 'Отправлено',
      Error: 'Ошибка отправки',
    }[message.delivery_status || message.status] || 'Статус доставки не получен'
  )
}

export function safeEmailDocument(content = '') {
  const sanitized = DOMPurify.sanitize(content, {
    FORBID_TAGS: [
      'img',
      'video',
      'audio',
      'iframe',
      'form',
      'style',
      'link',
      'input',
      'button',
    ],
    FORBID_ATTR: ['src', 'srcset', 'style', 'href', 'action', 'background'],
  })
  // An inert formatting-only document is a second boundary, including in DOM
  // implementations where DOMPurify declines support. Mail never gets URLs.
  const doc = new DOMParser().parseFromString(sanitized, 'text/html')
  const tags = new Set([
    'P',
    'BR',
    'DIV',
    'SPAN',
    'B',
    'STRONG',
    'I',
    'EM',
    'U',
    'S',
    'UL',
    'OL',
    'LI',
    'BLOCKQUOTE',
    'PRE',
    'CODE',
    'TABLE',
    'TBODY',
    'THEAD',
    'TR',
    'TD',
    'TH',
    'H1',
    'H2',
    'H3',
    'H4',
    'HR',
    'A',
  ])
  for (const element of [...doc.body.querySelectorAll('*')]) {
    if (
      [
        'SCRIPT',
        'STYLE',
        'IFRAME',
        'OBJECT',
        'EMBED',
        'SVG',
        'MATH',
        'TEMPLATE',
      ].includes(element.tagName)
    ) {
      element.remove()
      continue
    }
    for (const attribute of [...element.attributes])
      element.removeAttribute(attribute.name)
    if (!tags.has(element.tagName)) element.replaceWith(...element.childNodes)
  }
  const safe = doc.body.innerHTML
  return `<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><style>body{font:15px/1.6 system-ui;overflow-wrap:anywhere;margin:12px}table{max-width:100%}pre{white-space:pre-wrap}</style></head><body>${safe}</body></html>`
}

export function quoteMessage(text = '') {
  return (
    text
      .split('\n')
      .map((line) => `> ${line}`)
      .join('\n') + '\n\n'
  )
}
