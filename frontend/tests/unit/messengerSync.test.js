import {
  createMessengerSyncController,
  mergeMessengerMessages,
} from '@/utils/messengerSync'
import { describe, expect, it, vi } from 'vitest'

class SocketMock {
  handlers = new Map()
  emitted = []

  on(event, handler) {
    let handlers = this.handlers.get(event) || []
    handlers.push(handler)
    this.handlers.set(event, handlers)
  }

  off(event, handler) {
    this.handlers.set(
      event,
      (this.handlers.get(event) || []).filter((item) => item !== handler),
    )
  }

  emit(event, ...args) {
    if (event === 'doc_subscribe' || event === 'doc_unsubscribe') {
      this.emitted.push([event, ...args])
      return
    }
    ;(this.handlers.get(event) || []).forEach((handler) => handler(...args))
  }
}

function createHarness(responses = {}) {
  let socket = new SocketMock()
  let visibility = new EventTarget()
  visibility.visibilityState = 'visible'
  let changes = []
  let calls = []
  let call = vi.fn(async (method, params) => {
    calls.push([method, params])
    let key = method.split('.').pop()
    let response = responses[key]
    return typeof response === 'function' ? response(params, calls) : response
  })
  let controller = createMessengerSyncController({
    socket,
    call,
    visibilityTarget: visibility,
    onChange: (change) => changes.push(change),
  })
  return { controller, socket, visibility, changes, calls }
}

const snapshot = (messages = [], overrides = {}) => ({
  contract_version: 1,
  messages,
  page: { has_more: false, before_cursor: null },
  sync_cursor: 'cursor-1',
  ...overrides,
})

const delta = (changes = [], overrides = {}) => ({
  contract_version: 1,
  changes,
  next_cursor: 'cursor-2',
  has_more: false,
  ...overrides,
})

