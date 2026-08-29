const ATTACHMENT_ONLY_TYPES = new Set([
  'image',
  'video',
  'audio',
  'file',
  'sticker',
])

export function getForwardedContentKind(context) {
  let hasAttachment = false
  let messageContent = false

  function visit(items = []) {
    items.forEach((item) => {
      if (String(item?.text || '').trim()) messageContent = true
      let attachmentTypes = item?.attachment_types || []
      attachmentTypes.forEach((type) => {
        hasAttachment = true
        if (!ATTACHMENT_ONLY_TYPES.has(type)) messageContent = true
      })
      visit(item?.items)
    })
  }

  visit(context?.items)
  return hasAttachment && !messageContent ? 'attachment' : 'message'
}

export function isMaxForwardOnlyMessage(message = {}) {
  return Boolean(
    message.provider === 'max_direct' &&
    message.status !== 'deleted' &&
    message.forward_context &&
    !String(message.text || '').trim() &&
    !(message.attachments || []).length &&
    !message.reply_context,
  )
}

export function isStickerOnlyForwardItem(item = {}) {
  let attachments = Array.isArray(item?.attachments) ? item.attachments : []
  let children = Array.isArray(item?.items) ? item.items : []
  return Boolean(
    !String(item?.text || '').trim() &&
    attachments.length === 1 &&
    attachments[0]?.type === 'sticker' &&
    !children.length,
  )
}

export function isStickerOnlyForwardContext(context = {}) {
  let items = Array.isArray(context?.items) ? context.items : []
  return items.length === 1 && isStickerOnlyForwardItem(items[0])
}
