export function getMessengerMessageTextPresentation(message = {}) {
  let text = String(message?.text || '')
  let normalizedText = text.trim().toLowerCase()
  let attachments = Array.isArray(message?.attachments)
    ? message.attachments
    : []

  if (message?.message_type === 'image' && normalizedText === '[image]') {
    return { text: '', translate: false }
  }

  if (
    message?.provider === 'avito_direct' &&
    ['audio', 'voice'].includes(message?.message_type) &&
    attachments.some(isVoiceAttachment) &&
    /^(?:voice message|голосовое сообщение)\s*:\s*\S+\s*$/iu.test(text)
  ) {
    return { text: '', translate: false }
  }

  if (
    message?.provider === 'avito_direct' &&
    message?.message_type === 'video' &&
    !attachments.some(isVideoAttachment)
  ) {
    return {
      text: 'Video is unavailable through the Avito API.',
      translate: true,
      action: 'open_provider_chat',
    }
  }

  return { text, translate: false }
}

export function shouldShowMessengerMessageText(message = {}) {
  if (message?.status === 'deleted') return true
  return Boolean(getMessengerMessageTextPresentation(message).text.trim())
}

function isVoiceAttachment(attachment = {}) {
  return Boolean(
    attachment.is_voice || ['audio', 'voice'].includes(attachment.type),
  )
}

function isVideoAttachment(attachment = {}) {
  return attachment.type === 'video'
}
