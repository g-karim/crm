import {
  canDeleteMessengerMessage,
  canRetryDeleteMessengerMessage,
  createMessengerMessageActions,
  getMessengerDeleteRetryConfirmation,
  getMessengerMessageActions,
  getMessengerMessageDeleteNotice,
  makeMessengerDeleteRetryRequestId,
} from '@/utils/messengerMessageActions'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it, vi } from 'vitest'

const message = (overrides = {}) => ({
  name: 'MSG-1',
  conversation: 'CONV-1',
  channel: 'CHANNEL-1',
  provider: 'wazzup',
  channel_info: { wazzup_api_mode: 'partner_api_v2' },
  external_message_id: 'PROVIDER-MESSAGE-1',
  external_chat_id: 'PROVIDER-CHAT-1',
  message_type: 'text',
  status: 'sent',
  delete_state: 'unknown',
  modified: '2026-10-25 13:51:00.000000',
  can_reply: true,
  can_edit: false,
  can_delete: false,
  can_retry_delete: true,
  delete_retry_requires_confirmation: true,
  delete_retry_after_seconds: 0,
  delete_retry_attempts_remaining: 3,
  ...overrides,
})

function harness(initial = message()) {
  let current = initial
  let now = 1000
  let call = vi.fn(async () => ({ ok: true }))
  let sync = vi.fn(async () => {})
  let controller = createMessengerMessageActions({
    call,
    sync,
    now: () => now,
    getMessage: () => current,
  })
  controller.reconcileDeleteStates([initial])
  return {
    controller,
    call,
    sync,
    current: () => current,
    receive(fresh) {
      current = fresh
      controller.reconcileDeleteStates([fresh])
    },
    advance(ms) {
      now += ms
    },
  }
}

const source = readFileSync(
  resolve(process.cwd(), 'src/components/LeadMessenger/LeadConversation.vue'),
  'utf8',
)
const contentSource = readFileSync(
  resolve(process.cwd(), 'src/components/LeadMessenger/MessageContent.vue'),
  'utf8',
)
const metadataSource = readFileSync(
  resolve(process.cwd(), 'src/components/LeadMessenger/MessageMetadata.vue'),
  'utf8',
)
const ru = readFileSync(resolve(process.cwd(), '../crm/locale/ru.po'), 'utf8')

function handler(bindings, name = 'confirmRetryDeleteMessage') {
  let code = source.match(new RegExp(`^function ${name}\\([^]*?^\\}`, 'm'))[0]
  return new Function(...Object.keys(bindings), `return (${code})`)(
    ...Object.values(bindings),
  )
}

function dialogHarness(initial = message()) {
  let h = harness(initial)
  let currentContext = true
  let values = {
    __: (text, args) => (args ? text.replace('{0}', args[0]) : text),
    permissions: { value: { can_operate: true } },
    messageActions: h.controller,
    messageSync: { getMessages: () => [h.current()] },
    messageActionState: {
      get value() {
        return h.controller.getState()
      },
    },
    captureLeadContext: () => ({ isCurrent: () => currentContext }),
    selectedConversation: { value: { name: 'CONV-1' } },
    selectedChannel: { value: 'CHANNEL-1' },
    getMessengerDeleteRetryConfirmation,
    $dialog: vi.fn(),
  }
  return {
    ...h,
    values,
    open: handler(values),
    expire: () => (currentContext = false),
  }
}

