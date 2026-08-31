import { createApp, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => {
  let handlers = new Map()
  return {
    call: vi.fn(),
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
  globalStore: () => ({ $dialog: vi.fn(), $socket: mocks.socket }),
}))
vi.mock('@/stores/users', () => ({
  usersStore: () => ({
    getUser: (name) => ({ name, full_name: 'Оператор Тестов' }),
  }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
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
    methods: {
      discard() {},
      freeze() {
        return []
      },
      unfreeze() {},
      release() {},
      openFileSelector() {},
    },
    template: '<span />',
  },
}))
vi.mock('@/components/LeadMessenger/ComposerVoiceRecorder.vue', () => ({
  default: {
    methods: { reset() {}, start() {} },
    template: '<span />',
  },
}))

import LeadConversation from '@/components/LeadMessenger/LeadConversation.vue'

let mounted = []
let permissions
let preparedResult
let snapshotMessages

const channel = (name) => ({
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
  mocks.socket.reset()
  vi.clearAllMocks()
  mocks.call.mockImplementation(async (method) => {
    if (method.endsWith('get_channels')) {
      return {
        ok: true,
        channels: [channel('CHANNEL-1'), channel('CHANNEL-2')],
        permissions,
      }
    }
    if (method.endsWith('get_conversations')) {
      return {
        ok: true,
        conversations: [
          {
            name: 'CONVERSATION-1',
            channel: 'CHANNEL-1',
            status: 'Open',
            external_chat_id: 'chat-1',
          },
        ],
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
