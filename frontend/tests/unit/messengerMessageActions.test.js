import {
  canDeleteMessengerMessage,
  canEditMessengerMessage,
  canSaveMessengerMessageEdit,
  createMessengerMessageActions,
  getMessengerMessageActions,
  getMessengerMessageDisplay,
  getMessengerMessageDeleteNotice,
  getMessengerMessageEditNotice,
  getMessengerRetryConfirmation,
  openMessengerMessageEditor,
  revealMessengerEditor,
} from '@/utils/messengerMessageActions'
import { describe, expect, it, vi } from 'vitest'

const editable = (overrides = {}) => ({
  name: 'MSG-1',
  text: 'original',
  status: 'sent',
  can_edit: true,
  can_delete: true,
  can_edit_empty: false,
  edit_max_length: 9000,
  ...overrides,
})

const wazzupEditable = (overrides = {}) =>
  editable({ provider: 'wazzup', message_type: 'text', ...overrides })

function harness(response = { ok: true }) {
  let states = []
  let call = vi.fn(async () => response)
  let sync = vi.fn(async () => {})
  let onError = vi.fn()
  let controller = createMessengerMessageActions({
    call,
    sync,
    onError,
    onChange: (state) => states.push(state),
  })
  return { controller, call, sync, onError, states }
}

