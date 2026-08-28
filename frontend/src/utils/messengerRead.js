const DEFAULT_DEBOUNCE_MS = 600

export function createMessengerReadController(options) {
  let timer = null
  let lastRequested = new Map()

  function schedule() {
    clearTimeout(timer)
    if (!options.isEnabled()) return
    timer = setTimeout(() => {
      flush().catch((error) => options.onError?.(error))
    }, options.debounceMs || DEFAULT_DEBOUNCE_MS)
  }

  async function flush() {
    timer = null
    if (!options.isEnabled()) return false
    let conversation = options.getConversation()
    if (!conversation?.name) return false
    let message = [...(options.getMessages() || [])]
      .reverse()
      .find(
        (item) =>
          item.conversation === conversation.name &&
          item.direction === 'inbound' &&
          item.status !== 'deleted' &&
          Number(item.external_conversation_message_id) > 0,
      )
    if (!message) return false
    let cmid = Number(message.external_conversation_message_id)
    if (cmid <= (lastRequested.get(conversation.name) || 0)) return false
    let result = await options.call(
      'crm_messenger.api.conversations.mark_read',
      { conversation: conversation.name, up_to_message: message.name },
    )
    if (!result?.ok)
      throw new Error(
        result?.message || 'Не удалось отметить сообщения прочитанными.',
      )
    lastRequested.set(
      conversation.name,
      Math.max(cmid, Number(result.up_to_cmid) || 0),
    )
    options.onConfirmed?.(result)
    return true
  }

  function reset(conversation) {
    clearTimeout(timer)
    timer = null
    if (!conversation) lastRequested.clear()
  }

  function stop() {
    clearTimeout(timer)
    timer = null
    lastRequested.clear()
  }

  return { schedule, flush, reset, stop }
}
