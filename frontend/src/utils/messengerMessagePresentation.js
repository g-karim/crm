import { getMessengerAttachmentTitle } from '@/utils/messengerAttachments'

export function getMessengerMessageTextPresentation(message = {}) {
  let text = String(message?.text || '')
  let normalizedText = text.trim().toLowerCase()
  let attachments = Array.isArray(message?.attachments)
    ? message.attachments
    : []

  if (
    message?.provider === 'wazzup' &&
    message.text_is_attachment_filename &&
    attachments.length === 1 &&
    attachments[0].type === 'file' &&
    text.trim() === attachments[0].file_name
  ) {
    return { text: '', translate: false }
  }

  if (
    message?.provider === 'wazzup' &&
    message.direction === 'inbound' &&
    attachments.length === 1 &&
    attachments[0].type === 'file'
  ) {
    let attachment = attachments[0]
    let filename = getMessengerAttachmentTitle({
      ...attachment,
      provider: message.provider,
    })
    // Wazzup does not identify filename text separately from an equal caption.
    // Collapse exact duplicates only when that name is shown in the file card.
    if (
      text === filename &&
      [attachment.original_file_name, attachment.file_name].includes(filename)
    ) {
      return { text: '', translate: false }
    }
  }

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

  if (
    !text.trim() &&
    message?.status !== 'deleted' &&
    !attachments.length &&
    !message?.template_context &&
    !message?.forward_context?.items?.length
  ) {
    return { text: 'Content unavailable', translate: true }
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