describe('messenger message actions', () => {
  it('builds the menu only from backend can_edit/can_delete flags', () => {
    expect(getMessengerMessageActions(editable())).toEqual(['edit', 'delete'])
    expect(getMessengerMessageActions(editable({ can_edit: false }))).toEqual([
      'delete',
    ])
    expect(getMessengerMessageActions(editable({ can_delete: false }))).toEqual(
      ['edit'],
    )
    expect(
      getMessengerMessageActions(
        editable({ can_edit: false, can_delete: false }),
      ),
    ).toEqual([])
  })

  it('adds reply and retry only from backend flags', () => {
    expect(
      getMessengerMessageActions(
        editable({ can_reply: true, can_retry: true }),
      ),
    ).toEqual(['reply', 'retry', 'edit', 'delete'])
    expect(
      getMessengerMessageActions(
        editable({ can_reply: false, can_retry: false }),
      ),
    ).toEqual(['edit', 'delete'])
    expect(
      getMessengerMessageActions({
        provider: 'max_direct',
        can_reply: true,
        can_retry: false,
        can_edit: false,
        can_delete: false,
      }),
    ).toEqual(['reply'])
  })

  it('retries the same backend message with explicit unknown confirmation', async () => {
    let message = editable({ can_retry: true, status: 'unknown' })
    let { controller, call, sync } = harness()

    expect(await controller.retryMessage(message, true)).toBe(true)
    expect(call).toHaveBeenCalledWith(
      'crm_messenger.api.messages.retry_outbound_message',
      { message: 'MSG-1', confirm_unknown: 1 },
    )
    expect(sync).toHaveBeenCalledOnce()
  })

  it('uses Avito-specific ambiguous retry copy without VK request ID claims', () => {
    let confirmation = getMessengerRetryConfirmation({
      provider: 'avito_direct',
      status: 'unknown',
    })

    expect(confirmation.title).toBe('Retry sending?')
    expect(confirmation.message).toContain('Avito may have accepted')
    expect(confirmation.message).toContain('may create a duplicate')
    expect(confirmation.message).not.toContain('VK')
    expect(confirmation.message).not.toContain('same request ID')
  })

  it('does not promise that a VK request ID makes resending safe', () => {
    let confirmation = getMessengerRetryConfirmation({
      provider: 'vk_direct',
      status: 'unknown',
    })

    expect(confirmation.message).toContain('VK may have already accepted')
    expect(confirmation.message).toContain('may create a duplicate')
    expect(confirmation.message).not.toContain('same request ID')
  })

  it.each([false, true])(
    'blocks retry of an unknown VK image even with stale can_retry=%s',
    async (canRetry) => {
      let message = {
        name: 'VK-UNKNOWN',
        provider: 'vk_direct',
        direction: 'outbound',
        message_type: 'image',
        status: 'unknown',
        delivery_status: 'unknown',
        can_retry: canRetry,
      }
      let { controller, call } = harness()

      expect(getMessengerMessageActions(message)).toEqual([])
      expect(await controller.retryMessage(message)).toBe(false)
      expect(await controller.retryMessage(message, true)).toBe(false)
      expect(call).not.toHaveBeenCalled()
    },
  )

  it('allows an explicit retry after a definitive VK image failure', async () => {
    let message = {
      name: 'VK-FAILED',
      provider: 'vk_direct',
      direction: 'outbound',
      message_type: 'image',
      status: 'failed',
      delivery_status: 'failed',
      can_retry: true,
    }
    let { controller, call } = harness()

    expect(getMessengerMessageActions(message)).toEqual(['retry'])
    expect(await controller.retryMessage(message)).toBe(true)
    expect(call).toHaveBeenCalledOnce()
    expect(call).toHaveBeenCalledWith(
      'crm_messenger.api.messages.retry_outbound_message',
      { message: 'VK-FAILED', confirm_unknown: 0 },
    )
  })

  it('does not promise VK idempotency or retry a blocked Wazzup unknown result', async () => {
    let message = {
      name: 'WAZZUP-UNKNOWN',
      provider: 'wazzup',
      direction: 'outbound',
      status: 'unknown',
      delivery_status: 'unknown',
      can_retry: false,
    }
    let confirmation = getMessengerRetryConfirmation(message)

    expect(confirmation.message).toContain('may create a duplicate')
    expect(confirmation.message).not.toContain('VK')
    expect(confirmation.message).not.toContain('same request ID')
    expect(getMessengerMessageActions(message)).toEqual([])
    let { controller, call } = harness()
    expect(await controller.retryMessage(message, true)).toBe(false)
    expect(call).not.toHaveBeenCalled()
  })

  it.each(['whatsapp', 'telegram'])(
    'blocks an unknown Wazzup %s send even when retry eligibility is stale',
    async (platform) => {
      let message = {
        name: 'WAZZUP-UNKNOWN',
        provider: 'wazzup',
        platform,
        direction: 'outbound',
        status: 'unknown',
        delivery_status: 'unknown',
        can_retry: true,
      }
      let { controller, call } = harness()

      expect(getMessengerMessageActions(message)).toEqual([])
      expect(await controller.retryMessage(message)).toBe(false)
      expect(await controller.retryMessage(message, true)).toBe(false)
      expect(call).not.toHaveBeenCalled()
    },
  )

  it('exposes tombstone and edited marker display states', () => {
    expect(getMessengerMessageDisplay(editable({ is_edited: 1 }))).toEqual({
      tombstone: false,
      edited: true,
      text: 'original',
    })
    expect(
      getMessengerMessageDisplay(
        editable({ status: 'deleted', text: 'must not render', is_edited: 1 }),
      ),
    ).toEqual({ tombstone: true, edited: false, text: '' })
  })

  it('trusts the canonical backend edit flag for attachment-only messages', () => {
    expect(
      getMessengerMessageDisplay(
        editable({
          text: '',
          message_type: 'sticker',
          is_edited: 0,
          last_update_source: 'provider_history',
        }),
      ).edited,
    ).toBe(false)
    expect(
      getMessengerMessageDisplay(
        editable({
          text: '',
          message_type: 'image',
          is_edited: 1,
          attachments: [{ id: 'I-1', type: 'image' }],
        }),
      ).edited,
    ).toBe(true)
  })

  it('edits inline, sends no provider credentials and waits for delta', async () => {
    let message = editable()
    let { controller, call, sync } = harness()

    expect(controller.startEdit(message)).toBe(true)
    controller.setDraft('edited')
    expect(await controller.saveEdit(message)).toBe(true)

    expect(call).toHaveBeenCalledWith(
      'crm_messenger.api.messages.edit_message',
      { message: 'MSG-1', text: 'edited' },
    )
    expect(sync).toHaveBeenCalledOnce()
    expect(message.text).toBe('original')
    expect(controller.getState().editingMessage).toBe('')
  })

  it.each([
    ['partner_api_v2', 'whatsapp'],
    ['partner_api_v2', 'telegram'],
    ['user_api_v3', 'whatsapp'],
    ['user_api_v3', 'telegram'],
  ])(
    'edits Wazzup %s %s text through the common editor',
    async (apiMode, platform) => {
      let message = wazzupEditable({
        channel_info: { api_mode: apiMode, platform },
        external_message_id: 'server-only-provider-id',
      })
      let original = structuredClone(message)
      let { controller, call, sync } = harness()

      expect(controller.startEdit(message)).toBe(true)
      controller.setDraft('Updated text')
      expect(await controller.saveEdit(message)).toBe(true)

      expect(call).toHaveBeenCalledExactlyOnceWith(
        'crm_messenger.api.messages.edit_message',
        { message: 'MSG-1', text: 'Updated text' },
      )
      expect(sync).toHaveBeenCalledOnce()
      expect(message).toEqual(original)
      expect(controller.getState().editingMessage).toBe('')
    },
  )

  it.each(['pending', 'unknown'])(
    'blocks edit and delete for durable Wazzup edit state %s despite stale flags',
    async (editState) => {
      let message = wazzupEditable({ edit_state: editState })
      let { controller, call } = harness()

      expect(getMessengerMessageActions(message)).toEqual([])
      expect(canEditMessengerMessage(message)).toBe(false)
      expect(canSaveMessengerMessageEdit(message, 'Updated')).toBe(false)
      expect(canDeleteMessengerMessage(message)).toBe(false)
      expect(controller.startEdit(message)).toBe(false)
      expect(await controller.deleteMessage(message)).toBe(false)
      expect(call).not.toHaveBeenCalled()
    },
  )

  it.each(['pending', 'unknown'])(
    'blocks edit and delete during Wazzup deletion state %s',
    (deleteState) => {
      let message = wazzupEditable({ delete_state: deleteState })
      expect(getMessengerMessageActions(message)).toEqual([])
      expect(canSaveMessengerMessageEdit(message, 'Updated')).toBe(false)
    },
  )

  it('preserves a Wazzup draft and original text on unknown edit without repeating any mutation', async () => {
    let message = wazzupEditable()
    let { controller, call, sync } = harness({
      ok: false,
      reason: 'unknown_result',
      unknown_result: true,
    })
    controller.startEdit(message)
    controller.setDraft('Unsaved desired text')

    expect(await controller.saveEdit(message)).toBe(false)
    expect(controller.getState()).toMatchObject({
      editingMessage: 'MSG-1',
      draft: 'Unsaved desired text',
      blockedEdits: { 'MSG-1': 'unknown' },
      errors: {
        'MSG-1':
          'The message editing result is unknown. Automatic retry is disabled.',
      },
    })
    expect(message.text).toBe('original')
    expect(message.is_edited).toBeUndefined()
    expect(controller.startEdit(message)).toBe(false)
    expect(await controller.saveEdit(message)).toBe(false)
    expect(await controller.deleteMessage(message)).toBe(false)
    expect(call).toHaveBeenCalledOnce()
    expect(sync).toHaveBeenCalledOnce()
    expect(controller.cancelEdit()).toBe(true)
  })

  it.each(['failed', 'succeeded'])(
    'retains the draft and clears a lost-RPC block after canonical edit state %s',
    async (editState) => {
      let message = wazzupEditable()
      let canonical = {
        ...message,
        edit_state: editState,
        text: 'Newer provider text',
      }
      let { controller, call, sync, onError } = harness()
      call.mockRejectedValueOnce(new Error('RPC response lost'))
      sync.mockImplementation(async () =>
        controller.reconcileEditStates([canonical]),
      )
      controller.startEdit(message)
      controller.setDraft('Keep my desired draft')

      expect(await controller.saveEdit(message)).toBe(false)
      expect(controller.getState().blockedEdits).toEqual({})
      expect(controller.getState().errors).toEqual({})
      expect(controller.getState().draft).toBe('Keep my desired draft')
      expect(controller.getState().editingMessage).toBe('MSG-1')
      expect(onError).not.toHaveBeenCalled()
      expect(controller.canEditMessage(canonical)).toBe(true)
      expect(controller.canDeleteMessage(canonical)).toBe(true)
      expect(call).toHaveBeenCalledOnce()

      expect(await controller.saveEdit(canonical)).toBe(true)
      expect(call).toHaveBeenCalledTimes(2)
    },
  )

  it.each([
    ['', true],
    [null, true],
    ['pending', true],
    ['unknown', true],
    ['failed', false],
    ['succeeded', false],
  ])(
    'keeps lost-edit RPC blocked for state=%s, can_edit=%s',
    async (editState, canEdit) => {
      let message = wazzupEditable()
      let { controller, call } = harness()
      call.mockRejectedValueOnce(new Error('RPC response lost'))
      controller.startEdit(message)
      controller.setDraft('Changed')
      expect(await controller.saveEdit(message)).toBe(false)

      let canonical = { ...message, edit_state: editState, can_edit: canEdit }
      controller.reconcileEditStates([canonical])

      expect(controller.getState().blockedEdits['MSG-1']).toBe('unknown')
      expect(controller.canEditMessage(canonical)).toBe(false)
      expect(controller.canDeleteMessage(canonical)).toBe(false)
      expect(await controller.saveEdit(canonical)).toBe(false)
      expect(call).toHaveBeenCalledOnce()
    },
  )

  it('does not invent Wazzup caption editing from stale capability flags', () => {
    expect(
      canEditMessengerMessage(
        wazzupEditable({
          attachments: [{ type: 'image' }],
          can_edit_empty: true,
        }),
      ),
    ).toBe(false)
    expect(
      canEditMessengerMessage(wazzupEditable({ message_type: 'image' })),
    ).toBe(false)
    expect(
      canEditMessengerMessage(
        editable({
          provider: 'vk_direct',
          message_type: 'image',
          attachments: [{ type: 'image' }],
        }),
      ),
    ).toBe(true)
  })

  it('shows edit state notices without adding them to a deletion tombstone', () => {
    expect(getMessengerMessageEditNotice({ edit_state: 'pending' })).toContain(
      'editing is pending',
    )
    expect(getMessengerMessageEditNotice({ edit_state: 'unknown' })).toContain(
      'Automatic retry is disabled',
    )
    expect(getMessengerMessageEditNotice({ edit_state: 'failed' })).toBe('')
    expect(
      getMessengerMessageEditNotice({
        edit_state: 'unknown',
        status: 'deleted',
      }),
    ).toBe('')
  })

  it('edits a photo caption without sending or mutating attachments', async () => {
    let message = editable({
      message_type: 'image',
      can_edit_empty: true,
      attachments: [
        { id: 'ATT-1', type: 'image' },
        { id: 'ATT-2', type: 'image' },
      ],
    })
    let originalAttachments = structuredClone(message.attachments)
    let { controller, call, sync } = harness()

    expect(controller.startEdit(message)).toBe(true)
    controller.setDraft('new photo caption')
    expect(await controller.saveEdit(message)).toBe(true)

    expect(call).toHaveBeenCalledWith(
      'crm_messenger.api.messages.edit_message',
      { message: 'MSG-1', text: 'new photo caption' },
    )
    expect(sync).toHaveBeenCalledOnce()
    expect(message.text).toBe('original')
    expect(message.attachments).toEqual(originalAttachments)
  })

  it('uses backend edit length and empty-caption capabilities for MAX', () => {
    let message = editable({
      provider: 'max_direct',
      message_type: 'video',
      text: 'caption',
      attachments: [{ id: 'ATT-1', type: 'video' }],
      can_edit_empty: true,
      edit_max_length: 4000,
    })

    expect(canSaveMessengerMessageEdit(message, '')).toBe(true)
    expect(canSaveMessengerMessageEdit(message, 'x'.repeat(4000))).toBe(true)
    expect(canSaveMessengerMessageEdit(message, 'x'.repeat(4001))).toBe(false)
  })

  it('removes a photo or file caption but keeps empty text messages blocked', async () => {
    let message = editable({
      message_type: 'image',
      can_edit_empty: true,
      attachments: [
        { id: 'ATT-1', type: 'image' },
        { id: 'ATT-2', attachment_type: 'file' },
      ],
    })
    let { controller, call, sync } = harness()

    expect(canSaveMessengerMessageEdit(message, '')).toBe(true)
    expect(canSaveMessengerMessageEdit(editable(), '')).toBe(false)
    expect(controller.startEdit(message)).toBe(true)
    controller.setDraft('   ')
    expect(await controller.saveEdit(message)).toBe(true)

    expect(call).toHaveBeenCalledWith(
      'crm_messenger.api.messages.edit_message',
      { message: 'MSG-1', text: '' },
    )
    expect(sync).toHaveBeenCalledOnce()
  })

  it('deletes without optimistic mutation and waits for delta', async () => {
    let message = editable()
    let { controller, call, sync } = harness()

    expect(await controller.deleteMessage(message)).toBe(true)

    expect(call).toHaveBeenCalledWith(
      'crm_messenger.api.messages.delete_message',
      { message: 'MSG-1' },
    )
    expect(sync).toHaveBeenCalledOnce()
    expect(message.status).toBe('sent')
  })

  it.each(['whatsapp', 'telegram'])(
    'deletes Wazzup %s through the shared API without exposing provider identity',
    async (platform) => {
      let message = editable({
        provider: 'wazzup',
        platform,
        external_message_id: 'confirmed-provider-id',
      })
      let original = structuredClone(message)
      let { controller, call, sync } = harness()

      expect(await controller.deleteMessage(message)).toBe(true)
      expect(call).toHaveBeenCalledExactlyOnceWith(
        'crm_messenger.api.messages.delete_message',
        { message: 'MSG-1' },
      )
      expect(sync).toHaveBeenCalledOnce()
      expect(message).toEqual(original)
      // A stale message object cannot dispatch a second delete before delta.
      expect(await controller.deleteMessage(message)).toBe(false)
      expect(call).toHaveBeenCalledOnce()
    },
  )

  it.each(['pending', 'unknown', 'deleted'])(
    'blocks a stale delete capability after durable %s state',
    async (deleteState) => {
      let message = editable({
        provider: 'wazzup',
        can_edit: false,
        delete_state: deleteState,
      })
      let { controller, call } = harness()

      expect(canDeleteMessengerMessage(message)).toBe(false)
      expect(getMessengerMessageActions(message)).toEqual([])
      expect(await controller.deleteMessage(message)).toBe(false)
      expect(call).not.toHaveBeenCalled()
    },
  )

  it('keeps an unknown Wazzup deletion visible and never dispatches it again', async () => {
    let message = editable({ provider: 'wazzup' })
    let original = structuredClone(message)
    let { controller, call, sync, onError } = harness({
      ok: false,
      reason: 'unknown_result',
      unknown_result: true,
      message: 'Ambiguous provider result',
    })

    expect(await controller.deleteMessage(message)).toBe(false)
    expect(sync).toHaveBeenCalledOnce()
    expect(controller.getState().blockedDeletes['MSG-1']).toBe('unknown')
    expect(controller.getState().errors['MSG-1']).toBe(
      'The message deletion result is unknown. Automatic retry is disabled.',
    )
    expect(onError).toHaveBeenCalledOnce()
    expect(message).toEqual(original)
    expect(await controller.deleteMessage({ ...message })).toBe(false)
    expect(call).toHaveBeenCalledOnce()
    expect(sync).toHaveBeenCalledOnce()
  })

  it('blocks a lost Wazzup RPC response even when the read-only refresh fails', async () => {
    let message = editable({ provider: 'wazzup' })
    let { controller, call, sync } = harness()
    call.mockRejectedValue(new Error('Network request failed'))
    sync.mockRejectedValue(new Error('Refresh failed'))

    expect(await controller.deleteMessage(message)).toBe(false)
    expect(controller.getState().errors['MSG-1']).toContain(
      'deletion result is unknown',
    )
    expect(controller.canDeleteMessage(message)).toBe(false)
    expect(await controller.deleteMessage(message)).toBe(false)
    expect(call).toHaveBeenCalledOnce()
    expect(sync).toHaveBeenCalledOnce()
    expect(message.status).toBe('sent')
    expect(message.text).toBe('original')
  })

  it('keeps definite Wazzup delete rejections actionable without automatic retry', async () => {
    let message = editable({ provider: 'wazzup' })
    let { controller, call, sync } = harness({
      ok: false,
      reason: 'delete_expired',
      message: 'The provider no longer allows this message to be deleted.',
    })

    expect(await controller.deleteMessage(message)).toBe(false)
    expect(controller.getState().blockedDeletes).toEqual({})
    expect(controller.canDeleteMessage(message)).toBe(true)
    expect(controller.getState().errors['MSG-1']).toContain('no longer allows')
    expect(call).toHaveBeenCalledOnce()
    expect(sync).not.toHaveBeenCalled()
  })

  it('allows an explicit delete after a lost RPC response resolves to a definite rejection', async () => {
    let message = editable({ provider: 'wazzup' })
    let canonical = { ...message, delete_state: 'failed', can_delete: true }
    let { controller, call, sync, onError } = harness()
    call.mockRejectedValueOnce(new Error('RPC response lost'))
    sync.mockImplementation(async () => {
      controller.reconcileDeleteStates([canonical])
    })

    expect(await controller.deleteMessage(message)).toBe(false)
    expect(controller.getState().blockedDeletes).toEqual({})
    expect(controller.getState().errors).toEqual({})
    expect(controller.canDeleteMessage(canonical)).toBe(true)
    expect(onError).not.toHaveBeenCalled()
    expect(call).toHaveBeenCalledOnce()

    expect(await controller.deleteMessage(canonical)).toBe(true)
    expect(call).toHaveBeenCalledTimes(2)
  })

  it.each([
    ['', true],
    [null, true],
    ['pending', true],
    ['unknown', true],
    ['failed', false],
  ])(
    'retains a lost-response block for canonical delete_state=%s and can_delete=%s',
    async (deleteState, canDelete) => {
      let message = editable({ provider: 'wazzup' })
      let { controller, call } = harness()
      call.mockRejectedValueOnce(new Error('RPC response lost'))
      expect(await controller.deleteMessage(message)).toBe(false)

      let canonical = {
        ...message,
        delete_state: deleteState,
        can_delete: canDelete,
      }
      controller.reconcileDeleteStates([canonical])

      expect(controller.getState().blockedDeletes['MSG-1']).toBe('unknown')
      expect(controller.canDeleteMessage(canonical)).toBe(false)
      expect(await controller.deleteMessage(canonical)).toBe(false)
      expect(call).toHaveBeenCalledOnce()
    },
  )

  it('keeps a confirmed deletion blocked even if an older failed row is refreshed', async () => {
    let message = editable({ provider: 'wazzup' })
    let { controller, call } = harness()
    expect(await controller.deleteMessage(message)).toBe(true)

    controller.reconcileDeleteStates([
      { ...message, delete_state: 'failed', can_delete: true },
    ])

    expect(controller.getState().blockedDeletes['MSG-1']).toBe('deleted')
    expect(controller.canDeleteMessage(message)).toBe(false)
    expect(call).toHaveBeenCalledOnce()
  })

  it('hides a locally blocked delete in the shared menu while keeping reply', () => {
    expect(
      getMessengerMessageActions(
        editable({ provider: 'wazzup', can_edit: false, can_reply: true }),
        { deleteBlocked: true },
      ),
    ).toEqual(['reply'])
  })

  it('uses persistent deletion notices without rendering one on a tombstone', () => {
    expect(
      getMessengerMessageDeleteNotice({ delete_state: 'pending' }),
    ).toContain('pending')
    expect(
      getMessengerMessageDeleteNotice({ delete_state: 'unknown' }),
    ).toContain('Automatic retry is disabled')
    expect(getMessengerMessageDeleteNotice({ delete_state: 'failed' })).toBe('')
    expect(
      getMessengerMessageDeleteNotice({
        status: 'deleted',
        delete_state: 'unknown',
      }),
    ).toBe('')
  })

  it.each([
    ['edit_expired', 'VK code 909'],
    ['edit_not_allowed', 'VK code 920'],
    ['delete_for_all_not_allowed', 'VK code 924'],
    ['action_in_progress', 'Action in progress'],
    ['timeout', 'Result may be unknown'],
  ])('keeps provider error %s on the message', async (reason, messageText) => {
    let message = editable()
    let { controller, sync, onError } = harness({
      ok: false,
      reason,
      message: messageText,
      unknown_result: reason === 'timeout',
    })
    controller.startEdit(message)
    controller.setDraft('edited')

    expect(await controller.saveEdit(message)).toBe(false)

    expect(controller.getState().editingMessage).toBe('MSG-1')
    expect(controller.getState().errors['MSG-1']).toBe(messageText)
    expect(sync).not.toHaveBeenCalled()
    expect(onError).toHaveBeenCalledWith(messageText, expect.any(Error))
    expect(message.text).toBe('original')
  })

  it('supports cancel and blocks messages without backend eligibility', () => {
    let { controller, call } = harness()
    expect(controller.startEdit(editable({ can_edit: false }))).toBe(false)
    expect(
      controller.startEdit(editable({ name: 'MSG-2', can_delete: false })),
    ).toBe(true)
    controller.setDraft('draft')
    expect(controller.cancelEdit()).toBe(true)
    expect(controller.getState().editingMessage).toBe('')
    expect(call).not.toHaveBeenCalled()
  })

  it('reveals the editor ref instead of the full media bubble and focuses textarea', async () => {
    let events = []
    let textarea = {
      focus: vi.fn(() => events.push('focus')),
    }
    let editor = {
      getBoundingClientRect: () => ({ top: 420, bottom: 580 }),
      querySelector: (selector) => (selector === 'textarea' ? textarea : null),
    }
    let scrollContainer = {
      scrollTop: 100,
      scrollHeight: 2400,
      getBoundingClientRect: () => ({ top: 100, bottom: 500 }),
    }

    let opened = await openMessengerMessageEditor(editable(), {
      startEdit: () => {
        events.push('startEdit')
        return true
      },
      nextTick: async () => events.push('nextTick'),
      scrollContainer: () => scrollContainer,
      getEditorElement: () => {
        events.push('getEditorElement')
        return editor
      },
    })

    expect(opened).toBe(true)
    expect(events).toEqual([
      'startEdit',
      'nextTick',
      'getEditorElement',
      'focus',
    ])
    expect(scrollContainer.scrollTop).toBe(196)
    expect(scrollContainer.scrollTop).not.toBe(scrollContainer.scrollHeight)
    expect(textarea.focus).toHaveBeenCalledWith({ preventScroll: true })
  })

  it('does not move the chat when the whole editor is already visible', () => {
    let scrollContainer = {
      scrollTop: 240,
      scrollHeight: 2000,
      getBoundingClientRect: () => ({ top: 100, bottom: 600 }),
    }
    let editor = {
      getBoundingClientRect: () => ({ top: 180, bottom: 520 }),
    }
    let textarea = { focus: vi.fn() }

    expect(revealMessengerEditor(scrollContainer, editor, textarea)).toBe(false)
    expect(scrollContainer.scrollTop).toBe(240)
    expect(scrollContainer.scrollTop).not.toBe(scrollContainer.scrollHeight)
    expect(textarea.focus).toHaveBeenCalledWith({ preventScroll: true })
  })

  it('scrolls upward by only the hidden part for an editor in history', () => {
    let scrollContainer = {
      scrollTop: 500,
      getBoundingClientRect: () => ({ top: 100, bottom: 600 }),
    }
    let editor = {
      getBoundingClientRect: () => ({ top: 40, bottom: 260 }),
    }

    expect(revealMessengerEditor(scrollContainer, editor)).toBe(true)
    expect(scrollContainer.scrollTop).toBe(424)
  })
})
