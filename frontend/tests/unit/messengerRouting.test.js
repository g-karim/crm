import {
  maskExternalChatId,
  messengerConversationConflictTarget,
  messengerPersistedConversationConflict,
  messengerConversationOption,
  messengerConversationsForChannel,
  resolveMessengerHandoffAction,
  resolveMessengerConversationSelection,
  resolveMessengerReplyConversation,
} from '@/utils/messengerRouting'
import { computed, ref } from 'vue'

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
      messengerConversationOption(
        {
          name: 'TG-VIDEO',
          channel: 'TG',
          last_message: { message_type: 'video' },
        },
        (message) => (message === 'Video' ? 'Видео' : message),
      ),
    ).toEqual({ label: 'TG · Видео · TG-VIDEO', value: 'TG-VIDEO' })
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

  it('links a binding conflict only to the readable Lead supplied by the server', () => {
    expect(
      messengerConversationConflictTarget({
        reason: 'conversation_link_conflict',
        existing_reference: { doctype: 'CRM Lead', name: 'LEAD-OLD' },
      }),
    ).toEqual({ name: 'Lead', params: { leadId: 'LEAD-OLD' } })
    for (let result of [
      { reason: 'conversation_link_conflict' },
      {
        reason: 'conversation_link_conflict',
        existing_reference: { doctype: 'CRM Lead', name: ' ' },
      },
      {
        reason: 'conversation_link_conflict',
        existing_reference: { doctype: 'User', name: 'Administrator' },
      },
      {
        reason: 'missing_phone',
        existing_reference: { doctype: 'CRM Lead', name: 'LEAD-OLD' },
      },
    ]) {
      expect(messengerConversationConflictTarget(result)).toBeNull()
    }
  })
})

describe('persisted Partner conversation conflicts', () => {
  const channel = {
    name: 'PARTNER-TG',
    provider: 'wazzup',
    wazzup_api_mode: 'partner_api_v2',
    platform: 'telegram',
  }
  const conversation = {
    name: 'PROVISIONAL-TG',
    provider: 'wazzup',
    channel: channel.name,
    reference_doctype: 'CRM Lead',
    reference_name: 'LEAD-NEW',
  }
  const bindingConflict = {
    ok: false,
    reason: 'conversation_link_conflict',
    message: 'This chat is already linked to another lead.',
    existing_reference: { doctype: 'CRM Lead', name: 'LEAD-OLD' },
  }
  const message = {
    name: 'FIRST-SEND',
    provider: 'wazzup',
    conversation: conversation.name,
    channel: channel.name,
    direction: 'outbound',
    binding_conflict: bindingConflict,
  }
  const scope = { conversation, channel, leadName: 'LEAD-NEW' }

  it('reacts to an exact echo conflict arriving in a delta or loaded history', () => {
    let messages = ref([{ ...message, binding_conflict: null }])
    let notice = computed(() =>
      messengerPersistedConversationConflict({
        ...scope,
        messages: messages.value,
      }),
    )
    expect(notice.value).toBeNull()
    messages.value = [{ ...message }]
    expect(notice.value).toEqual(bindingConflict)
    expect(messengerConversationConflictTarget(notice.value)).toEqual({
      name: 'Lead',
      params: { leadId: 'LEAD-OLD' },
    })
    messages.value = [{ ...message }, { name: 'RECENT', direction: 'inbound' }]
    expect(notice.value).toEqual(bindingConflict)
  })

  it('does not expose conflicts from another Lead, channel, conversation or provider', () => {
    for (let altered of [
      { leadName: 'LEAD-OTHER' },
      { conversation: { ...conversation, name: 'OTHER-CONVERSATION' } },
      { conversation: { ...conversation, reference_name: 'LEAD-OTHER' } },
      { channel: { ...channel, name: 'OTHER-CHANNEL' } },
      { channel: { ...channel, provider: 'telegram_bot' } },
      { channel: { ...channel, wazzup_api_mode: 'user_api_v3' } },
    ]) {
      expect(
        messengerPersistedConversationConflict({
          ...scope,
          ...altered,
          messages: [message],
        }),
      ).toBeNull()
    }
    for (let alteredMessage of [
      { provider: 'telegram_bot' },
      { channel: 'OTHER-CHANNEL' },
      { conversation: 'OTHER-CONVERSATION' },
      { direction: 'inbound' },
    ]) {
      expect(
        messengerPersistedConversationConflict({
          ...scope,
          messages: [{ ...message, ...alteredMessage }],
        }),
      ).toBeNull()
    }
  })

  it('clears the notice on navigation and keeps unreadable references without a link', () => {
    let leadName = ref('LEAD-NEW')
    let messages = ref([
      {
        ...message,
        binding_conflict: { ...bindingConflict, existing_reference: undefined },
      },
    ])
    let notice = computed(() =>
      messengerPersistedConversationConflict({
        ...scope,
        leadName: leadName.value,
        messages: messages.value,
      }),
    )
    expect(notice.value?.reason).toBe('conversation_link_conflict')
    expect(messengerConversationConflictTarget(notice.value)).toBeNull()
    leadName.value = 'LEAD-OTHER'
    expect(notice.value).toBeNull()
  })
})
