import {
  maskExternalChatId,
  messengerConversationOption,
  messengerConversationsForChannel,
  resolveMessengerHandoffAction,
  resolveMessengerConversationSelection,
  resolveMessengerReplyConversation,
} from '@/utils/messengerRouting'

describe('messenger routing', () => {
  const conversations = [
    {
      name: 'VK-1',
      channel: 'VK',
      client_name: 'Иван',
      external_chat_id: '123456',
      status: 'Open',
    },
    {
      name: 'VK-2',
      channel: 'VK',
      external_chat_id: '987654',
      last_message: { text: 'Последнее сообщение' },
      status: 'Open',
    },
    {
      name: 'WA-1',
      channel: 'WA',
      external_chat_id: '79990001122',
      status: 'Open',
    },
    {
      name: 'VK-ARCHIVED',
      channel: 'VK',
      status: 'Archived',
    },
  ]

  it('keeps channel candidates separate and excludes archived chats', () => {
    expect(
      messengerConversationsForChannel(conversations, 'VK').map(
        (conversation) => conversation.name,
      ),
    ).toEqual(['VK-1', 'VK-2'])
  })

  it('resolves one chat and requires a choice for several chats', () => {
    expect(
      resolveMessengerConversationSelection({
        conversations,
        channel: 'WA',
      }),
    ).toMatchObject({
      state: 'resolved',
      conversation: { name: 'WA-1' },
    })
    expect(
      resolveMessengerConversationSelection({
        conversations,
        channel: 'VK',
      }),
    ).toMatchObject({
      state: 'ambiguous',
      conversation: null,
    })
    expect(
      resolveMessengerConversationSelection({
        conversations,
        channel: 'VK',
        selectedConversation: 'VK-2',
      }),
    ).toMatchObject({
      state: 'resolved',
      conversation: { name: 'VK-2' },
    })
  })

  it('builds a human conversation option with masked external id', () => {
    expect(maskExternalChatId('123456')).toBe('…3456')
    expect(messengerConversationOption(conversations[1])).toEqual({
      label: 'VK · …7654 · Последнее сообщение · VK-2',
      value: 'VK-2',
    })
  })

  it('uses a human attachment preview instead of a technical type marker', () => {
    expect(
      messengerConversationOption({
        name: 'TG-VOICE',
        channel: 'TG',
        last_message: {
          message_type: 'audio',
          display_text: 'Голосовое сообщение',
        },
      }).label,
    ).toContain('Голосовое сообщение')
    expect(
      messengerConversationOption({
        name: 'TG-VIDEO',
        channel: 'TG',
        last_message: { message_type: 'video' },
      }).label,
    ).toContain('Видео')
  })

  it('pins reply to the source conversation regardless of selected channel', () => {
    expect(
      resolveMessengerReplyConversation(conversations, {
        conversation: 'VK-2',
      }),
    ).toMatchObject({ name: 'VK-2', channel: 'VK' })
    expect(
      resolveMessengerReplyConversation(conversations, {
        conversation: 'missing',
      }),
    ).toBeNull()
  })

  it('switches an existing handoff target and creates only when none exists', () => {
    expect(resolveMessengerHandoffAction(conversations, 'WA')).toMatchObject({
      state: 'switch',
      conversation: { name: 'WA-1' },
    })
    expect(resolveMessengerHandoffAction(conversations, 'VK')).toMatchObject({
      state: 'ambiguous',
      conversation: null,
    })
    expect(resolveMessengerHandoffAction(conversations, 'MAX')).toMatchObject({
      state: 'create_handoff',
      conversation: null,
    })
  })
})
