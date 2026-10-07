const AVITO_MESSENGER_URL = 'https://www.avito.ru/profile/messenger'
const AVITO_CHAT_ID_PATTERN = /^[A-Za-z0-9_~-]{26}$/

export function getProviderExternalChatUrl(provider, externalChatId) {
  if (provider !== 'avito_direct') return ''

  let chatId = String(externalChatId || '').trim()
  if (!AVITO_CHAT_ID_PATTERN.test(chatId)) return AVITO_MESSENGER_URL

  return `${AVITO_MESSENGER_URL}/channel/${encodeURIComponent(chatId)}`
}