describe('explicit Partner deletion retries', () => {
  it.each(['unknown', 'failed'])(
    'shows a retry for server-eligible %s, with reply retained',
    (deleteState) => {
      let row = message({ delete_state: deleteState })
      expect(getMessengerMessageActions(row)).toEqual(['reply', 'retry_delete'])
      expect(canDeleteMessengerMessage({ ...row, can_delete: true })).toBe(
        false,
      )
    },
  )

  it.each([
    { delete_state: 'pending' },
    { status: 'deleted' },
    { edit_state: 'pending' },
    { edit_state: 'unknown' },
    { can_retry_delete: false },
    { delete_retry_attempts_remaining: 0 },
    { modified: '' },
    { channel_info: { wazzup_api_mode: 'user_api_v3' } },
    { provider: 'vk_direct' },
  ])('fails closed for ineligible state %j', async (overrides) => {
    let row = message(overrides)
    let h = harness(row)
    expect(canRetryDeleteMessengerMessage(row)).toBe(false)
    expect(await h.controller.retryDeleteMessage(row, true)).toBe(false)
    expect(h.call).not.toHaveBeenCalled()
  })

  it('requires explicit confirmation and sends the precise UUID/CAS DELETE contract once', async () => {
    let h = harness()
    expect(await h.controller.retryDeleteMessage(h.current())).toBe(false)
    expect(h.call).not.toHaveBeenCalled()
    expect(await h.controller.retryDeleteMessage(h.current(), true)).toBe(true)
    expect(h.call).toHaveBeenCalledExactlyOnceWith(
      'crm_messenger.api.messages.delete_message',
      {
        message: 'MSG-1',
        confirm_unknown_delete: 1,
        delete_retry_request_id: expect.stringMatching(
          /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
        ),
        expected_modified: h.current().modified,
      },
    )
    expect(h.sync).toHaveBeenCalledOnce()
  })

  it('uses UUID/CAS for a confirmed failed attempt without claiming an unknown result', async () => {
    let row = message({
      delete_state: 'failed',
      delete_retry_requires_confirmation: false,
    })
    let h = harness(row)
    expect(await h.controller.retryDeleteMessage(row, true)).toBe(true)
    expect(h.call.mock.calls[0][1].confirm_unknown_delete).toBe(0)
    expect(h.call.mock.calls[0][1].expected_modified).toBe(row.modified)
  })

  it('refreshes an initial definite Partner failure into the explicit retry action without another DELETE', async () => {
    let initial = message({
      delete_state: '',
      can_delete: true,
      can_retry_delete: false,
    })
    let h = harness(initial)
    h.call.mockResolvedValueOnce({
      ok: false,
      reason: 'delete_not_allowed',
      message: 'Deletion rejected',
    })
    h.sync.mockImplementationOnce(async () =>
      h.receive(
        message({
          delete_state: 'failed',
          delete_retry_requires_confirmation: false,
          delete_retry_after_seconds: 30,
          modified: '2026-10-25 13:51:02.000000',
        }),
      ),
    )

    expect(await h.controller.deleteMessage(initial)).toBe(false)
    expect(h.call).toHaveBeenCalledExactlyOnceWith(
      'crm_messenger.api.messages.delete_message',
      { message: 'MSG-1' },
    )
    expect(h.sync).toHaveBeenCalledOnce()
    expect(h.controller.canDeleteMessage(h.current())).toBe(false)
    expect(getMessengerMessageActions(h.current())).toEqual([
      'reply',
      'retry_delete',
    ])
    expect(h.controller.getDeleteRetryAfterSeconds(h.current())).toBe(30)
  })

  it('does not send another DELETE on double click', async () => {
    let h = harness()
    let resolve
    h.call.mockImplementationOnce(() => new Promise((done) => (resolve = done)))
    let first = h.controller.retryDeleteMessage(h.current(), true)
    expect(await h.controller.retryDeleteMessage(h.current(), true)).toBe(false)
    expect(h.call).toHaveBeenCalledOnce()
    resolve({ ok: true })
    expect(await first).toBe(true)
  })

  it('closes the initial deletion dialog after a fresh definite failure exposes only the retry flow', async () => {
    let initial = message({
      delete_state: '',
      can_delete: true,
      can_retry_delete: false,
    })
    let h = dialogHarness(initial)
    h.call.mockResolvedValueOnce({ ok: false, reason: 'delete_not_allowed' })
    h.sync.mockImplementationOnce(async () =>
      h.receive(message({ delete_state: 'failed' })),
    )
    handler(h.values, 'confirmDeleteMessage')(initial)
    let close = vi.fn()

    await h.values.$dialog.mock.calls[0][0].actions[0].onClick(close)

    expect(close).toHaveBeenCalledOnce()
    expect(h.call).toHaveBeenCalledOnce()
    expect(h.controller.canDeleteMessage(h.current())).toBe(false)
    expect(h.controller.canRetryDeleteMessage(h.current())).toBe(true)
  })

  it.each([
    'modified',
    'conversation',
    'channel',
    'external_message_id',
    'external_chat_id',
  ])('does not dispatch a retry after canonical %s changes', async (field) => {
    let h = harness()
    let original = h.current()
    h.receive(message({ [field]: 'CHANGED' }))
    expect(await h.controller.retryDeleteMessage(original, true)).toBe(false)
    expect(h.call).not.toHaveBeenCalled()
  })

  it('recovers a local lost-RPC block only from a fresh eligible DTO and never retries automatically', async () => {
    let h = harness()
    h.call.mockRejectedValueOnce(new Error('RPC lost'))
    h.sync.mockRejectedValueOnce(new Error('refresh lost'))
    expect(await h.controller.retryDeleteMessage(h.current(), true)).toBe(false)
    expect(h.controller.getState().blockedDeletes['MSG-1']).toBe('unknown')
    expect(await h.controller.retryDeleteMessage(h.current(), true)).toBe(false)
    expect(h.call).toHaveBeenCalledOnce()

    h.receive(message())
    expect(h.controller.getState().blockedDeletes['MSG-1']).toBeUndefined()
    expect(h.controller.canRetryDeleteMessage(h.current())).toBe(true)
    expect(h.controller.canDeleteMessage(h.current())).toBe(false)
    expect(h.call).toHaveBeenCalledOnce()
    h.call.mockResolvedValueOnce({ ok: true })
    expect(await h.controller.retryDeleteMessage(h.current(), true)).toBe(true)
    expect(h.call.mock.calls[0][1].delete_retry_request_id).not.toBe(
      h.call.mock.calls[1][1].delete_retry_request_id,
    )
  })

  it('shows cooldown in the dialog, advances only local time and sends nothing automatically', async () => {
    let h = dialogHarness(message({ delete_retry_after_seconds: 30 }))
    expect(getMessengerMessageActions(h.current())).toContain('retry_delete')
    h.open(h.current())
    expect(h.values.$dialog.mock.calls[0][0].message).toContain('30 seconds')
    expect(h.values.$dialog.mock.calls[0][0].actions).toEqual([])
    expect(await h.controller.retryDeleteMessage(h.current(), true)).toBe(false)
    h.advance(30000)
    expect(h.call).not.toHaveBeenCalled()
    h.open(h.current())
    let dialog = h.values.$dialog.mock.calls[1][0]
    expect(dialog.message).toContain(
      'previous attempt may already have deleted',
    )
    expect(h.call).not.toHaveBeenCalled()
    await dialog.actions[0].onClick(vi.fn())
    expect(h.call).toHaveBeenCalledOnce()
  })

  it.each(['route', 'permission', 'selection'])(
    'discards an already-open risk confirmation after %s changes',
    async (change) => {
      let h = dialogHarness()
      h.open(h.current())
      expect(h.call).not.toHaveBeenCalled()
      if (change === 'route') h.expire()
      else if (change === 'permission')
        h.values.permissions.value.can_operate = false
      else h.values.selectedConversation.value.name = 'OTHER'
      let close = vi.fn()
      await h.values.$dialog.mock.calls[0][0].actions[0].onClick(close)
      expect(h.call).not.toHaveBeenCalled()
      expect(close).toHaveBeenCalledOnce()
    },
  )

  it('keeps Partner unknown bubble short and removes its inline checking flow', () => {
    expect(getMessengerMessageDeleteNotice(message())).toBe(
      'Could not confirm deletion',
    )
    expect(
      getMessengerMessageDeleteNotice(message({ delete_state: '' }), true),
    ).toBe('Could not confirm deletion')
    expect(
      getMessengerMessageDeleteNotice(message({ status: 'deleted' })),
    ).toBe('')
    expect(contentSource).not.toContain('Check confirmation in CRM')
    expect(contentSource).not.toContain('check-delete-confirmation')
    expect(contentSource).not.toContain('confirmationNotice')
    expect(metadataSource).toContain("label: __('Retry Deletion')")
    expect(ru).toContain(
      'msgid "Could not confirm deletion"\nmsgstr "Не удалось подтвердить удаление"',
    )
    expect(ru).toContain('msgid "Retry Deletion"\nmsgstr "Повторить удаление"')
  })

  it('leaves Legacy/other provider notices and outbound retry policy unchanged', () => {
    let legacy = message({ channel_info: { wazzup_api_mode: 'user_api_v3' } })
    expect(getMessengerMessageDeleteNotice(legacy)).toContain(
      'Automatic retry is disabled',
    )
    expect(getMessengerMessageActions(legacy)).toEqual(['reply'])
    expect(
      getMessengerMessageActions(
        message({ can_retry: true, status: 'unknown' }),
      ),
    ).not.toContain('retry')
    expect(
      getMessengerMessageActions(
        message({ can_edit: true, edit_state: 'unknown' }),
      ),
    ).toEqual(['reply'])
  })

  it('generates canonical random UUID4 identifiers', () => {
    let first = makeMessengerDeleteRetryRequestId()
    expect(first).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    )
    expect(makeMessengerDeleteRetryRequestId()).not.toBe(first)
  })
})
