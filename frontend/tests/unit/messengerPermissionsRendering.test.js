import { createApp, h, nextTick, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => {
  let handlers = new Map()
  return {
    attachmentPreserve: vi.fn(),
    attachmentRetarget: vi.fn(async () => {}),
    attachmentRelease: vi.fn(),
    attachmentUnmount: vi.fn(),
    call: vi.fn(),
    dialog: vi.fn(),
    toastError: vi.fn(),
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
  toast: { error: mocks.toastError },
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
vi.mock('@/components/LeadMessenger/MessageMetadata.vue', () => ({
  default: {
    props: ['message', 'constrainIntrinsicWidth'],
    emits: ['retry', 'reply'],
    template: `<div data-message-metadata :class="constrainIntrinsicWidth ? 'w-0 min-w-full' : 'min-w-0'">
				<button v-if="message.can_retry" data-testid="mock-message-retry" @click="$emit('retry')">retry</button>
				<button v-if="message.can_reply" data-testid="mock-message-reply" @click="$emit('reply')">reply</button>
		</div>`,
  },
}))
vi.mock('@/components/LeadMessenger/MessageReactions.vue', emptyComponent)
vi.mock('@/components/LeadMessenger/ComposerAttachments.vue', () => ({
  default: {
    props: [
      'acceptedFileTypes',
      'acceptedFileTypesByType',
      'maxFiles',
      'supportedAttachmentTypes',
      'maxAttachmentSizeBytes',
      'maxAttachmentSizeBytesByType',
    ],
    emits: ['change'],
    data: () => ({ files: [] }),
    beforeUnmount() {
      mocks.attachmentUnmount()
    },
    methods: {
      discard() {},
      freeze() {
        return this.files
      },
      unfreeze() {},
      release() {
        mocks.attachmentRelease()
        this.clearDraft()
      },
      retarget(conversation) {
        return mocks.attachmentRetarget(conversation)
      },
      preserveScopeChange() {
        mocks.attachmentPreserve()
      },
      openFileSelector() {},
      setDraft(name, type) {
        this.files = [`FILE-${name}`]
        this.$emit('change', [
          {
            status: 'uploaded',
            file: { name, type },
            uploadedFile: { name: this.files[0] },
          },
        ])
      },
      clearDraft() {
        this.files = []
        this.$emit('change', [])
      },
    },
    template: `<span data-attachment-policy :data-max-size="maxAttachmentSizeBytes" :data-image-max-size="maxAttachmentSizeBytesByType?.image" :data-max-files="maxFiles" :data-video-formats="acceptedFileTypesByType?.video?.join(',')">
      <button data-testid="mock-attachment-draft" @click="setDraft('draft.pdf', 'application/pdf')">attachment draft</button>
      <button data-testid="mock-image-draft" @click="setDraft('photo.jpg', 'image/jpeg')">image draft</button>
      <button data-testid="mock-clear-attachments" @click="clearDraft">clear attachments</button>
    </span>`,
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
  let reject
  let promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
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
  let liveProps = reactive({ leadName: 'LEAD-1', ...props })
  let app = createApp({ render: () => h(LeadConversation, liveProps) })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root, props: liveProps })
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

describe('Avito subscription restriction', () => {
  function restrictedChannel(name = 'AVITO') {
    return {
      ...channel(name),
      provider: 'avito_direct',
      platform: 'avito',
      capabilities: {
        ...channel(name).capabilities,
        messenger_access: 'subscription_required',
        supports_text: false,
        supports_attachments: false,
      },
      can_send: false,
      disabled_reason: 'messenger_subscription_required',
    }
  }

  it.each([
    ['no source', {}],
    ['VK source', { source: 'VK' }],
    ['Telegram source', { source: 'Telegram bot' }],
  ])('shows an empty conversation for a lead with %s', async (_, lead) => {
    permissions = { ...permissions, can_operate: true }
    channelRows = [restrictedChannel(), channel('TELEGRAM')]
    conversationRows = []

    let root = await mountConversation({ lead })

    expect(root.querySelector('input[placeholder="Platform"]')?.value).toBe(
      'AVITO',
    )
    expect(
      root.querySelector('[data-testid="avito-subscription-notice"]'),
    ).toBeNull()
    expect(root.querySelector('[data-testid="avito-open-chat"]')).toBeNull()
    expect(root.textContent).toContain('No messages yet')
    expect(
      root.querySelector('input[placeholder="Enter a message..."]'),
    ).toBeNull()
    expect(
      mocks.call.mock.calls.some(([method]) => method.endsWith('send_message')),
    ).toBe(false)
  })

  it.each([
    ['Avito source', { source: 'Avito' }],
    ['no source', {}],
  ])(
    'shows the real chat link and restricts a linked Avito chat with %s',
    async (_, lead) => {
      permissions = { ...permissions, can_operate: true }
      channelRows = [restrictedChannel()]
      conversationRows = [
        {
          name: 'AVITO-CHAT',
          provider: 'avito_direct',
          channel: 'AVITO',
          external_chat_id: 'A'.repeat(26),
          status: 'Open',
        },
      ]
      conversationRows[0].avito_item = {
        id: '123',
        title: 'Balancing machine',
        price_string: '1 615 680 ₽',
        url: 'https://www.avito.ru/item_123',
      }
      snapshotMessages = [
        {
          name: 'OLD-AVITO-MESSAGE',
          conversation: 'AVITO-CHAT',
          channel: 'AVITO',
          provider: 'avito_direct',
          direction: 'inbound',
          text: 'old content',
          message_datetime: '2026-08-23 10:00:00',
        },
      ]
      let root = await mountConversation({ lead })
      let notice = root.querySelector(
        '[data-testid="avito-subscription-notice"]',
      )
      expect(notice?.textContent).toContain(
        'The lead is synchronized automatically',
      )
      expect(
        notice?.querySelector('[data-testid="avito-open-chat"]').href,
      ).toBe(`https://www.avito.ru/profile/messenger/channel/${'A'.repeat(26)}`)
      expect(
        root.querySelector('[data-message-id="OLD-AVITO-MESSAGE"]'),
      ).toBeNull()
      expect(
        root.querySelector('input[placeholder="Enter a message..."]'),
      ).toBeNull()
      expect(root.querySelector('[data-testid="avito-item-card"]')).toBeNull()
      expect(
        root.querySelectorAll('[data-testid="avito-subscription-notice"]'),
      ).toHaveLength(1)
      expect(root.textContent.match(/Balancing machine/g)).toHaveLength(1)
      expect(notice.textContent).toContain('1 615 680 ₽')
      expect(root.textContent).not.toContain('No messages yet')
    },
  )

  it('reloads channel access when an open conversation is invalidated', async () => {
    permissions = { ...permissions, can_operate: true }
    channelRows = [restrictedChannel()]
    conversationRows = [
      {
        name: 'AVITO-CHAT',
        provider: 'avito_direct',
        channel: 'AVITO',
        external_chat_id: 'A'.repeat(26),
        status: 'Open',
      },
    ]
    conversationRows[0].avito_item = { id: '123', title: 'Balancing machine' }
    let root = await mountConversation({ active: true })
    expect(
      root.querySelector('[data-testid="avito-subscription-notice"]'),
    ).not.toBeNull()
    channelRows = [
      { ...channel('AVITO'), provider: 'avito_direct', platform: 'avito' },
    ]
    mocks.socket.emit('crm_messenger:conversation_changed', {
      version: 1,
      reference_doctype: 'CRM Lead',
      reference_name: 'LEAD-1',
      conversation_state_changed: true,
      scope_invalidated: true,
    })
    await vi.waitFor(() =>
      expect(
        root.querySelector('[data-testid="avito-subscription-notice"]'),
      ).toBeNull(),
    )
    expect(root.querySelector('[data-testid="avito-item-card"]')).not.toBeNull()
    expect(
      root.querySelector('input[placeholder="Enter a message..."]'),
    ).not.toBeNull()
  })

  it.each([
    ['Telegram', 'telegram_bot', 'telegram'],
    ['VK', 'vk_direct', 'vk'],
  ])(
    'keeps %s available in a lead with a restricted Avito channel',
    async (_, provider, platform) => {
      permissions = { ...permissions, can_operate: true }
      channelRows = [
        restrictedChannel(),
        { ...channel('OTHER'), provider, platform, channel_type: platform },
      ]
      conversationRows = [
        {
          name: 'OTHER-CHAT',
          channel: 'OTHER',
          provider,
          external_chat_id: 'chat-1',
          status: 'Open',
        },
        {
          name: 'AVITO-CHAT',
          channel: 'AVITO',
          provider: 'avito_direct',
          external_chat_id: 'A'.repeat(26),
          status: 'Open',
        },
      ]
      latestInbound = { conversation: 'OTHER-CHAT', channel: 'OTHER' }
      let root = await mountConversation()
      expect(
        root.querySelector('[data-testid="avito-subscription-notice"]'),
      ).toBeNull()
      expect(
        root.querySelector('input[placeholder="Enter a message..."]')?.disabled,
      ).toBe(false)
    },
  )

  it('shows the notice only for the selected chat while switching channels and conversations', async () => {
    permissions = { ...permissions, can_operate: true }
    channelRows = [
      restrictedChannel(),
      restrictedChannel('UNRELATED-AVITO'),
      channel('TELEGRAM'),
    ]
    conversationRows = [
      {
        name: 'TELEGRAM-CHAT',
        channel: 'TELEGRAM',
        provider: 'telegram_bot',
        external_chat_id: 'chat-1',
        status: 'Open',
      },
      ...['A', 'B'].map((id) => ({
        name: `AVITO-CHAT-${id}`,
        channel: 'AVITO',
        provider: 'avito_direct',
        external_chat_id: id.repeat(26),
        status: 'Open',
      })),
    ]
    latestInbound = { conversation: 'TELEGRAM-CHAT', channel: 'TELEGRAM' }
    let root = await mountConversation()
    let platform = root.querySelector('input[placeholder="Platform"]')
    platform.value = 'AVITO'
    platform.dispatchEvent(new Event('input'))
    await nextTick()

    expect(
      root.querySelector('[data-testid="avito-subscription-notice"]'),
    ).toBeNull()
    let externalChat = root.querySelector('input[placeholder="External Chat"]')
    expect(externalChat?.value).toBe('')
    for (let id of ['A', 'B']) {
      externalChat.value = `AVITO-CHAT-${id}`
      externalChat.dispatchEvent(new Event('input'))
      await nextTick()
      expect(root.querySelector('[data-testid="avito-open-chat"]')?.href).toBe(
        `https://www.avito.ru/profile/messenger/channel/${id.repeat(26)}`,
      )
    }

    platform.value = 'UNRELATED-AVITO'
    platform.dispatchEvent(new Event('input'))
    await nextTick()
    expect(
      root.querySelector('[data-testid="avito-subscription-notice"]'),
    ).toBeNull()
    expect(root.querySelector('[data-testid="avito-open-chat"]')).toBeNull()
    expect(
      root.querySelector('input[placeholder="Enter a message..."]'),
    ).toBeNull()
    expect(
      mocks.call.mock.calls.some(([method]) =>
        ['send_message', 'send_typing'].some((name) => method.endsWith(name)),
      ),
    ).toBe(false)

    platform.value = 'TELEGRAM'
    platform.dispatchEvent(new Event('input'))
    await nextTick()
    expect(
      root.querySelector('[data-testid="avito-subscription-notice"]'),
    ).toBeNull()
    expect(
      root.querySelector('input[placeholder="Enter a message..."]')?.disabled,
    ).toBe(false)
  })

  it('clears the notice for a different lead and restores it for the linked chat', async () => {
    permissions = { ...permissions, can_operate: true }
    channelRows = [restrictedChannel()]
    conversationRows = [
      {
        name: 'AVITO-CHAT',
        provider: 'avito_direct',
        channel: 'AVITO',
        external_chat_id: 'A'.repeat(26),
        status: 'Open',
      },
    ]
    let linkedConversations = conversationRows
    let root = await mountConversation({ lead: { source: 'Avito' } })
    expect(root.querySelector('[data-testid="avito-open-chat"]')?.href).toBe(
      `https://www.avito.ru/profile/messenger/channel/${'A'.repeat(26)}`,
    )

    conversationRows = []
    mounted.at(-1).props.leadName = 'LEAD-2'
    mounted.at(-1).props.lead = { source: 'VK' }
    await nextTick()
    await vi.waitFor(() =>
      expect(root.textContent).toContain('No messages yet'),
    )
    expect(
      root.querySelector('[data-testid="avito-subscription-notice"]'),
    ).toBeNull()
    expect(root.querySelector('[data-testid="avito-open-chat"]')).toBeNull()

    conversationRows = linkedConversations
    mounted.at(-1).props.leadName = 'LEAD-1'
    mounted.at(-1).props.lead = {}
    await nextTick()
    await vi.waitFor(() =>
      expect(root.querySelector('[data-testid="avito-open-chat"]')?.href).toBe(
        `https://www.avito.ru/profile/messenger/channel/${'A'.repeat(26)}`,
      ),
    )
  })
})

describe('messenger initial selection', () => {
  it.each(['success', 'failure', 'return-to-same-lead'])(
    'ignores obsolete Lead context responses: %s',
    async (outcome) => {
      permissions = { ...permissions, can_operate: true }
      channelRows = [channel('CHANNEL-2')]
      conversationRows = [
        { name: 'CURRENT-CHAT', channel: 'CHANNEL-2', status: 'Open' },
      ]
      latestInbound = { conversation: 'CURRENT-CHAT', channel: 'CHANNEL-2' }
      let oldChannels = deferred()
      let oldConversations = deferred()
      let deferredMethods = new Set()
      let defaultCall = mocks.call.getMockImplementation()
      mocks.call.mockImplementation((method, args) => {
        if (args?.reference_name === 'LEAD-1' && !deferredMethods.has(method)) {
          if (
            method.endsWith('get_channels') ||
            method.endsWith('get_conversations')
          ) {
            deferredMethods.add(method)
            return method.endsWith('get_channels')
              ? oldChannels.promise
              : oldConversations.promise
          }
        }
        return defaultCall(method, args)
      })
      let mounting = mountConversation()
      await vi.waitFor(() => expect(deferredMethods.size).toBe(2))
      mounted.at(-1).props.leadName = 'LEAD-2'
      let root = await mounting
      if (outcome === 'return-to-same-lead') {
        mounted.at(-1).props.leadName = 'LEAD-1'
        await nextTick()
        await vi.waitFor(() =>
          expect(
            root.querySelector('input[placeholder="Platform"]')?.value,
          ).toBe('CHANNEL-2'),
        )
      }
      let composer = root.querySelector(
        'input[placeholder="Enter a message..."]',
      )
      composer.value = 'Current Lead draft'
      composer.dispatchEvent(new Event('input'))
      await nextTick()
      if (outcome === 'failure') {
        oldChannels.reject(new Error('Obsolete channel failure'))
        oldConversations.reject(new Error('Obsolete conversation failure'))
      } else {
        oldChannels.resolve({
          ok: true,
          channels: [channel('OLD-CHANNEL')],
          permissions: { can_read: true, can_operate: false },
        })
        oldConversations.resolve({
          ok: true,
          conversations: [{ name: 'OLD-CHAT', channel: 'OLD-CHANNEL' }],
          latest_inbound: { conversation: 'OLD-CHAT' },
          permissions: { can_read: true, can_operate: false },
        })
      }
      await new Promise((resolve) => setTimeout(resolve, 0))
      await nextTick()
      expect(root.querySelector('input[placeholder="Platform"]')?.value).toBe(
        'CHANNEL-2',
      )
      expect(
        root.querySelector('input[placeholder="Enter a message..."]')?.value,
      ).toBe('Current Lead draft')
      expect(root.textContent).not.toContain('Obsolete')
      expect(root.textContent).not.toContain('Read Only')
    },
  )

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

describe('Wazzup configuration warnings', () => {
  it.each([
    ['partner_api_v2', 'Ask your system administrator to check the connection'],
    ['user_api_v3', 'Enable the integration and enter an API token'],
  ])(
    'uses the connection model for %s send failures',
    async (mode, warning) => {
      permissions = { ...permissions, can_operate: true }
      channelRows = [
        {
          ...channel('CHANNEL-1'),
          provider: 'wazzup',
          platform: 'whatsapp',
          channel_type: 'whatsapp',
          wazzup_api_mode: mode,
        },
      ]
      conversationRows[0].provider = 'wazzup'
      const defaultCall = mocks.call.getMockImplementation()
      mocks.call.mockImplementation((method, args) =>
        method.endsWith('send_message')
          ? Promise.resolve({
              ok: false,
              name: 'MESSAGE-FAILED',
              channel: 'CHANNEL-1',
              reason: 'not_configured',
            })
          : defaultCall(method, args),
      )
      const root = await mountConversation()
      const composer = root.querySelector(
        'input[placeholder="Enter a message..."]',
      )
      composer.value = 'Check connection'
      composer.dispatchEvent(new Event('input'))
      await nextTick()
      const send = [...root.querySelectorAll('button')].find(
        (button) => button.textContent === 'Send',
      )
      send.click()
      await vi.waitFor(() => expect(root.textContent).toContain(warning))
      expect(mocks.toastError).toHaveBeenCalledWith(
        expect.stringContaining(warning),
      )
      if (mode === 'partner_api_v2') {
        expect(root.textContent).not.toContain('enter an API token')
      }
    },
  )
})

describe('VK image outbound composer', () => {
  async function mountVKImageComposer() {
    permissions = { ...permissions, can_operate: true }
    channelRows = [
      {
        ...channel('CHANNEL-1', { supports_attachments: true }),
        provider: 'vk_direct',
        platform: 'vk',
        channel_type: 'vk',
      },
    ]
    conversationRows[0].provider = 'vk_direct'
    let root = await mountConversation()
    root.querySelector('[data-testid="mock-image-draft"]').click()
    await nextTick()
    let send = [...root.querySelectorAll('button')].find(
      (button) => button.textContent === 'Send',
    )
    return { root, send }
  }

  it('consumes the accepted image once and blocks concurrent sends', async () => {
    let request = deferred()
    let defaultCall = mocks.call.getMockImplementation()
    mocks.call.mockImplementation((method, args) =>
      method.endsWith('send_message')
        ? request.promise
        : defaultCall(method, args),
    )
    let { send } = await mountVKImageComposer()

    send.click()
    send.click()
    await vi.waitFor(() =>
      expect(
        mocks.call.mock.calls.filter(([method]) =>
          method.endsWith('send_message'),
        ),
      ).toHaveLength(1),
    )
    expect(send.disabled).toBe(true)
    expect(mocks.call).toHaveBeenCalledWith(
      'crm_messenger.api.messages.send_message',
      expect.objectContaining({
        attachments: ['FILE-photo.jpg'],
        client_request_id: expect.any(String),
      }),
    )

    request.resolve({ ok: true, name: 'VK-IMAGE-1', status: 'queued' })
    await vi.waitFor(() =>
      expect(mocks.attachmentRelease).toHaveBeenCalledOnce(),
    )
    expect(send.disabled).toBe(true)
    send.click()
    expect(
      mocks.call.mock.calls.filter(([method]) =>
        method.endsWith('send_message'),
      ),
    ).toHaveLength(1)
  })

  it('keeps the same request ID for a user retry after the CRM RPC response is lost', async () => {
    let defaultCall = mocks.call.getMockImplementation()
    mocks.call.mockImplementation(async (method, args) => {
      if (method.endsWith('send_message')) throw new Error('network error')
      return defaultCall(method, args)
    })
    let { root, send } = await mountVKImageComposer()
    send.click()
    await vi.waitFor(() => expect(mocks.toastError).toHaveBeenCalledOnce())
    expect(mocks.attachmentRelease).not.toHaveBeenCalled()
    await vi.waitFor(() => {
      send = [...root.querySelectorAll('button')].find(
        (button) => button.textContent === 'Send',
      )
      expect(send?.disabled).toBe(false)
    })
    let calls = mocks.call.mock.calls.filter(([method]) =>
      method.endsWith('send_message'),
    )
    expect(calls).toHaveLength(1)
    expect(mocks.attachmentUnmount).not.toHaveBeenCalled()

    send.click()
    await vi.waitFor(() => expect(mocks.toastError).toHaveBeenCalledTimes(2))
    calls = mocks.call.mock.calls.filter(([method]) =>
      method.endsWith('send_message'),
    )
    expect(calls).toHaveLength(2)
    expect(calls[1][1].client_request_id).toBe(calls[0][1].client_request_id)
    expect(calls[1][1].attachments).toEqual(calls[0][1].attachments)
    expect(mocks.attachmentUnmount).not.toHaveBeenCalled()
  })
})

describe('Wazzup ambiguous sends', () => {
  it.each([false, true])(
    'ignores stale Wazzup unknown retry events with confirmation=%s',
    async (requiresConfirmation) => {
      permissions = { ...permissions, can_operate: true }
      snapshotMessages = [
        {
          name: 'WAZZUP-UNKNOWN',
          provider: 'wazzup',
          channel: 'CHANNEL-1',
          conversation: 'CONVERSATION-1',
          direction: 'outbound',
          status: 'unknown',
          delivery_status: 'unknown',
          message_type: 'text',
          text: 'проверка',
          attachments: [],
          can_retry: true,
          retry_requires_confirmation: requiresConfirmation,
          message_datetime: '2026-10-22 10:56:00',
        },
      ]
      let root = await mountConversation()

      root.querySelector('[data-testid="mock-message-retry"]').click()
      await nextTick()

      expect(mocks.dialog).not.toHaveBeenCalled()
      expect(
        mocks.call.mock.calls.some(([method]) =>
          method.endsWith('retry_outbound_message'),
        ),
      ).toBe(false)
    },
  )
})

describe('locally disconnected conversation channels', () => {
  it.each([
    ['wazzup', 0],
    ['wazzup', false],
    ['telegram_bot', 0],
    ['telegram_bot', false],
  ])(
    'blocks the selected %s channel for enabled=%s while preserving history, sibling routing and resume',
    async (provider, disabled) => {
      permissions = { ...permissions, can_operate: true }
      const primary = { ...channel('CHANNEL-1'), provider, enabled: 1 }
      const sibling = { ...channel('CHANNEL-2'), provider, enabled: 1 }
      channelRows = [primary, sibling]
      conversationRows = [
        { ...conversationRows[0], provider, channel_info: primary },
        {
          name: 'CONVERSATION-2',
          channel: 'CHANNEL-2',
          provider,
          status: 'Open',
          external_chat_id: 'chat-2',
          channel_info: sibling,
        },
      ]
      snapshotMessages = [
        {
          name: 'PAUSED-CHANNEL-HISTORY',
          conversation: 'CONVERSATION-1',
          channel: 'CHANNEL-1',
          provider,
          direction: 'inbound',
          text: 'Saved history',
          message_datetime: '2026-08-23 10:00:00',
        },
      ]
      const root = await mountConversation()
      const composer = root.querySelector(
        'input[placeholder="Enter a message..."]',
      )
      const platform = root.querySelector('input[placeholder="Platform"]')
      const send = [...root.querySelectorAll('button')].find(
        (button) => button.textContent === 'Send',
      )
      composer.value = 'Keep this draft'
      composer.dispatchEvent(new Event('input'))
      await nextTick()
      expect(composer.disabled).toBe(false)
      expect(send.disabled).toBe(false)

      // The active-channel endpoint omits the paused channel; its known local
      // enable flag still arrives with the existing conversation's channel_info.
      channelRows = [sibling]
      conversationRows = conversationRows.map((conversation) =>
        conversation.channel === primary.name
          ? {
              ...conversation,
              channel_info: {
                ...primary,
                enabled: disabled,
                state: 'connected',
                wazzup_status: 'active',
              },
            }
          : conversation,
      )
      const refresh = [...root.querySelectorAll('button')].find(
        (button) => button.textContent === 'Refresh',
      )
      refresh.click()
      await vi.waitFor(() => expect(composer.disabled).toBe(true))
      expect(send.disabled).toBe(true)
      expect(composer.value).toBe('Keep this draft')
      expect(
        root.querySelector('[data-message-id="PAUSED-CHANNEL-HISTORY"]'),
      ).not.toBeNull()
      expect(platform.disabled).toBe(false)

      platform.value = sibling.name
      platform.dispatchEvent(new Event('input'))
      await vi.waitFor(() => expect(composer.disabled).toBe(false))
      expect(send.disabled).toBe(false)
      expect(composer.value).toBe('Keep this draft')

      channelRows = [primary, sibling]
      conversationRows = conversationRows.map((conversation) =>
        conversation.channel === primary.name
          ? { ...conversation, channel_info: primary }
          : conversation,
      )
      const previousLoads = mocks.call.mock.calls.filter(([method]) =>
        method.endsWith('get_channels'),
      ).length
      refresh.click()
      await vi.waitFor(() =>
        expect(
          mocks.call.mock.calls.filter(([method]) =>
            method.endsWith('get_channels'),
          ).length,
        ).toBeGreaterThan(previousLoads),
      )
      platform.value = primary.name
      platform.dispatchEvent(new Event('input'))
      await vi.waitFor(() => expect(platform.value).toBe(primary.name))
      await nextTick()
      expect(composer.disabled).toBe(false)
      expect(send.disabled).toBe(false)
      expect(composer.value).toBe('Keep this draft')
      expect(
        root.querySelector('[data-message-id="PAUSED-CHANNEL-HISTORY"]'),
      ).not.toBeNull()
      expect(
        mocks.call.mock.calls.some(([method]) =>
          method.endsWith('send_message'),
        ),
      ).toBe(false)
    },
  )

  it('keeps older partial channel DTOs without enabled usable even when can_send is not authoritative', async () => {
    permissions = { ...permissions, can_operate: true }
    const partial = {
      ...channel('CHANNEL-1'),
      provider: 'wazzup',
      can_send: false,
    }
    channelRows = [partial, { ...channel('CHANNEL-2'), enabled: 1 }]
    conversationRows[0] = {
      ...conversationRows[0],
      provider: 'wazzup',
      channel_info: partial,
    }
    const root = await mountConversation()
    const composer = root.querySelector(
      'input[placeholder="Enter a message..."]',
    )
    expect(composer.disabled).toBe(false)
    composer.value = 'A partial DTO still permits composing'
    composer.dispatchEvent(new Event('input'))
    await nextTick()
    expect(
      [...root.querySelectorAll('button')].find(
        (button) => button.textContent === 'Send',
      ).disabled,
    ).toBe(false)
  })
})

describe('Wazzup native text replies', () => {
  function wazzupChannel(platform) {
    return {
      ...channel('CHANNEL-1', { requires_phone: true }),
      provider: 'wazzup',
      platform,
      channel_type: platform,
    }
  }

  it.each(['whatsapp', 'telegram'])(
    'sends to an existing Wazzup %s chat without a phone on the lead',
    async (platform) => {
      permissions = { ...permissions, can_operate: true }
      channelRows = [wazzupChannel(platform)]
      conversationRows[0].provider = 'wazzup'
      let root = await mountConversation()
      let composer = root.querySelector(
        'input[placeholder="Enter a message..."]',
      )

      expect(composer.disabled).toBe(false)
      composer.value = 'Ответ в существующий чат'
      composer.dispatchEvent(new Event('input'))
      await nextTick()
      let send = [...root.querySelectorAll('button')].find(
        (button) => button.textContent === 'Send',
      )
      expect(send.disabled).toBe(false)
      send.click()

      await vi.waitFor(() =>
        expect(mocks.call).toHaveBeenCalledWith(
          'crm_messenger.api.messages.send_message',
          expect.objectContaining({
            conversation: 'CONVERSATION-1',
            channel: 'CHANNEL-1',
            text: 'Ответ в существующий чат',
          }),
        ),
      )
    },
  )

  it('keeps first contact blocked without a phone or an existing Wazzup chat', async () => {
    permissions = { ...permissions, can_operate: true }
    channelRows = [wazzupChannel('telegram')]
    conversationRows = []
    let root = await mountConversation()

    expect(
      root.querySelector('input[placeholder="Enter a message..."]').disabled,
    ).toBe(true)
    expect(root.textContent).toContain('Add a phone number to the lead record.')
    expect(
      mocks.call.mock.calls.some(([method]) => method.endsWith('send_message')),
    ).toBe(false)
  })

  it.each([
    ['wazzup', false],
    ['telegram_bot', true],
  ])(
    'shows the file drop invitation only for an attachment-capable %s channel',
    async (provider, supportsAttachments) => {
      permissions = { ...permissions, can_operate: true }
      channelRows = [
        {
          ...channel('CHANNEL-1', {
            supports_attachments: supportsAttachments,
          }),
          provider,
        },
      ]
      let root = await mountConversation()
      let event = new Event('dragover', { bubbles: true, cancelable: true })
      Object.defineProperty(event, 'dataTransfer', {
        value: { types: ['Files'] },
      })

      root
        .querySelector('input[placeholder="Enter a message..."]')
        .dispatchEvent(event)
      await nextTick()

      expect(event.defaultPrevented).toBe(true)
      expect(root.textContent.includes('Drop files here')).toBe(
        supportsAttachments,
      )
    },
  )

  function mediaChannel(platform) {
    return {
      ...wazzupChannel(platform),
      capabilities: {
        ...wazzupChannel(platform).capabilities,
        supports_attachments: true,
        supported_attachment_types: ['image', 'file', 'audio', 'video'],
        supported_attachment_file_types_by_type: { video: ['.mp4'] },
        max_attachment_count: 1,
        max_attachment_size_bytes: 10_000_000,
        max_attachment_size_bytes_by_type:
          platform === 'telegram' ? { image: 5_000_000 } : {},
        supports_attachment_captions: false,
        supports_image_caption: false,
      },
    }
  }

  it.each(['whatsapp', 'telegram'])(
    'keeps Wazzup %s text and file drafts separate without discarding either',
    async (platform) => {
      permissions = { ...permissions, can_operate: true }
      channelRows = [mediaChannel(platform)]
      let root = await mountConversation()
      expect(
        root.querySelector('[aria-label="Record a Voice Message"]'),
      ).toBeNull()
      expect(root.querySelector('[aria-label="Add Location"]')).toBeNull()
      let policy = root.querySelector('[data-attachment-policy]')
      expect(policy.dataset.maxSize).toBe('10000000')
      expect(policy.dataset.maxFiles).toBe('1')
      expect(policy.dataset.videoFormats).toBe('.mp4')
      expect(policy.dataset.imageMaxSize).toBe(
        platform === 'telegram' ? '5000000' : undefined,
      )
      let composer = root.querySelector(
        'input[placeholder="Enter a message..."]',
      )
      composer.value = 'Keep this text'
      composer.dispatchEvent(new Event('input'))
      root.querySelector('[data-testid="mock-attachment-draft"]').click()
      await nextTick()
      let send = [...root.querySelectorAll('button')].find(
        (button) => button.textContent === 'Send',
      )

      expect(composer.disabled).toBe(false)
      expect(composer.value).toBe('Keep this text')
      expect(send.disabled).toBe(true)
      expect(root.textContent).toContain(
        'This channel cannot send text and an attachment together. Send them as separate messages.',
      )
      expect(root.textContent).not.toContain('Avito API')
      composer.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
      send.click()
      await nextTick()
      expect(
        mocks.call.mock.calls.some(([method]) =>
          method.endsWith('send_message'),
        ),
      ).toBe(false)

      root.querySelector('[data-testid="mock-clear-attachments"]').click()
      await nextTick()
      expect(composer.value).toBe('Keep this text')
      expect(send.disabled).toBe(false)
      root.querySelector('[data-testid="mock-attachment-draft"]').click()
      await nextTick()
      composer.value = ''
      composer.dispatchEvent(new Event('input'))
      await nextTick()
      expect(composer.disabled).toBe(true)
      expect(composer.placeholder).toBe(
        'Text and attachments must be sent separately.',
      )
      expect(send.disabled).toBe(false)
      send.click()

      await vi.waitFor(() =>
        expect(mocks.call).toHaveBeenCalledWith(
          'crm_messenger.api.messages.send_message',
          expect.objectContaining({
            text: '',
            attachments: ['FILE-draft.pdf'],
          }),
        ),
      )
      let sends = mocks.call.mock.calls.filter(([method]) =>
        method.endsWith('send_message'),
      )
      expect(sends).toHaveLength(1)
      expect(sends[0][1].location).toBeUndefined()
      expect(
        mocks.call.mock.calls.some(([method]) =>
          method.endsWith('send_voice_message'),
        ),
      ).toBe(false)
    },
  )

  it.each([
    ['max_direct', 'max'],
    ['vk_direct', 'vk'],
    ['telegram_bot', 'telegram'],
  ])(
    'preserves supported captions, recorder and location for %s',
    async (provider, platform) => {
      permissions = { ...permissions, can_operate: true }
      channelRows = [
        {
          ...channel('CHANNEL-1', {
            supports_attachments: true,
            supported_attachment_types: ['image', 'file', 'audio', 'video'],
            supports_attachment_captions: true,
            supports_image_caption: true,
            voice: { send: true },
            location: { send: true },
          }),
          provider,
          platform,
          channel_type: platform,
        },
      ]
      let root = await mountConversation()
      expect(
        root.querySelector('[aria-label="Record a Voice Message"]'),
      ).not.toBeNull()
      expect(root.querySelector('[aria-label="Add Location"]')).not.toBeNull()
      let composer = root.querySelector(
        'input[placeholder="Enter a message..."]',
      )
      composer.value = 'An attachment caption'
      composer.dispatchEvent(new Event('input'))
      root.querySelector('[data-testid="mock-attachment-draft"]').click()
      await nextTick()
      let send = [...root.querySelectorAll('button')].find(
        (button) => button.textContent === 'Send',
      )

      expect(send.disabled).toBe(false)
      expect(
        root.querySelector('[data-testid="image-caption-warning"]'),
      ).toBeNull()
      send.click()

      await vi.waitFor(() =>
        expect(mocks.call).toHaveBeenCalledWith(
          'crm_messenger.api.messages.send_message',
          expect.objectContaining({
            text: 'An attachment caption',
            attachments: ['FILE-draft.pdf'],
          }),
        ),
      )
      expect(
        mocks.call.mock.calls.filter(([method]) =>
          method.endsWith('send_message'),
        ),
      ).toHaveLength(1)
    },
  )

  it.each(['whatsapp', 'telegram'])(
    'sends a Wazzup %s quoted reply using the local original message id',
    async (platform) => {
      permissions = { ...permissions, can_operate: true }
      channelRows = [mediaChannel(platform)]
      snapshotMessages = [
        {
          name: 'WAZZUP-ORIGINAL',
          external_message_id: 'provider-original-id',
          provider: 'wazzup',
          channel: 'CHANNEL-1',
          conversation: 'CONVERSATION-1',
          direction: 'inbound',
          status: 'received',
          message_type: 'image',
          text: '',
          attachments: [{ id: 'IMAGE-1', type: 'image', status: 'available' }],
          can_reply: true,
          message_datetime: '2026-10-02 10:00:00',
        },
      ]
      let defaultCall = mocks.call.getMockImplementation()
      mocks.call.mockImplementation((method, args) => {
        if (method.endsWith('resolve_send_target'))
          return { ok: true, conversation: conversationRows[0] }
        return defaultCall(method, args)
      })
      let root = await mountConversation()
      root.querySelector('[data-testid="mock-message-reply"]').click()
      await nextTick()
      let composer = root.querySelector(
        'input[placeholder="Enter a message..."]',
      )
      composer.value = 'Reply to the photo'
      composer.dispatchEvent(new Event('input'))
      await nextTick()
      ;[...root.querySelectorAll('button')]
        .find((button) => button.textContent === 'Send')
        .click()

      await vi.waitFor(() =>
        expect(mocks.call).toHaveBeenCalledWith(
          'crm_messenger.api.messages.send_message',
          expect.objectContaining({
            conversation: 'CONVERSATION-1',
            text: 'Reply to the photo',
            reply_to_message: 'WAZZUP-ORIGINAL',
          }),
        ),
      )
      expect(mocks.call).toHaveBeenCalledWith(
        'crm_messenger.api.conversations.resolve_send_target',
        expect.objectContaining({ reply_to_message: 'WAZZUP-ORIGINAL' }),
      )
    },
  )

  it.each([
    [
      'static sticker',
      { type: 'image', mime_type: 'image/webp', is_sticker_candidate: true },
      'Sticker',
    ],
    [
      'ordinary WebP image',
      { type: 'image', mime_type: 'image/webp' },
      'Image',
    ],
    [
      'animated sticker',
      {
        type: 'sticker',
        mime_type: 'application/x-tgsticker',
        is_animated: true,
      },
      'Sticker',
    ],
  ])(
    'labels a Wazzup %s correctly in the reply composer',
    async (_kind, attachment, label) => {
      permissions = { ...permissions, can_operate: true }
      channelRows = [mediaChannel('telegram')]
      snapshotMessages = [
        {
          name: 'WAZZUP-ORIGINAL',
          provider: 'wazzup',
          channel: 'CHANNEL-1',
          conversation: 'CONVERSATION-1',
          direction: 'inbound',
          status: 'received',
          message_type: attachment.type,
          text: '',
          attachments: [{ id: 'MEDIA-1', status: 'available', ...attachment }],
          can_reply: true,
          message_datetime: '2026-10-25 10:00:00',
        },
      ]
      let root = await mountConversation()
      root.querySelector('[data-testid="mock-message-reply"]').click()
      await nextTick()
      expect(
        root.querySelector('[data-message-reply-quote]').textContent,
      ).toContain(label)
    },
  )
})

describe('Avito messenger UX', () => {
  function avitoChannel() {
    return {
      name: 'CHANNEL-1',
      provider: 'avito_direct',
      platform: 'avito',
      channel_type: 'avito',
      capabilities: {
        supports_attachments: true,
        supported_attachment_types: ['image'],
        max_attachment_count: 1,
        requires_inbound: true,
        requires_phone: false,
        voice: { send: false },
        location: { send: false },
        reactions: { receive: false, send: false },
        video: {},
      },
    }
  }

  it('opens an Avito unknown retry dialog without VK request ID copy', async () => {
    permissions = { ...permissions, can_operate: true }
    channelRows = [avitoChannel()]
    snapshotMessages = [
      {
        name: 'MESSAGE-UNKNOWN',
        provider: 'avito_direct',
        channel: 'CHANNEL-1',
        conversation: 'CONVERSATION-1',
        direction: 'outbound',
        status: 'unknown',
        delivery_status: 'unknown',
        message_type: 'text',
        text: 'проверка',
        attachments: [],
        can_retry: true,
        retry_requires_confirmation: true,
        message_datetime: '2026-09-14 10:56:00',
      },
    ]
    let root = await mountConversation()

    root.querySelector('[data-testid="mock-message-retry"]').click()

    expect(mocks.dialog).toHaveBeenCalledOnce()
    let dialog = mocks.dialog.mock.calls[0][0]
    expect(dialog.title).toBe('Retry sending?')
    expect(dialog.message).toContain('Avito may have accepted')
    expect(dialog.message).toContain('may create a duplicate')
    expect(dialog.message).not.toContain('VK')
    expect(dialog.message).not.toContain('same request ID')
  })

  it('lets the user clear an existing draft while an Avito image blocks caption sending', async () => {
    permissions = { ...permissions, can_operate: true }
    channelRows = [avitoChannel()]
    let root = await mountConversation()
    let composer = root.querySelector('input[placeholder="Enter a message..."]')
    composer.value = 'Send this separately'
    composer.dispatchEvent(new Event('input'))
    await nextTick()

    root.querySelector('[data-testid="mock-image-draft"]').click()
    await nextTick()

    expect(composer.disabled).toBe(false)
    expect(composer.value).toBe('Send this separately')
    expect(
      root.querySelector('[data-testid="image-caption-warning"]'),
    ).not.toBeNull()
    expect(root.textContent).toContain(
      'Avito API does not support image captions. Send the text as a separate message.',
    )
    let send = [...root.querySelectorAll('button')].find(
      (button) => button.textContent === 'Send',
    )
    expect(send.disabled).toBe(true)

    root.querySelector('[data-testid="mock-clear-attachments"]').click()
    await nextTick()

    expect(composer.disabled).toBe(false)
    expect(composer.value).toBe('Send this separately')
    expect(
      root.querySelector('[data-testid="image-caption-warning"]'),
    ).toBeNull()

    root.querySelector('[data-testid="mock-image-draft"]').click()
    await nextTick()

    composer.value = ''
    composer.dispatchEvent(new Event('input'))
    await nextTick()

    expect(composer.disabled).toBe(true)
    expect(composer.value).toBe('')
    expect(
      root.querySelector('[data-testid="image-caption-warning"]'),
    ).toBeNull()
    expect(send.disabled).toBe(false)

    root.querySelector('[data-testid="mock-clear-attachments"]').click()
    await nextTick()

    expect(composer.disabled).toBe(false)
    expect(composer.value).toBe('')
    expect(
      root.querySelector('[data-testid="image-caption-warning"]'),
    ).toBeNull()
  })

  it('disables an empty Avito image caption without showing a warning', async () => {
    permissions = { ...permissions, can_operate: true }
    channelRows = [avitoChannel()]
    let root = await mountConversation()
    let composer = root.querySelector('input[placeholder="Enter a message..."]')

    root.querySelector('[data-testid="mock-image-draft"]').click()
    await nextTick()

    expect(composer.disabled).toBe(true)
    expect(composer.value).toBe('')
    expect(composer.placeholder).toBe(
      'Image captions are unavailable for Avito.',
    )
    expect(
      root.querySelector('[data-testid="image-caption-warning"]'),
    ).toBeNull()
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

  it('names both Avito listings when routing between conversations of one account', async () => {
    prepareRoutingFixture()
    channelRows = [
      {
        ...channel('CHANNEL-1'),
        provider: 'avito_direct',
        platform: 'avito',
        channel_type: 'avito',
        label: 'Avito shop',
      },
    ]
    conversationRows = [1, 2].map((id) => ({
      name: `CONVERSATION-${id}`,
      channel: 'CHANNEL-1',
      status: 'Open',
      provider: 'avito_direct',
      external_chat_id: `chat-${id}`,
      avito_item: { id: `${id}`, title: id === 1 ? 'Bicycle' : 'Scooter' },
    }))
    latestInbound.channel = 'CHANNEL-1'
    let root = await mountConversation()
    expect(
      root.querySelector('[data-testid="avito-item-card"]').textContent,
    ).toContain('Scooter')
    let selector = root.querySelector('input[placeholder="External Chat"]')
    selector.value = 'CONVERSATION-1'
    selector.dispatchEvent(new Event('input'))
    await nextTick()
    let warning = root.querySelector(
      '[data-testid="conversation-routing-warning"]',
    )
    expect(warning.textContent).toContain('Scooter · #2 · CONVERSATION-2')
    expect(warning.textContent).toContain('Bicycle · #1 · CONVERSATION-1')
    expect(
      root.querySelector('[data-testid="avito-item-card"]').textContent,
    ).toContain('Bicycle')
    root.querySelector('[data-testid="conversation-routing-switch"]').click()
    await nextTick()
    await nextTick()
    expect(
      root.querySelector('[data-testid="conversation-routing-warning"]'),
    ).toBeNull()
    expect(
      root.querySelector('[data-testid="avito-item-card"]').textContent,
    ).toContain('Scooter')
    expect(
      mocks.call.mock.calls.some(([method]) => method.endsWith('send_message')),
    ).toBe(false)
  })

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

  it.each([
    ['telegram_bot', 'telegram', 'Telegram - Support Bot'],
    ['max_direct', 'max', 'MAX - Support Bot'],
    ['vk_direct', 'vk', 'VK - Support Bot'],
  ])(
    'constrains metadata intrinsic width for a %s generic file-only message',
    async (provider, platform, label) => {
      channelRows = [
        {
          ...channel('CHANNEL-1'),
          provider,
          platform,
          channel_type: platform,
          label,
        },
      ]
      snapshotMessages = [
        {
          name: `MESSAGE-${provider}`,
          provider,
          channel: 'CHANNEL-1',
          conversation: 'CONVERSATION-1',
          direction: 'outbound',
          status: 'sent',
          text: '',
          attachments: [{ id: 'FILE-1', type: 'file' }],
          message_datetime: '2026-09-14 10:56:00',
        },
      ]

      let root = await mountConversation()
      let metadata = root.querySelector('[data-message-metadata]')

      expect(metadata.className.split(/\s+/)).toEqual(
        expect.arrayContaining(['w-0', 'min-w-full']),
      )
    },
  )

  it.each(['wazzup', 'vk_direct', 'telegram_bot', 'max_direct'])(
    'keeps sender and channel in the intrinsic width of a short %s reply',
    async (provider) => {
      snapshotMessages = [
        {
          name: 'SHORT-REPLY',
          provider,
          channel: 'CHANNEL-1',
          conversation: 'CONVERSATION-1',
          direction: 'outbound',
          status: 'sent',
          text: 'Ок',
          attachments: [],
          reply_context: {
            state: 'available',
            message: 'ORIGINAL',
            snapshot: { attachment_types: ['image'] },
          },
          message_datetime: '2026-09-14 10:56:00',
        },
      ]
      let root = await mountConversation()
      expect(root.querySelector('[data-message-reply-quote]')).not.toBeNull()
      expect(
        root.querySelector('[data-message-metadata]').classList.contains('w-0'),
      ).toBe(false)
      expect(root.querySelector('[data-message-bubble]').className).toContain(
        'min-w-[min(18rem,94%)]',
      )
    },
  )

  it.each(['wazzup', 'vk_direct', 'telegram_bot', 'max_direct'])(
    'hides the original quote in a deleted %s reply bubble',
    async (provider) => {
      snapshotMessages = [
        {
          name: 'DELETED-REPLY',
          provider,
          channel: 'CHANNEL-1',
          conversation: 'CONVERSATION-1',
          direction: 'outbound',
          status: 'deleted',
          text: null,
          attachments: [],
          reply_context: {
            state: 'available',
            message: 'ORIGINAL',
            snapshot: { text: 'Original quoted text', direction: 'outbound' },
          },
          message_datetime: '2026-10-25 10:00:00',
        },
      ]
      let root = await mountConversation()
      expect(root.querySelector('[data-message-reply-quote]')).toBeNull()
      expect(root.textContent).not.toContain('Original quoted text')
      expect(
        root.querySelector('[data-message-bubble]').className,
      ).not.toContain('min-w-[min(18rem,94%)]')
    },
  )

  it('hides the technical VK photo upload reason below the message bubble', async () => {
    channelRows = [
      {
        ...channel('CHANNEL-1'),
        provider: 'vk_direct',
        platform: 'vk',
        channel_type: 'vk',
      },
    ]
    snapshotMessages = [
      {
        name: 'MESSAGE-VK-FAILED-PHOTO',
        provider: 'vk_direct',
        channel: 'CHANNEL-1',
        conversation: 'CONVERSATION-1',
        direction: 'outbound',
        status: 'failed',
        delivery_status: 'failed',
        message_type: 'image',
        text: '',
        failure_reason: 'VK photo upload did not return photo data.',
        attachments: [
          {
            id: 'IMAGE-1',
            type: 'image',
            status: 'failed',
            url: '/api/method/crm_messenger.api.attachments.stream_file',
          },
        ],
        message_datetime: '2026-09-15 10:00:00',
      },
    ]

    let root = await mountConversation()

    expect(root.textContent).toContain(
      'Could not upload the image to VK. Try sending it again.',
    )
    expect(root.textContent).not.toContain(
      'VK photo upload did not return photo data.',
    )
  })

  it.each(['error', 'not_configured'])(
    'ignores a late %s from a send started on another Lead',
    async (outcome) => {
      prepareRoutingFixture()
      let oldSend = deferred()
      let defaultCall = mocks.call.getMockImplementation()
      mocks.call.mockImplementation((method, args) => {
        if (method.endsWith('send_message') && args.reference_name === 'LEAD-1')
          return oldSend.promise
        return defaultCall(method, args)
      })
      let root = await mountConversation()
      let composer = root.querySelector(
        'input[placeholder="Enter a message..."]',
      )
      composer.value = 'Message from A'
      composer.dispatchEvent(new Event('input'))
      await nextTick()
      sendButton(root).click()
      await vi.waitFor(() =>
        expect(mocks.call).toHaveBeenCalledWith(
          'crm_messenger.api.messages.send_message',
          expect.objectContaining({
            reference_name: 'LEAD-1',
            text: 'Message from A',
          }),
        ),
      )

      mounted.at(-1).props.leadName = 'LEAD-2'
      await vi.waitFor(() => expect(sendButton(root)?.disabled).toBe(true))
      if (outcome === 'error') oldSend.reject(new Error('Old Lead send error'))
      else oldSend.resolve({ ok: false, reason: 'not_configured' })
      await vi.waitFor(() =>
        expect(
          root.querySelector('input[placeholder="Enter a message..."]')
            ?.disabled,
        ).toBe(false),
      )
      expect(root.textContent).not.toContain('Old Lead send error')
      expect(root.textContent).not.toContain('not configured')
      expect(mocks.toastError).not.toHaveBeenCalled()

      composer = root.querySelector('input[placeholder="Enter a message..."]')
      composer.value = 'Message from B'
      composer.dispatchEvent(new Event('input'))
      await nextTick()
      sendButton(root).click()
      await vi.waitFor(() =>
        expect(mocks.call).toHaveBeenCalledWith(
          'crm_messenger.api.messages.send_message',
          expect.objectContaining({
            reference_name: 'LEAD-2',
            text: 'Message from B',
          }),
        ),
      )
    },
  )

  it('does not send after a stale Lead target resolution', async () => {
    permissions = { ...permissions, can_operate: true }
    conversationRows = []
    let oldTarget = deferred()
    let defaultCall = mocks.call.getMockImplementation()
    mocks.call.mockImplementation((method, args) => {
      if (
        method.endsWith('resolve_send_target') &&
        args.reference_name === 'LEAD-1'
      )
        return oldTarget.promise
      return defaultCall(method, args)
    })
    let root = await mountConversation()
    let composer = root.querySelector('input[placeholder="Enter a message..."]')
    composer.value = 'Old Lead draft'
    composer.dispatchEvent(new Event('input'))
    await nextTick()
    sendButton(root).click()
    await vi.waitFor(() =>
      expect(mocks.call).toHaveBeenCalledWith(
        'crm_messenger.api.conversations.resolve_send_target',
        expect.objectContaining({ reference_name: 'LEAD-1' }),
      ),
    )

    mounted.at(-1).props.leadName = 'LEAD-2'
    await nextTick()
    oldTarget.resolve({
      ok: true,
      conversation: { name: 'OLD-CONVERSATION', channel: 'CHANNEL-1' },
    })
    await vi.waitFor(() =>
      expect(
        root.querySelector('input[placeholder="Enter a message..."]')?.disabled,
      ).toBe(false),
    )
    expect(
      mocks.call.mock.calls.some(([method]) => method.endsWith('send_message')),
    ).toBe(false)
    expect(root.textContent).not.toContain('OLD-CONVERSATION')
    expect(mocks.toastError).not.toHaveBeenCalled()
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

  it('reads the current user’s Messenger notification through the chat read boundary', async () => {
    permissions = { ...permissions, can_operate: true }
    snapshotMessages = [
      {
        name: 'MESSAGE-INBOUND-1',
        conversation: 'CONVERSATION-1',
        direction: 'inbound',
        status: 'received',
        ingest_source: 'provider_webhook',
        message_datetime: '2026-08-23 12:00:00',
        local_inbound_sequence: 1,
      },
    ]

    await mountConversation()

    await vi.waitFor(() =>
      expect(mocks.call).toHaveBeenCalledWith(
        'crm_messenger.api.conversations.mark_read',
        {
          conversation: 'CONVERSATION-1',
          up_to_message: 'MESSAGE-INBOUND-1',
        },
      ),
    )
  })

  it('does not read Messenger notifications while the tab is inactive', async () => {
    permissions = { ...permissions, can_operate: true }
    snapshotMessages = [
      {
        name: 'MESSAGE-INBOUND-1',
        conversation: 'CONVERSATION-1',
        direction: 'inbound',
        status: 'received',
        ingest_source: 'provider_webhook',
        message_datetime: '2026-08-23 12:00:00',
        local_inbound_sequence: 1,
      },
    ]

    await mountConversation({ active: false })

    expect(
      mocks.call.mock.calls.some(([method]) => method.endsWith('mark_read')),
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
