import { createMessengerTypingController } from '@/utils/messengerTyping'

describe('messengerTyping', () => {
  it('sends immediately and repeats only after continued input past four seconds', async () => {
    let now = 1000
    let sent = []
    let controller = createMessengerTypingController({
      now: () => now,
      send: (conversation) => sent.push(conversation),
    })

    expect(
      controller.input({ text: 'П', conversation: 'CONV-1', enabled: true }),
    ).toBe(true)
    now += 3999
    expect(
      controller.input({ text: 'Пр', conversation: 'CONV-1', enabled: true }),
    ).toBe(false)
    now += 1
    expect(
      controller.input({ text: 'При', conversation: 'CONV-1', enabled: true }),
    ).toBe(true)
    expect(sent).toEqual(['CONV-1', 'CONV-1'])
  })

  it('resets on empty, disabled, or changed conversations', () => {
    let now = 1000
    let sent = []
    let controller = createMessengerTypingController({
      now: () => now,
      send: (conversation) => sent.push(conversation),
    })
    controller.input({ text: 'A', conversation: 'CONV-1', enabled: true })
    now += 10
    controller.input({ text: '', conversation: 'CONV-1', enabled: true })
    controller.input({ text: 'B', conversation: 'CONV-1', enabled: true })
    controller.input({ text: 'C', conversation: 'CONV-2', enabled: true })
    controller.input({ text: 'D', conversation: 'CONV-2', enabled: false })
    controller.input({ text: 'E', conversation: 'CONV-2', enabled: true })
    expect(sent).toEqual(['CONV-1', 'CONV-1', 'CONV-2', 'CONV-2'])
  })

  it('swallows rejected typing requests', async () => {
    let controller = createMessengerTypingController({
      now: () => 1000,
      send: () => Promise.reject(new Error('offline')),
    })
    expect(
      controller.input({ text: 'A', conversation: 'CONV-1', enabled: true }),
    ).toBe(true)
    await Promise.resolve()
  })
})
