import {
  createMessengerMessageActions,
  getMessengerMessageActions,
  getMessengerMessageDisplay,
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
  ...overrides,
})

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

  it('edits a photo caption without sending or mutating attachments', async () => {
    let message = editable({
      message_type: 'image',
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
