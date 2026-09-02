import { createApp, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => {
  let handlers = new Map()
  return {
    attachmentPreserve: vi.fn(),
    attachmentRetarget: vi.fn(async () => {}),
    call: vi.fn(),
    dialog: vi.fn(),
    route: { query: {} },
    voiceRetarget: vi.fn(),
    voiceSend: vi.fn(),
    socket: {
      on: vi.fn((event, handler) => {
        let listeners = handlers.get(event) || []
        listeners.push(handler)
        handlers.set(event, listeners)
      }),
      off: vi.fn(),
      emit: vi.fn((event, ...args) => {
        if (event.startsWith('doc_')) return
        for (let handler of handlers.get(event) || []) handler(...args)
      }),
      reset() {
        handlers = new Map()
      },
    },
  }
})

const components = vi.hoisted(() => ({
  button: {
    props: ['label', 'disabled', 'loading'],
    emits: ['click'],
    template:
      '<button :disabled="disabled" @click="$emit(\'click\')">{{ label }}</button>',
  },
  input: {
    props: ['modelValue', 'placeholder', 'disabled'],
    emits: ['update:modelValue'],
    template:
      '<input :value="modelValue" :placeholder="placeholder" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
}))

vi.mock('frappe-ui', () => ({
  Badge: { props: ['label'], template: '<span>{{ label }}</span>' },
  Button: components.button,
  Dialog: {
    template: '<div><slot name="body-content" /><slot name="actions" /></div>',
  },
  Dropdown: { template: '<div><slot /></div>' },
  FeatherIcon: { template: '<span />' },
  FileUploadHandler: { template: '<div><slot /></div>' },
  FormControl: components.input,
  Textarea: components.input,
  Tooltip: { template: '<span><slot /></span>' },
  call: mocks.call,
  dayjsLocal: () => ({
    isValid: () => true,
    format: () => '2026-08-23',
    fromNow: () => 'now',
  }),
  toast: { error: vi.fn() },
}))

vi.mock('@/stores/global', () => ({
  globalStore: () => ({ $dialog: mocks.dialog, $socket: mocks.socket }),
}))
vi.mock('@/stores/users', () => ({
  usersStore: () => ({
    getUser: (name) => ({ name, full_name: 'Оператор Тестов' }),
  }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
}))

const emptyComponent = vi.hoisted(() => () => ({
  default: { template: '<span />' },
}))
vi.mock('@/components/Icons/CommentIcon.vue', emptyComponent)
vi.mock('@/components/Icons/LoadingIndicator.vue', emptyComponent)
vi.mock('@/components/LeadMessenger/AttachmentRenderer.vue', emptyComponent)
vi.mock('@/components/LeadMessenger/LocationPickerDialog.vue', emptyComponent)
vi.mock('@/components/LeadMessenger/MessageContent.vue', emptyComponent)
vi.mock('@/components/LeadMessenger/MessageFooterMetadata.vue', emptyComponent)
vi.mock('@/components/LeadMessenger/MessageForwardStack.vue', emptyComponent)
vi.mock('@/components/LeadMessenger/MessageMetadata.vue', emptyComponent)
vi.mock('@/components/LeadMessenger/MessageReactions.vue', emptyComponent)
vi.mock('@/components/LeadMessenger/MessageReplyQuote.vue', emptyComponent)
vi.mock('@/components/LeadMessenger/ComposerAttachments.vue', () => ({
  default: {
    emits: ['change'],
    methods: {
      discard() {},
      freeze() {
        return []
      },
      unfreeze() {},
      release() {},
      retarget(conversation) {
        return mocks.attachmentRetarget(conversation)
      },
      preserveScopeChange() {
        mocks.attachmentPreserve()
      },
      openFileSelector() {},
    },
    template:
      "<button data-testid=\"mock-attachment-draft\" @click=\"$emit('change', [{ status: 'uploaded', file: { name: 'draft.pdf', type: 'application/pdf' } }])\">attachment draft</button>",
  },
}))
vi.mock('@/components/LeadMessenger/ComposerVoiceRecorder.vue', () => ({
  default: {
    methods: {
      reset() {},
      start() {},
      send() {
        mocks.voiceSend()
      },
      retarget() {
        mocks.voiceRetarget()
      },
    },
    template: '<span />',
  },
}))

import LeadConversation from '@/components/LeadMessenger/LeadConversation.vue'

let mounted = []
let permissions
let preparedResult
let snapshotMessages
let channelRows
let conversationRows
let latestInbound

const channel = (name, capabilities = {}) => ({
  name,
  provider: 'telegram_bot',
  platform: 'telegram',
  channel_type: 'telegram',
  capabilities: {
    supports_attachments: false,
    max_attachment_count: 10,
    requires_inbound: false,
    requires_phone: false,
    voice: { send: false },
    location: { send: false },
    reactions: { receive: true, send: true },
    video: {},
    ...capabilities,
  },
})

beforeEach(() => {
  permissions = {
    can_read: true,
    can_operate: false,
    can_administer: false,
  }
  preparedResult = {
    ok: true,
    handoff: 'HANDOFF-1',
    status: 'prepared',
    target_channel: 'CHANNEL-2',
    expires_at: '2026-08-24 12:00:00',
    message: 'Перейдите в другой канал\nCRM-ABCDEFGHIJKLMNOPQRSTUVWXYZ',
  }
  snapshotMessages = []
  channelRows = [channel('CHANNEL-1'), channel('CHANNEL-2')]
  conversationRows = [
    {
      name: 'CONVERSATION-1',
      channel: 'CHANNEL-1',
      status: 'Open',
      external_chat_id: 'chat-1',
    },
  ]
  latestInbound = null
  mocks.route.query = {}
  mocks.socket.reset()
  vi.clearAllMocks()
  mocks.call.mockImplementation(async (method) => {
    if (method.endsWith('get_channels')) {
      return {
        ok: true,
        channels: channelRows,
        permissions,
      }
    }
    if (method.endsWith('get_conversations')) {
      return {
        ok: true,
        conversations: conversationRows,
        latest_inbound: latestInbound,
        permissions,
      }
    }
    if (method.endsWith('get_message_page')) {
      return {
        contract_version: 1,
        messages: snapshotMessages,
        page: { has_more: false, before_cursor: null },
        sync_cursor: 'cursor-1',
        permissions,
      }
    }
    if (method.endsWith('get_message_changes')) {
      return {
        contract_version: 1,
        changes: [],
        next_cursor: 'cursor-2',
        has_more: false,
        permissions,
      }
    }
    if (method.endsWith('create_handoff')) return preparedResult
    if (method.endsWith('revoke_handoff'))
      return { ok: true, handoff: 'HANDOFF-1', status: 'revoked' }
    if (method.endsWith('send_message'))
      return {
        ok: true,
        name: 'MESSAGE-1',
        status: 'queued',
        handoff_status: 'queued',
      }
    return { ok: true }
  })
})

function deferred() {
  let resolve
  let promise = new Promise((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

afterEach(() => {
  for (let { app, root } of mounted) {
    app.unmount()
    root.remove()
  }
  mounted = []
})

async function mountConversation(props = {}) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(LeadConversation, { leadName: 'LEAD-1', ...props })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  await nextTick()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await nextTick()
  await vi.waitFor(() => expect(root.textContent).not.toContain('Loading'))
  await nextTick()
  return root
}

function deferSelectionRequests() {
  let channelsRequest = deferred()
  let conversationsRequest = deferred()
  let defaultCall = mocks.call.getMockImplementation()
  mocks.call.mockImplementation((method, args) => {
    if (method.endsWith('get_channels')) return channelsRequest.promise
    if (method.endsWith('get_conversations'))
      return conversationsRequest.promise
    return defaultCall(method, args)
  })
  return {
    resolveChannels() {
      channelsRequest.resolve({ ok: true, channels: channelRows, permissions })
    },
    resolveConversations() {
      conversationsRequest.resolve({
        ok: true,
        conversations: conversationRows,
        latest_inbound: latestInbound,
        permissions,
      })
    },
  }
}

async function resolveSelectionRequests(requests, first) {
  await vi.waitFor(() => {
    expect(
      mocks.call.mock.calls.some(([method]) => method.endsWith('get_channels')),
    ).toBe(true)
    expect(
      mocks.call.mock.calls.some(([method]) =>
        method.endsWith('get_conversations'),
      ),
    ).toBe(true)
  })
  if (first === 'channels') {
    requests.resolveChannels()
    await nextTick()
    requests.resolveConversations()
  } else {
    requests.resolveConversations()
    await nextTick()
    requests.resolveChannels()
  }
}

describe('messenger initial selection', () => {
  it('selects the conversation containing the latest inbound message', async () => {
    permissions = { ...permissions, can_operate: true }
    conversationRows = [
      { name: 'CONVERSATION-1', channel: 'CHANNEL-1', status: 'Open' },
      { name: 'CONVERSATION-2', channel: 'CHANNEL-2', status: 'Open' },
    ]
    latestInbound = {
      message: 'MESSAGE-2',
      conversation: 'CONVERSATION-2',
      channel: 'CHANNEL-2',
      message_datetime: '2026-08-28 10:00:00',
      creation: '2026-08-28 10:00:00',
    }

    let root = await mountConversation()

    expect(root.querySelector('input[placeholder="Platform"]').value).toBe(
      'CHANNEL-2',
    )
    expect(
      root.querySelector('[data-testid="conversation-routing-warning"]'),
    ).toBeNull()
  })

  it.each(['channels', 'conversations'])(
    'selects the first conversation channel when %s resolve first',
    async (first) => {
      permissions = { ...permissions, can_operate: true }
      conversationRows = [
        {
          name: 'CONVERSATION-2',
          channel: 'CHANNEL-2',
          status: 'Open',
          external_chat_id: 'chat-2',
        },
      ]
      let requests = deferSelectionRequests()
      let mounting = mountConversation()

      await resolveSelectionRequests(requests, first)
      let root = await mounting

      expect(root.querySelector('input[placeholder="Platform"]').value).toBe(
        'CHANNEL-2',
      )
    },
  )

  it('falls back to the first channel when there are no conversations', async () => {
    permissions = { ...permissions, can_operate: true }
    conversationRows = []

    let root = await mountConversation()

    expect(root.querySelector('input[placeholder="Platform"]').value).toBe(
      'CHANNEL-1',
    )
  })

  it.each(['channels', 'conversations'])(
    'applies a requested conversation when %s resolve first',
    async (first) => {
      permissions = { ...permissions, can_operate: true }
      channelRows = [
        channel('CHANNEL-1'),
        channel('CHANNEL-2'),
        channel('CHANNEL-3'),
      ]
      conversationRows = [
        {
          name: 'CONVERSATION-RECENT',
          channel: 'CHANNEL-2',
          status: 'Open',
        },
        {
          name: 'CONVERSATION-REQUESTED-1',
          channel: 'CHANNEL-3',
          status: 'Open',
        },
        {
          name: 'CONVERSATION-REQUESTED-2',
          channel: 'CHANNEL-3',
          status: 'Open',
        },
      ]
      mocks.route.query = {
        messenger_conversation: 'CONVERSATION-REQUESTED-2',
      }
      let requests = deferSelectionRequests()
      let mounting = mountConversation()

      await resolveSelectionRequests(requests, first)
      let root = await mounting

      expect(root.querySelector('input[placeholder="Platform"]').value).toBe(
        'CHANNEL-3',
      )
      expect(
        root.querySelector('input[placeholder="External Chat"]').value,
      ).toBe('CONVERSATION-REQUESTED-2')
    },
  )

  it('preserves a valid explicit selection across refresh and realtime reload', async () => {
    permissions = { ...permissions, can_operate: true }
    conversationRows = [
      {
        name: 'CONVERSATION-2',
        channel: 'CHANNEL-2',
        status: 'Open',
      },
      {
        name: 'CONVERSATION-1A',
        channel: 'CHANNEL-1',
        status: 'Open',
        external_chat_id: 'chat-1a',
      },
      {
        name: 'CONVERSATION-1B',
        channel: 'CHANNEL-1',
        status: 'Open',
        external_chat_id: 'chat-1b',
      },
    ]
    latestInbound = {
      message: 'MESSAGE-2',
      conversation: 'CONVERSATION-2',
      channel: 'CHANNEL-2',
      message_datetime: '2026-08-28 10:00:00',
      creation: '2026-08-28 10:00:00',
    }
    let root = await mountConversation()
    let platform = root.querySelector('input[placeholder="Platform"]')
    platform.value = 'CHANNEL-1'
    platform.dispatchEvent(new Event('input'))
    await nextTick()
    let externalChat = root.querySelector('input[placeholder="External Chat"]')
    externalChat.value = 'CONVERSATION-1B'
    externalChat.dispatchEvent(new Event('input'))
    await nextTick()

    let channelLoads = mocks.call.mock.calls.filter(([method]) =>
      method.endsWith('get_channels'),
    ).length
    ;[...root.querySelectorAll('button')]
      .find((button) => button.textContent === 'Refresh')
      .click()
    await vi.waitFor(() =>
      expect(
        mocks.call.mock.calls.filter(([method]) =>
          method.endsWith('get_channels'),
        ).length,
      ).toBeGreaterThan(channelLoads),
    )
    expect(platform.value).toBe('CHANNEL-1')
    expect(externalChat.value).toBe('CONVERSATION-1B')

    let conversationLoads = mocks.call.mock.calls.filter(([method]) =>
      method.endsWith('get_conversations'),
    ).length
    mocks.socket.emit('crm_messenger:conversation_changed', {
      version: 1,
      reference_doctype: 'CRM Lead',
      reference_name: 'LEAD-1',
      conversation: 'CONVERSATION-2',
      conversation_state_changed: true,
    })
    await vi.waitFor(() =>
      expect(
        mocks.call.mock.calls.filter(([method]) =>
          method.endsWith('get_conversations'),
        ).length,
      ).toBeGreaterThan(conversationLoads),
    )
    expect(platform.value).toBe('CHANNEL-1')
    expect(externalChat.value).toBe('CONVERSATION-1B')
  })

  it('does not replace a draft-pinned conversation with a newer inbound', async () => {
    permissions = { ...permissions, can_operate: true }
    conversationRows = [
      { name: 'CONVERSATION-1', channel: 'CHANNEL-1', status: 'Open' },
      { name: 'CONVERSATION-2', channel: 'CHANNEL-2', status: 'Open' },
    ]
    latestInbound = {
      message: 'MESSAGE-1',
      conversation: 'CONVERSATION-1',
      channel: 'CHANNEL-1',
      message_datetime: '2026-08-28 10:00:00',
      creation: '2026-08-28 10:00:00',
    }
    let root = await mountConversation()
    let composer = root.querySelector('input[placeholder="Enter a message..."]')
    composer.value = 'Keep this draft on conversation 1'
    composer.dispatchEvent(new Event('input'))
    await nextTick()
    latestInbound = {
      message: 'MESSAGE-2',
      conversation: 'CONVERSATION-2',
      channel: 'CHANNEL-2',
      message_datetime: '2026-08-28 10:01:00',
      creation: '2026-08-28 10:01:00',
    }

    mocks.socket.emit('crm_messenger:conversation_changed', {
      version: 1,
      reference_doctype: 'CRM Lead',
      reference_name: 'LEAD-1',
      conversation: 'CONVERSATION-2',
      conversation_state_changed: true,
    })

    await vi.waitFor(() =>
      expect(
        root.querySelector('[data-testid="conversation-routing-warning"]'),
      ).not.toBeNull(),
    )
    expect(root.querySelector('input[placeholder="Platform"]').value).toBe(
      'CHANNEL-1',
    )
    expect(composer.value).toBe('Keep this draft on conversation 1')
  })
})

describe('messenger conversation routing guard', () => {
  function prepareRoutingFixture({ attachments = false } = {}) {
    permissions = { ...permissions, can_operate: true }
    let capabilityOverrides = attachments ? { supports_attachments: true } : {}
    channelRows = [
      channel('CHANNEL-1', capabilityOverrides),
      channel('CHANNEL-2', capabilityOverrides),
    ]
    conversationRows = [
      {
        name: 'CONVERSATION-1',
        channel: 'CHANNEL-1',
        status: 'Open',
        external_chat_id: 'chat-1',
      },
      {
        name: 'CONVERSATION-2',
        channel: 'CHANNEL-2',
        status: 'Open',
        external_chat_id: 'chat-2',
      },
    ]
    latestInbound = {
      message: 'MESSAGE-2',
      conversation: 'CONVERSATION-2',
      channel: 'CHANNEL-2',
      message_datetime: '2026-08-28 10:01:00',
      creation: '2026-08-28 10:01:00',
    }
  }

  async function selectConversationOne(root, text = '') {
    let platform = root.querySelector('input[placeholder="Platform"]')
    platform.value = 'CHANNEL-1'
    platform.dispatchEvent(new Event('input'))
    await nextTick()
    if (text) {
      let composer = root.querySelector(
        'input[placeholder="Enter a message..."]',
      )
      composer.value = text
      composer.dispatchEvent(new Event('input'))
      await nextTick()
    }
  }

  function sendButton(root) {
    return [...root.querySelectorAll('button')].find(
      (button) => button.textContent === 'Send',
    )
  }

  it('shows the mismatch warning only for a different selected conversation', async () => {
    prepareRoutingFixture()
    channelRows[0].label = 'Telegram - Support'
    channelRows[1].label = 'Telegram - Sales'
    conversationRows[0].client_name = 'Иван'
    conversationRows[0].last_message_at = '2026-08-28 10:00:00'
    conversationRows[1].client_name = 'Пётр'
    conversationRows[1].last_message_at = '2026-08-28 10:01:00'
    let root = await mountConversation()

    expect(
      root.querySelector('[data-testid="conversation-routing-warning"]'),
    ).toBeNull()

    await selectConversationOne(root)

    let warning = root.querySelector(
      '[data-testid="conversation-routing-warning"]',
    )
    expect(warning).not.toBeNull()
    expect(warning.textContent).toContain('Telegram - Sales')
    expect(warning.textContent).toContain('Telegram - Support')
    expect(warning.textContent).not.toContain('Иван')
    expect(warning.textContent).not.toContain('Пётр')
    expect(warning.textContent).not.toContain('CONVERSATION-')
    expect(warning.textContent).not.toContain('2026-08-28')
  })

  it('confirms and sends through the intentionally selected conversation', async () => {
    prepareRoutingFixture()
    channelRows[0].label = 'Telegram - Support'
    channelRows[1].label = 'Telegram - Sales'
    let root = await mountConversation()
    await selectConversationOne(root, 'Send intentionally through chat 1')

    sendButton(root).click()

    expect(
      mocks.call.mock.calls.some(([method]) => method.endsWith('send_message')),
    ).toBe(false)
    let dialog = mocks.dialog.mock.calls.at(-1)[0]
    expect(dialog.title).toBe('Check sending conversation')
    expect(dialog.message).toBe(
      'The latest inbound message arrived in Telegram - Sales, but Telegram - Support is selected.',
    )
    expect(dialog.actions.map((action) => action.label)).toEqual([
      'Send through Telegram - Support',
      'Switch to Telegram - Sales',
      'Cancel',
    ])
    dialog.actions
      .find((action) => action.label.startsWith('Send through'))
      .onClick(vi.fn())

    await vi.waitFor(() =>
      expect(mocks.call).toHaveBeenCalledWith(
        'crm_messenger.api.messages.send_message',
        expect.objectContaining({
          conversation: 'CONVERSATION-1',
          text: 'Send intentionally through chat 1',
        }),
      ),
    )
  })

  it('does not send when the routing confirmation is cancelled', async () => {
    prepareRoutingFixture()
    let root = await mountConversation()
    await selectConversationOne(root, 'Do not send this')

    sendButton(root).click()
    let dialog = mocks.dialog.mock.calls.at(-1)[0]
    dialog.actions.find((action) => action.label === 'Cancel').onClick(vi.fn())
    await nextTick()

    expect(
      mocks.call.mock.calls.some(([method]) => method.endsWith('send_message')),
    ).toBe(false)
  })

  it('retargets uploaded composer attachments before switching', async () => {
    prepareRoutingFixture({ attachments: true })
    let root = await mountConversation()
    await selectConversationOne(root, 'Keep the composer draft')
    root.querySelector('[data-testid="mock-attachment-draft"]').click()
    await nextTick()

    root.querySelector('[data-testid="conversation-routing-switch"]').click()

    await vi.waitFor(() =>
      expect(mocks.attachmentRetarget).toHaveBeenCalledWith('CONVERSATION-2'),
    )
    await vi.waitFor(() =>
      expect(root.querySelector('input[placeholder="Platform"]').value).toBe(
        'CHANNEL-2',
      ),
    )
    expect(
      root.querySelector('input[placeholder="Enter a message..."]').value,
    ).toBe('Keep the composer draft')
  })

  it('selects and pins the source conversation of an inbound message click', async () => {
    prepareRoutingFixture()
    snapshotMessages = [
      {
        name: 'MESSAGE-1',
        conversation: 'CONVERSATION-1',
        channel: 'CHANNEL-1',
        direction: 'inbound',
        status: 'received',
        message_datetime: '2026-08-28 10:00:00',
      },
    ]
    let root = await mountConversation()

    root.querySelector('[data-message-bubble]').click()

    await vi.waitFor(() =>
      expect(root.querySelector('input[placeholder="Platform"]').value).toBe(
        'CHANNEL-1',
      ),
    )
    expect(
      root.querySelector('[data-testid="conversation-routing-warning"]'),
    ).not.toBeNull()
  })
})

describe('messenger permission rendering', () => {
  it('renders read-only history without composer or handoff controls', async () => {
    let root = await mountConversation()

    expect(root.textContent).toContain('Read Only')
    expect(root.textContent).not.toContain('Send')
    expect(root.textContent).not.toContain('Prepare Handoff')
    expect(
      root.querySelector('input[placeholder="Enter a message..."]'),
    ).toBeNull()
  })

  it('renders operator composer and handoff controls', async () => {
    permissions = { ...permissions, can_operate: true }
    let root = await mountConversation()

    expect(root.textContent).not.toContain('Read Only')
    expect(root.textContent).toContain('Send')
    expect(root.textContent).toContain('Prepare Handoff')
    expect(
      root.querySelector('input[placeholder="Enter a message..."]'),
    ).not.toBeNull()
  })

  it('does not send Enter while an IME composition is active', async () => {
    permissions = { ...permissions, can_operate: true }
    let root = await mountConversation()
    let composer = root.querySelector('input[placeholder="Enter a message..."]')
    composer.value = 'составляемый текст'
    composer.dispatchEvent(new Event('input'))
    composer.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'Enter',
        bubbles: true,
        isComposing: true,
      }),
    )
    await nextTick()

    expect(
      mocks.call.mock.calls.some(([method]) => method.endsWith('send_message')),
    ).toBe(false)
  })

  it('marks a Messenger notification at the loaded event boundary', async () => {
    snapshotMessages = [
      {
        name: 'MESSAGE-INBOUND-1',
        conversation: 'CONVERSATION-1',
        direction: 'inbound',
        status: 'received',
        ingest_source: 'provider_webhook',
        message_datetime: '2026-08-23 12:00:00',
      },
    ]

    await mountConversation()

    await vi.waitFor(() =>
      expect(mocks.call).toHaveBeenCalledWith(
        'crm.api.notifications.mark_messenger_as_read',
        {
          conversation: 'CONVERSATION-1',
          last_event_id: 'MESSAGE-INBOUND-1',
        },
      ),
    )
  })

  it('does not mark Messenger notifications while the tab is inactive', async () => {
    snapshotMessages = [
      {
        name: 'MESSAGE-INBOUND-1',
        conversation: 'CONVERSATION-1',
        direction: 'inbound',
        status: 'received',
        ingest_source: 'provider_webhook',
        message_datetime: '2026-08-23 12:00:00',
      },
    ]

    await mountConversation({ active: false })

    expect(
      mocks.call.mock.calls.some(([method]) =>
        method.endsWith('mark_messenger_as_read'),
      ),
    ).toBe(false)
  })

  it('closes an active composer when a delta revokes operator permission', async () => {
    permissions = { ...permissions, can_operate: true }
    let root = await mountConversation()
    let composer = root.querySelector('input[placeholder="Enter a message..."]')
    composer.value = 'unsent draft'
    composer.dispatchEvent(new Event('input'))

    permissions = { ...permissions, can_operate: false }
    mocks.socket.emit('crm_messenger:conversation_changed', {
      version: 1,
      reference_doctype: 'CRM Lead',
      reference_name: 'LEAD-1',
      conversation: 'CONVERSATION-1',
    })

    await vi.waitFor(() => expect(root.textContent).toContain('Read Only'))
    expect(
      root.querySelector('input[placeholder="Enter a message..."]'),
    ).toBeNull()
  })

  it('locks prepared handoff text and sends it with the handoff id', async () => {
    permissions = { ...permissions, can_operate: true }
    let root = await mountConversation()
    let target = root.querySelector(
      'input[placeholder="Move to another channel"]',
    )
    target.value = 'CHANNEL-2'
    target.dispatchEvent(new Event('input'))
    await nextTick()
    ;[...root.querySelectorAll('button')]
      .find((button) => button.textContent === 'Prepare Handoff')
      .click()

    await vi.waitFor(() =>
      expect(
        root.querySelector('[data-testid="prepared-handoff"]'),
      ).not.toBeNull(),
    )
    expect(root.textContent).toContain(preparedResult.message)
    expect(
      root.querySelector('input[placeholder="Enter a message..."]'),
    ).toBeNull()
    expect(root.querySelector('input[placeholder="Platform"]').disabled).toBe(
      true,
    )
    ;[...root.querySelectorAll('button')]
      .find((button) => button.textContent === 'Send')
      .click()

    await vi.waitFor(() =>
      expect(mocks.call).toHaveBeenCalledWith(
        'crm_messenger.api.messages.send_message',
        expect.objectContaining({
          conversation: 'CONVERSATION-1',
          text: preparedResult.message,
          handoff: 'HANDOFF-1',
          attachments: [],
        }),
      ),
    )
    await vi.waitFor(() =>
      expect(root.querySelector('[data-testid="prepared-handoff"]')).toBeNull(),
    )
  })

  it('keeps prepared handoff until revoke succeeds', async () => {
    permissions = { ...permissions, can_operate: true }
    let root = await mountConversation()
    let target = root.querySelector(
      'input[placeholder="Move to another channel"]',
    )
    target.value = 'CHANNEL-2'
    target.dispatchEvent(new Event('input'))
    await nextTick()
    ;[...root.querySelectorAll('button')]
      .find((button) => button.textContent === 'Prepare Handoff')
      .click()
    await vi.waitFor(() =>
      expect(
        root.querySelector('[data-testid="prepared-handoff"]'),
      ).not.toBeNull(),
    )
    ;[...root.querySelectorAll('button')]
      .find((button) => button.textContent === 'Cancel')
      .click()

    await vi.waitFor(() =>
      expect(mocks.call).toHaveBeenCalledWith(
        'crm_messenger.api.handoffs.revoke_handoff',
        { handoff: 'HANDOFF-1' },
      ),
    )
    await vi.waitFor(() =>
      expect(root.querySelector('[data-testid="prepared-handoff"]')).toBeNull(),
    )
  })

  it('keeps a prepared handoff after a recoverable send error', async () => {
    permissions = { ...permissions, can_operate: true }
    let root = await mountConversation()
    let target = root.querySelector(
      'input[placeholder="Move to another channel"]',
    )
    target.value = 'CHANNEL-2'
    target.dispatchEvent(new Event('input'))
    await nextTick()
    ;[...root.querySelectorAll('button')]
      .find((button) => button.textContent === 'Prepare Handoff')
      .click()
    await vi.waitFor(() =>
      expect(
        root.querySelector('[data-testid="prepared-handoff"]'),
      ).not.toBeNull(),
    )
    let defaultCall = mocks.call.getMockImplementation()
    mocks.call.mockImplementation(async (method, args) => {
      if (method.endsWith('send_message')) throw new Error('network error')
      return defaultCall(method, args)
    })
    ;[...root.querySelectorAll('button')]
      .find((button) => button.textContent === 'Send')
      .click()

    await vi.waitFor(() =>
      expect(
        root.querySelector('[data-testid="prepared-handoff"]'),
      ).not.toBeNull(),
    )
  })

  it('clears a prepared handoff after a terminal server response', async () => {
    permissions = { ...permissions, can_operate: true }
    let root = await mountConversation()
    let target = root.querySelector(
      'input[placeholder="Move to another channel"]',
    )
    target.value = 'CHANNEL-2'
    target.dispatchEvent(new Event('input'))
    await nextTick()
    ;[...root.querySelectorAll('button')]
      .find((button) => button.textContent === 'Prepare Handoff')
      .click()
    await vi.waitFor(() =>
      expect(
        root.querySelector('[data-testid="prepared-handoff"]'),
      ).not.toBeNull(),
    )
    let defaultCall = mocks.call.getMockImplementation()
    mocks.call.mockImplementation(async (method, args) => {
      if (method.endsWith('send_message'))
        return {
          ok: false,
          reason: 'handoff_expired',
          message: 'Handoff has expired.',
        }
      return defaultCall(method, args)
    })
    ;[...root.querySelectorAll('button')]
      .find((button) => button.textContent === 'Send')
      .click()

    await vi.waitFor(() =>
      expect(root.querySelector('[data-testid="prepared-handoff"]')).toBeNull(),
    )
  })
})
