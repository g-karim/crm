import { getProviderExternalChatUrl } from '@/utils/messengerExternalLinks'

export function isAvitoChatRestricted(channel) {
  return (
    channel?.provider === 'avito_direct' &&
    (channel?.capabilities?.messenger_access === 'subscription_required' ||
      [
        'messenger_subscription_required',
        'avito_subscription_required',
      ].includes(channel?.disabled_reason))
  )
}

export function restrictedAvitoChats(conversations = [], channels = []) {
  const byName = new Map(channels.map((channel) => [channel.name, channel]))
  return conversations
    .filter(
      (conversation) =>
        conversation.provider === 'avito_direct' &&
        isAvitoChatRestricted(
          byName.get(conversation.channel) || conversation.channel_info,
        ),
    )
    .map((conversation) => ({
      ...conversation,
      externalUrl: getProviderExternalChatUrl(
        'avito_direct',
        conversation.external_chat_id,
      ),
    }))
}
