import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { messengerConversationConflictTarget } from '@/utils/messengerRouting'

const source = readFileSync(
  resolve(process.cwd(), 'src/components/LeadMessenger/LeadConversation.vue'),
  'utf8',
)
const ref = (value) => ({ value })
const conflict = {
  ok: false,
  reason: 'conversation_link_conflict',
  message: 'This chat is already linked to another lead.',
  existing_reference: { doctype: 'CRM Lead', name: 'LEAD-OLD' },
}

// Execute the production send handlers with local RPC doubles. This covers
// draft ownership and stale responses without a Frappe site or provider I/O.
function handler(name, bindings, text = source) {
  let code = text.match(
    new RegExp(`^(?:async )?function ${name}\\([^]*?^\\}`, 'm'),
  )[0]
  return new Function(...Object.keys(bindings), `return (${code})`)(
    ...Object.values(bindings),
  )
}

function context() {
  let current = true
  let captured = { lead: 'LEAD-NEW', isCurrent: () => current }
  return { captured, expire: () => (current = false) }
}

function bindings(captured) {
  let values = {
    __: (message) => message,
    genericError: ref(''),
    conversationConflictTarget: ref(null),
    messengerConversationConflictTarget,
    call: vi.fn().mockResolvedValue(conflict),
    selectedChannel: ref('WA'),
    selectedCapabilities: ref({ requires_inbound: false }),
    conversations: ref([]),
    selectedConversationName: ref(''),
    preserveComposerDuringScopeChange: (change) => change(),
  }
  values.handleConversationLinkConflict = handler(
    'handleConversationLinkConflict',
    values,
  )
  return { ...values, captureLeadContext: () => captured }
}

describe('conversation binding conflict handlers', () => {
  it('does not adopt a conflicting conversation returned while creating the first chat', async () => {
    let { captured } = context()
    let values = bindings(captured)
    let create = handler('createConversation', values)
    expect(await create(captured)).toBeNull()
    expect(values.conversations.value).toEqual([])
    expect(values.selectedConversationName.value).toBe('')
    expect(values.conversationConflictTarget.value).toEqual({
      name: 'Lead',
      params: { leadId: 'LEAD-OLD' },
    })
  })

  it('does not show a previous Lead conflict after navigation', async () => {
    let { captured, expire } = context()
    let values = bindings(captured)
    let finish
    values.call.mockImplementation(() => new Promise((done) => (finish = done)))
    let pending = handler('createConversation', values)(captured)
    expire()
    finish(conflict)
    await pending
    expect(values.genericError.value).toBe('')
    expect(values.conversationConflictTarget.value).toBeNull()
  })

  it('keeps the draft, attachment ownership and reply when the final send finds a conflict', async () => {
    let { captured } = context()
    let values = {
      ...bindings(captured),
      permissions: ref({ can_operate: true }),
      preparedHandoff: ref(null),
      draftText: ref('Keep this draft'),
      voiceActive: ref(false),
      pendingAttachments: ref([{ name: 'ATTACHMENT-1' }]),
      pendingLocation: ref(null),
      sendDisabled: ref(false),
      replyTarget: ref({ name: 'REPLY-1' }),
      sendWarning: ref(''),
      sendingMessage: ref(false),
      composerAttachments: ref({
        freeze: vi.fn().mockReturnValue(['ATTACHMENT-1']),
        unfreeze: vi.fn(),
        release: vi.fn(),
      }),
      resolveConversationForSend: vi.fn().mockResolvedValue({ name: 'CONV-1' }),
      clientRequestId: ref(''),
      clientRequestFingerprint: ref(''),
      makeClientRequestId: () => 'CLIENT-1',
      composerTyping: { reset: vi.fn() },
      cancelReply: vi.fn(),
      handleError: vi.fn(),
      refreshConversations: vi.fn(),
      messageSync: { syncDelta: vi.fn() },
    }
    await handler('sendMessage', values)()
    expect(values.draftText.value).toBe('Keep this draft')
    expect(values.replyTarget.value).toEqual({ name: 'REPLY-1' })
    expect(values.composerAttachments.value.unfreeze).toHaveBeenCalledOnce()
    expect(values.composerAttachments.value.release).not.toHaveBeenCalled()
    expect(values.cancelReply).not.toHaveBeenCalled()
    expect(values.genericError.value).toBe(conflict.message)
    expect(values.sendingMessage.value).toBe(false)
  })

  it('shows a conflict from route resolution before attempting chat creation', async () => {
    let { captured } = context()
    let values = {
      ...bindings(captured),
      selectedConversation: ref(null),
      replyTarget: ref(null),
      createConversation: vi.fn(),
    }
    expect(
      await handler('resolveConversationForSend', values)(captured),
    ).toBeNull()
    expect(values.createConversation).not.toHaveBeenCalled()
    expect(values.genericError.value).toBe(conflict.message)
  })
})
