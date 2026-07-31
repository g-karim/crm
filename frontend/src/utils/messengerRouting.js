export function messengerConversationsForChannel(
  conversations = [],
  channel = '',
) {
  return conversations.filter(
    (conversation) =>
      conversation?.channel === channel && conversation?.status !== 'Archived',
  )
}

export function resolveMessengerConversationSelection({
  conversations = [],
  channel = '',
  selectedConversation = '',
} = {}) {
  let candidates = messengerConversationsForChannel(conversations, channel)
  let selected = candidates.find(
    (conversation) => conversation.name === selectedConversation,
  )
  if (selected) return { state: 'resolved', conversation: selected, candidates }
  if (candidates.length === 1)
    return { state: 'resolved', conversation: candidates[0], candidates }
  return {
    state: candidates.length ? 'ambiguous' : 'missing',
    conversation: null,
    candidates,
  }
}

export function messengerConversationOption(conversation = {}) {
  let platform =
    conversation.channel_info?.label ||
    conversation.platform ||
    conversation.chat_type ||
    conversation.provider
  let channel = conversation.channel_info?.name || conversation.channel
  let externalId =
    conversation.external_chat_id_masked ||
    maskExternalChatId(conversation.external_chat_id)
  let lastMessage =
    conversation.last_message?.text ||
    (conversation.last_message?.message_type &&
    conversation.last_message.message_type !== 'text'
      ? `[${conversation.last_message.message_type}]`
      : '')
  let label = [
    platform,
    channel,
    conversation.client_name,
    externalId,
    lastMessage,
    conversation.last_message_at,
    conversation.name,
  ]
    .filter(Boolean)
    .join(' · ')
  return {
    label: label || conversation.name,
    value: conversation.name,
  }
}

export function resolveMessengerReplyConversation(
  conversations = [],
  message = {},
) {
  if (!message?.conversation) return null
  return (
    conversations.find(
      (conversation) => conversation.name === message.conversation,
    ) || null
  )
}

export function resolveMessengerHandoffAction(
  conversations = [],
  targetChannel = '',
) {
  let candidates = messengerConversationsForChannel(
    conversations,
    targetChannel,
  )
  if (candidates.length === 1)
    return { state: 'switch', conversation: candidates[0], candidates }
  if (candidates.length > 1)
    return { state: 'ambiguous', conversation: null, candidates }
  return { state: 'create_handoff', conversation: null, candidates }
}

export function maskExternalChatId(value) {
  let text = `${value || ''}`
  if (!text) return ''
  return text.length <= 4 ? text : `…${text.slice(-4)}`
}
