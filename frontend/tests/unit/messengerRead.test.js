import { createMessengerReadController } from '@/utils/messengerRead'
import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => vi.useRealTimers())

function harness({ enabled = true, provider = 'vk_direct' } = {}) {
  let messages = [
    {
      name: 'MSG-10',
      local_inbound_sequence: 10,
      conversation: 'CONV-1',
      direction: 'inbound',
      status: 'received',
      external_conversation_message_id: '10',
      external_message_id: 'provider-10',
    },
  ]
  let call = vi.fn(async () => ({
    ok: true,
    conversation: 'CONV-1',
    local_read_sequence: 10,
    unread_count: 0,
  }))
  let controller = createMessengerReadController({
    call,
    isEnabled: () => enabled,
    getConversation: () => ({ name: 'CONV-1', provider }),
    getMessages: () => messages,
  })
  return { controller, call, messages }
}

describe('messenger local read controller', () => {
  it('debounces and sends the local message name, not a raw CMID', async () => {
    vi.useFakeTimers()
    let { controller, call } = harness()
    controller.schedule()
    controller.schedule()
    await vi.advanceTimersByTimeAsync(600)
    expect(call).toHaveBeenCalledOnce()
    expect(call).toHaveBeenCalledWith(
      'crm_messenger.api.conversations.mark_read',
      { conversation: 'CONV-1', up_to_message: 'MSG-10' },
    )
  })

  it('does nothing while the view is inactive and never lowers its boundary', async () => {
    let inactive = harness({ enabled: false })
    expect(await inactive.controller.flush()).toBe(false)
    expect(inactive.call).not.toHaveBeenCalled()

    let active = harness()
    expect(await active.controller.flush()).toBe(true)
    expect(await active.controller.flush()).toBe(false)
    expect(active.call).toHaveBeenCalledOnce()
  })

  it.each(['avito_direct', 'telegram_bot', 'max_direct', 'vk_direct'])(
    'uses local sequence without external IDs for %s',
    async (provider) => {
      let { controller, call, messages } = harness({ provider })
      messages[0].external_conversation_message_id = null
      messages[0].external_message_id = null

      expect(await controller.flush()).toBe(true)
      expect(await controller.flush()).toBe(false)
      messages.push({
        ...messages[0],
        name: 'MSG-11',
        local_inbound_sequence: 11,
        external_message_id: 'provider-11',
      })
      expect(await controller.flush()).toBe(true)
      expect(call).toHaveBeenLastCalledWith(
        'crm_messenger.api.conversations.mark_read',
        { conversation: 'CONV-1', up_to_message: 'MSG-11' },
      )
    },
  )
})

it('reads late arrivals by local sequence even with smaller provider ID and earlier display position', async () => {
  let { controller, call, messages } = harness()
  await controller.flush()
  messages.unshift({
    ...messages[0],
    name: 'LATE',
    local_inbound_sequence: 11,
    external_conversation_message_id: '2',
  })
  await controller.flush()
  expect(call).toHaveBeenLastCalledWith(
    'crm_messenger.api.conversations.mark_read',
    { conversation: 'CONV-1', up_to_message: 'LATE' },
  )
})
it('excludes deleted messages and quiet history imports', async () => {
  let { controller, call, messages } = harness()
  messages[0].deleted_at = '2026-09-20 10:00:00'
  messages.push({
    ...messages[0],
    name: 'HISTORY',
    deleted_at: null,
    local_inbound_sequence: 0,
  })
  expect(await controller.flush()).toBe(false)
  expect(call).not.toHaveBeenCalled()
})