describe('messenger sync', () => {
  it('loads the initial snapshot for the current CRM Lead', async () => {
    let message = { name: 'M-1', message_datetime: '2026-07-16 10:00:00' }
    let harness = createHarness({ get_message_page: snapshot([message]) })

    await harness.controller.start('LEAD-1')

    expect(harness.controller.getMessages()).toEqual([message])
    expect(harness.calls[0]).toEqual([
      'crm_messenger.api.messages.get_message_page',
      {
        reference_doctype: 'CRM Lead',
        reference_name: 'LEAD-1',
        limit: 100,
      },
    ])
  })

  it('subscribes and unsubscribes with the component lifecycle', async () => {
    let harness = createHarness({ get_message_page: snapshot() })
    await harness.controller.start('LEAD-1')
    harness.controller.stop()

    expect(harness.socket.emitted).toEqual([
      ['doc_subscribe', 'CRM Lead', 'LEAD-1'],
      ['doc_unsubscribe', 'CRM Lead', 'LEAD-1'],
    ])
    expect(
      harness.socket.handlers.get('crm_messenger:conversation_changed'),
    ).toEqual([])
  })

  it('merges delta changes by message name without duplicates', async () => {
    let first = { name: 'M-1', status: 'sent', message_datetime: '2026-07-16 10:00:00' }
    let changed = { ...first, status: 'read' }
    let harness = createHarness({
      get_message_page: snapshot([first]),
      get_message_changes: delta([changed]),
    })
    await harness.controller.start('LEAD-1')

    harness.socket.emit('crm_messenger:conversation_changed', {
      version: 1,
      reference_doctype: 'CRM Lead',
      reference_name: 'LEAD-1',
      conversation: 'CONV-1',
    })
    await vi.waitFor(() => {
      expect(harness.controller.getMessages()[0].status).toBe('read')
    })
    expect(harness.controller.getMessages()).toHaveLength(1)
  })

  it('coalesces a repeated realtime event and remains idempotent', async () => {
    let resolveDelta
    let changesCall = new Promise((resolve) => (resolveDelta = resolve))
    let harness = createHarness({
      get_message_page: snapshot(),
      get_message_changes: vi
        .fn()
        .mockImplementationOnce(() => changesCall)
        .mockImplementation(() => delta()),
    })
    await harness.controller.start('LEAD-1')
    let event = {
      version: 1,
      reference_doctype: 'CRM Lead',
      reference_name: 'LEAD-1',
    }
    harness.socket.emit('crm_messenger:conversation_changed', event)
    harness.socket.emit('crm_messenger:conversation_changed', event)
    resolveDelta(delta([{ name: 'M-1', message_datetime: '2026-07-16 10:00:00' }]))

    await vi.waitFor(() => expect(harness.controller.getMessages()).toHaveLength(1))
    expect(harness.controller.getMessages().map((item) => item.name)).toEqual([
      'M-1',
    ])
  })

  it('deduplicates the same message in snapshot and delta', async () => {
    let message = { name: 'M-1', text: 'snapshot', message_datetime: '2026-07-16 10:00:00' }
    let harness = createHarness({
      get_message_page: snapshot([message]),
      get_message_changes: delta([{ ...message, text: 'delta' }]),
    })
    await harness.controller.start('LEAD-1')
    await harness.controller.syncDelta()

    expect(harness.controller.getMessages()).toEqual([
      { ...message, text: 'delta' },
    ])
  })

  it('resubscribes and requests delta after reconnect', async () => {
    let harness = createHarness({
      get_message_page: snapshot(),
      get_message_changes: delta(),
    })
    await harness.controller.start('LEAD-1')
    harness.socket.emit('connect')

    await vi.waitFor(() =>
      expect(
        harness.calls.filter(([method]) => method.endsWith('get_message_changes')),
      ).toHaveLength(1),
    )
    expect(harness.socket.emitted.at(-1)).toEqual([
      'doc_subscribe',
      'CRM Lead',
      'LEAD-1',
    ])
  })

  it('unsubscribes from the old Lead and ignores its events after a switch', async () => {
    let harness = createHarness({
      get_message_page: ({ reference_name }) =>
        snapshot([{ name: `${reference_name}-M`, message_datetime: '2026-07-16 10:00:00' }]),
      get_message_changes: delta(),
    })
    await harness.controller.start('LEAD-1')
    await harness.controller.setLead('LEAD-2')
    harness.socket.emit('crm_messenger:conversation_changed', {
      version: 1,
      reference_doctype: 'CRM Lead',
      reference_name: 'LEAD-1',
    })

    expect(harness.socket.emitted.slice(-2)).toEqual([
      ['doc_unsubscribe', 'CRM Lead', 'LEAD-1'],
      ['doc_subscribe', 'CRM Lead', 'LEAD-2'],
    ])
    expect(harness.controller.getMessages()[0].name).toBe('LEAD-2-M')
  })

  it('requests delta when the browser tab becomes visible', async () => {
    let harness = createHarness({
      get_message_page: snapshot(),
      get_message_changes: delta(),
    })
    await harness.controller.start('LEAD-1')
    harness.visibility.dispatchEvent(new Event('visibilitychange'))

    await vi.waitFor(() =>
      expect(
        harness.calls.filter(([method]) => method.endsWith('get_message_changes')),
      ).toHaveLength(1),
    )
  })

  it('updates an old status and attachment from delta', () => {
    let message = {
      name: 'M-1',
      status: 'sent',
      attachments: [{ id: 'A-1', status: 'pending' }],
    }
    let result = mergeMessengerMessages([message], [
      {
        ...message,
        status: 'read',
        attachments: [{ id: 'A-1', status: 'available' }],
      },
    ])

    expect(result.messages[0].status).toBe('read')
    expect(result.messages[0].attachments[0].status).toBe('available')
    expect(result.messages).toHaveLength(1)
  })

  it('replaces one attachment with a complete five-photo delta', () => {
    let message = {
      name: 'M-PHOTOS',
      attachments: [{ id: 'A-1', type: 'image' }],
    }
    let attachments = Array.from({ length: 5 }, (_, index) => ({
      id: `A-${index + 1}`,
      type: 'image',
    }))

    let result = mergeMessengerMessages([message], [{ ...message, attachments }])

    expect(result.messages).toHaveLength(1)
    expect(result.messages[0].attachments).toEqual(attachments)
    expect(result.updated).toEqual(['M-PHOTOS'])
  })
})
