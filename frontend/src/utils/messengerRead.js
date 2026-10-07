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
    // Arrival order in CRM is independent of provider IDs and display order.
    let message = (options.getMessages() || [])
      .filter(
        (item) =>
          item.conversation === conversation.name &&
          item.direction === 'inbound' &&
          item.status !== 'deleted' &&
          !item.deleted_at &&
          Number(item.local_inbound_sequence) > 0,
      )
      .reduce(
        (latest, item) =>
          !latest ||
          Number(item.local_inbound_sequence) >
            Number(latest.local_inbound_sequence)
            ? item
            : latest,
        null,
      )
    if (!message) return false
    let boundary = Number(message.local_inbound_sequence)
    if (boundary <= (lastRequested.get(conversation.name) || 0)) return false
    let result = await options.call(
      'crm_messenger.api.conversations.mark_read',
      { conversation: conversation.name, up_to_message: message.name },
    )
    if (!result?.ok)
      throw new Error(result?.message || 'Could not mark messages as read.')
    lastRequested.set(
      conversation.name,
      Math.max(
        lastRequested.get(conversation.name) || 0,
        boundary,
        Number(result.local_read_sequence) || 0,
      ),
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
