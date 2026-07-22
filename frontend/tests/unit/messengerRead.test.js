import { createMessengerReadController } from '@/utils/messengerRead'
import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => vi.useRealTimers())

function harness({ enabled = true } = {}) {
  let messages = [
    {
      name: 'MSG-10',
      conversation: 'CONV-1',
      direction: 'inbound',
      status: 'received',
      external_conversation_message_id: '10',
    },
  ]
  let call = vi.fn(async () => ({
    ok: true,
    conversation: 'CONV-1',
    up_to_cmid: 10,
    unread_count: 0,
  }))
  let controller = createMessengerReadController({
    call,
    isEnabled: () => enabled,
    getConversation: () => ({ name: 'CONV-1' }),
    getMessages: () => messages,
  })
  return { controller, call, messages }
}

describe('messenger provider read controller', () => {
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
})
