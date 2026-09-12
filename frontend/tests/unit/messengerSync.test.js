import {
  countNewMessengerMessages,
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
  let permissions = []
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
    onPermissions: (value) => permissions.push(value),
  })
  return { controller, socket, visibility, changes, permissions, calls }
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
  it('merges an exact unloaded reply target through the shared ordering path', () => {
    let harness = createHarness()
    let older = {
      name: 'M-1',
      message_datetime: '2026-07-16 09:00:00',
    }
    let newer = {
      name: 'M-2',
      message_datetime: '2026-07-16 10:00:00',
    }

    harness.controller.mergeExternal(newer)
    harness.controller.mergeExternal(older)

    expect(harness.controller.getMessages()).toEqual([older, newer])
  })
  it('counts only appended inbound non-history inserts as new messages', () => {
    let previous = {
      name: 'M-1',
      message_datetime: '2026-07-16 10:00:00',
      creation: '2026-07-16 10:00:01',
    }
    let messages = [
      {
        name: 'OLD-HISTORY',
        direction: 'inbound',
        ingest_source: 'provider_history',
        message_datetime: '2026-07-15 10:00:00',
      },
      previous,
      {
        name: 'OUTBOUND',
        direction: 'outbound',
        message_datetime: '2026-07-16 10:01:00',
      },
      {
        name: 'DELETED',
        direction: 'inbound',
        status: 'deleted',
        message_datetime: '2026-07-16 10:02:00',
      },
      {
        name: 'NEW-INBOUND',
        direction: 'inbound',
        ingest_source: 'provider_webhook',
        conversation: 'OTHER-CHANNEL-SAME-LEAD',
        message_datetime: '2026-07-16 10:03:00',
      },
    ]

    expect(
      countNewMessengerMessages({
        messages,
        inserted: ['OLD-HISTORY', 'OUTBOUND', 'DELETED', 'NEW-INBOUND'],
        previousLastMessage: previous,
      }),
    ).toBe(1)
  })

  it('does not count an inserted provider message sorted before the old tail', () => {
    let previous = {
      name: 'M-2',
      message_datetime: '2026-07-16 10:00:00',
    }
    expect(
      countNewMessengerMessages({
        messages: [
          {
            name: 'LATE-DELIVERY',
            direction: 'inbound',
            ingest_source: 'provider_webhook',
            message_datetime: '2026-07-16 09:59:00',
          },
          previous,
        ],
        inserted: ['LATE-DELIVERY'],
        previousLastMessage: previous,
      }),
    ).toBe(0)
  })
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

  it('propagates permission loss from a delta response', async () => {
    let operator = {
      can_read: true,
      can_operate: true,
      can_administer: false,
    }
    let readOnly = { ...operator, can_operate: false }
    let harness = createHarness({
      get_message_page: snapshot([], { permissions: operator }),
      get_message_changes: delta([], { permissions: readOnly }),
    })

    await harness.controller.start('LEAD-1')
    await harness.controller.syncDelta()

    expect(harness.permissions).toEqual([operator, readOnly])
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
    expect(harness.socket.handlers.get('crm_messenger:typing')).toEqual([])
  })

  it('routes only typing events for the active Lead', async () => {
    let typing = []
    let harness = createHarness({ get_message_page: snapshot() })
    harness.controller.stop()
    harness.controller = createMessengerSyncController({
      socket: harness.socket,
      call: vi.fn(async () => snapshot()),
      visibilityTarget: harness.visibility,
      onTyping: (payload) => typing.push(payload),
    })
    await harness.controller.start('LEAD-1')
    harness.socket.emit('crm_messenger:typing', {
      version: 1,
      reference_doctype: 'CRM Lead',
      reference_name: 'LEAD-2',
      conversation: 'CONV-2',
    })
    harness.socket.emit('crm_messenger:typing', {
      version: 1,
      reference_doctype: 'CRM Lead',
      reference_name: 'LEAD-1',
      conversation: 'CONV-1',
      active: true,
      expires_in_ms: 6000,
    })
    expect(typing).toHaveLength(1)
    expect(typing[0].conversation).toBe('CONV-1')
  })

  it('merges delta changes by message name without duplicates', async () => {
    let first = {
      name: 'M-1',
      status: 'sent',
      message_datetime: '2026-07-16 10:00:00',
    }
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

  it('notifies the conversation layer about lifecycle realtime changes', async () => {
    let stateChanges = []
    let harness = createHarness({
      get_message_page: snapshot(),
      get_message_changes: delta(),
    })
    harness.controller.stop()
    harness.controller = createMessengerSyncController({
      socket: harness.socket,
      call: vi.fn(async (method) =>
        method.endsWith('get_message_page') ? snapshot() : delta(),
      ),
      visibilityTarget: harness.visibility,
      onConversationStateChanged: (payload) => stateChanges.push(payload),
    })
    await harness.controller.start('LEAD-1')

    harness.socket.emit('crm_messenger:conversation_changed', {
      version: 1,
      reference_doctype: 'CRM Lead',
      reference_name: 'LEAD-1',
      conversation: 'CONV-1',
      conversation_state_changed: true,
    })

    expect(stateChanges).toHaveLength(1)
    expect(stateChanges[0].conversation).toBe('CONV-1')
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
    resolveDelta(
      delta([{ name: 'M-1', message_datetime: '2026-07-16 10:00:00' }]),
    )

    await vi.waitFor(() =>
      expect(harness.controller.getMessages()).toHaveLength(1),
    )
    expect(harness.controller.getMessages().map((item) => item.name)).toEqual([
      'M-1',
    ])
  })

  it('deduplicates the same message in snapshot and delta', async () => {
    let message = {
      name: 'M-1',
      text: 'snapshot',
      message_datetime: '2026-07-16 10:00:00',
    }
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
        harness.calls.filter(([method]) =>
          method.endsWith('get_message_changes'),
        ),
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
        snapshot([
          {
            name: `${reference_name}-M`,
            message_datetime: '2026-07-16 10:00:00',
          },
        ]),
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
        harness.calls.filter(([method]) =>
          method.endsWith('get_message_changes'),
        ),
      ).toHaveLength(1),
    )
  })

  it('updates an old status and attachment from delta', () => {
    let message = {
      name: 'M-1',
      status: 'sent',
      attachments: [{ id: 'A-1', status: 'pending' }],
    }
    let result = mergeMessengerMessages(
      [message],
      [
        {
          ...message,
          status: 'read',
          attachments: [{ id: 'A-1', status: 'available' }],
        },
      ],
    )

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

    let result = mergeMessengerMessages(
      [message],
      [{ ...message, attachments }],
    )

    expect(result.messages).toHaveLength(1)
    expect(result.messages[0].attachments).toEqual(attachments)
    expect(result.updated).toEqual(['M-PHOTOS'])
  })

  it('accepts an equal server version but keeps versioned data over unversioned data', () => {
    let current = {
      name: 'M-1',
      text: 'Current',
      modified: '2026-07-16 10:00:00',
    }
    let equal = mergeMessengerMessages(
      [current],
      [{ ...current, text: 'Complete server row' }],
    )
    let unversioned = mergeMessengerMessages(equal.messages, [
      { name: 'M-1', text: 'Stale unversioned row' },
    ])

    expect(equal.messages[0].text).toBe('Complete server row')
    expect(equal.updated).toEqual(['M-1'])
    expect(unversioned.messages[0].text).toBe('Complete server row')
    expect(unversioned.updated).toEqual([])
  })

  it('keeps a newer version when delayed history returns an older message', async () => {
    let resolveHistory
    let message = (text, modified, status = 'received') => ({
      name: 'M-1',
      text,
      status,
      modified,
      message_datetime: '2026-07-16 10:00:00',
      creation: '2026-07-16 10:00:01',
    })
    let harness = createHarness({
      get_message_page: (params) =>
        params.before_cursor
          ? new Promise((resolve) => (resolveHistory = resolve))
          : snapshot([], {
              page: { has_more: true, before_cursor: 'history-1' },
            }),
      get_message_changes: delta([
        message('Message deleted', '2026-07-16 10:02:00', 'deleted'),
      ]),
    })
    await harness.controller.start('LEAD-1')

    let history = harness.controller.loadOlder()
    await harness.controller.syncDelta()
    resolveHistory({
      contract_version: 1,
      messages: [message('Old text', '2026-07-16 10:01:00')],
      page: { has_more: false, before_cursor: null },
    })
    await history

    expect(harness.controller.getMessages()[0]).toMatchObject({
      status: 'deleted',
      modified: '2026-07-16 10:02:00',
    })
    expect(harness.controller.getCursor()).toBe('cursor-2')
    expect(harness.changes.at(-1).updated).toEqual([])
  })

  it('keeps a newer delta tombstone when a delayed snapshot resets the page', async () => {
    let snapshotCalls = 0
    let resolveRefresh
    let message = (text, modified, status = 'received') => ({
      name: 'M-1',
      text,
      status,
      modified,
      message_datetime: '2026-07-16 10:00:00',
      creation: '2026-07-16 10:00:01',
    })
    let harness = createHarness({
      get_message_page: () => {
        snapshotCalls += 1
        if (snapshotCalls === 1)
          return snapshot([message('Initial', '2026-07-16 10:00:00')])
        return new Promise((resolve) => (resolveRefresh = resolve))
      },
      get_message_changes: delta([
        message('Message deleted', '2026-07-16 10:02:00', 'deleted'),
      ]),
    })
    await harness.controller.start('LEAD-1')

    let refresh = harness.controller.loadSnapshot()
    await harness.controller.syncDelta()
    resolveRefresh(
      snapshot([message('Old snapshot', '2026-07-16 10:01:00')], {
        sync_cursor: 'snapshot-cursor',
      }),
    )
    await refresh

    expect(harness.controller.getMessages()[0]).toMatchObject({
      status: 'deleted',
      modified: '2026-07-16 10:02:00',
    })
    expect(harness.changes.at(-1).updated).toEqual([])
  })

  it('starts the new Lead delta while the old Lead delta is still pending', async () => {
    let resolveOldDelta
    let harness = createHarness({
      get_message_page: ({ reference_name }) =>
        snapshot([], { sync_cursor: `${reference_name}-cursor` }),
      get_message_changes: ({ reference_name }) =>
        reference_name === 'LEAD-1'
          ? new Promise((resolve) => (resolveOldDelta = resolve))
          : delta([], { next_cursor: 'LEAD-2-next' }),
    })
    await harness.controller.start('LEAD-1')
    let oldDelta = harness.controller.syncDelta()

    await harness.controller.setLead('LEAD-2')
    let newDelta = harness.controller.syncDelta()
    await newDelta

    expect(
      harness.calls.filter(
        ([method, params]) =>
          method.endsWith('get_message_changes') &&
          params.reference_name === 'LEAD-2',
      ),
    ).toHaveLength(1)
    expect(harness.controller.getCursor()).toBe('LEAD-2-next')

    resolveOldDelta(delta([], { next_cursor: 'LEAD-1-next' }))
    await oldDelta
    expect(harness.controller.getCursor()).toBe('LEAD-2-next')
  })

  it('starts the new Lead history while the old Lead history is pending', async () => {
    let resolveOldHistory
    let harness = createHarness({
      get_message_page: ({ reference_name, before_cursor }) => {
        if (!before_cursor)
          return snapshot([], {
            sync_cursor: `${reference_name}-cursor`,
            page: {
              has_more: true,
              before_cursor: `${reference_name}-history`,
            },
          })
        if (reference_name === 'LEAD-1')
          return new Promise((resolve) => (resolveOldHistory = resolve))
        return {
          contract_version: 1,
          messages: [
            {
              name: 'LEAD-2-M',
              modified: '2026-07-16 10:00:00',
              message_datetime: '2026-07-16 09:00:00',
            },
          ],
          page: { has_more: false, before_cursor: null },
        }
      },
    })
    await harness.controller.start('LEAD-1')
    let oldHistory = harness.controller.loadOlder()

    await harness.controller.setLead('LEAD-2')
    await harness.controller.loadOlder()
    expect(harness.controller.getMessages().map(({ name }) => name)).toEqual([
      'LEAD-2-M',
    ])

    resolveOldHistory({
      contract_version: 1,
      messages: [
        {
          name: 'LEAD-1-M',
          modified: '2026-07-16 09:00:00',
          message_datetime: '2026-07-16 08:00:00',
        },
      ],
      page: { has_more: false, before_cursor: null },
    })
    await oldHistory
    expect(harness.controller.getMessages().map(({ name }) => name)).toEqual([
      'LEAD-2-M',
    ])
  })

  it('runs a delta requested while the initial snapshot is pending', async () => {
    let resolveSnapshot
    let harness = createHarness({
      get_message_page: () =>
        new Promise((resolve) => (resolveSnapshot = resolve)),
      get_message_changes: delta([
        {
          name: 'M-1',
          modified: '2026-07-16 10:01:00',
          message_datetime: '2026-07-16 10:00:00',
        },
      ]),
    })
    let started = harness.controller.start('LEAD-1')
    harness.socket.emit('crm_messenger:conversation_changed', {
      version: 1,
      reference_doctype: 'CRM Lead',
      reference_name: 'LEAD-1',
    })
    resolveSnapshot(snapshot())
    await started

    expect(harness.controller.getMessages()).toHaveLength(1)
    expect(
      harness.calls.filter(([method]) =>
        method.endsWith('get_message_changes'),
      ),
    ).toHaveLength(1)
  })
})
