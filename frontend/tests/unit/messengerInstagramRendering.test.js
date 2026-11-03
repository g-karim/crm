import { createApp, h, nextTick, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/utils', () => ({
  formatDate: (value, format) => (format === 'HH:mm' ? '12:00' : value),
}))

vi.mock('frappe-ui', () => ({
  Button: { template: '<button><slot /></button>' },
  Textarea: { template: '<textarea />' },
  FeatherIcon: { template: '<svg />' },
  Tooltip: {
    props: ['text'],
    template: '<span data-test-tooltip :title="text"><slot /></span>',
  },
}))

import AttachmentRenderer from '@/components/LeadMessenger/AttachmentRenderer.vue'
import MessageContent from '@/components/LeadMessenger/MessageContent.vue'
import MessageFooterMetadata from '@/components/LeadMessenger/MessageFooterMetadata.vue'
import { shouldShowMessengerMessageText } from '@/utils/messengerMessagePresentation'
import { createMessengerSyncController } from '@/utils/messengerSync'

let mounted = []
let controllers = []

afterEach(() => {
  controllers.forEach((controller) => controller.stop())
  controllers = []
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
})

function message(platform = 'instagram', overrides = {}) {
  return {
    name: 'MSG-INBOUND',
    provider: 'wazzup',
    platform,
    channel: `CHANNEL-${platform}`,
    conversation: `CONVERSATION-${platform}`,
    channel_info: { platform, wazzup_api_mode: 'partner_api_v2' },
    external_chat_id: 'opaque-instagram-thread:001',
    external_message_id: 'opaque-provider-message:001',
    direction: 'inbound',
    message_type: 'text',
    text: 'An incoming Direct message',
    status: 'received',
    message_datetime: '2026-11-03 12:00:00.001000',
    creation: '2026-11-03 12:00:00.002000',
    modified: '2026-11-03 12:00:00.003000',
    attachments: [],
    ...overrides,
  }
}

function image(overrides = {}) {
  return {
    id: 'IMAGE-1',
    type: 'image',
    mime_type: 'image/jpeg',
    status: 'available',
    url: '/private/files/direct-image.jpg',
    width: 640,
    height: 640,
    ...overrides,
  }
}

function mountMessages(messages) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  // Use the same shared message, attachment and footer components as
  // LeadConversation; platform-specific rendering is intentionally unnecessary.
  let app = createApp({
    render: () =>
      h(
        'div',
        messages.value.map((item) =>
          h('article', { key: item.name, 'data-message': item.name }, [
            h(MessageContent, {
              message: item,
              shouldShowText: shouldShowMessengerMessageText(item),
            }),
            h(AttachmentRenderer, {
              attachments: item.attachments,
              provider: item.provider,
              outbound: item.direction === 'outbound',
            }),
            h(MessageFooterMetadata, { message: item }),
          ]),
        ),
      ),
  })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return root
}

describe('Instagram through the shared Messenger renderers', () => {
  it.each(['instagram', 'whatsapp', 'telegram', 'max', 'viber'])(
    'renders existing %s text and incoming attachments without a phone',
    (platform) => {
      let incoming = message(platform, {
        attachments: [
          image(),
          {
            id: 'FILE-1',
            type: 'file',
            status: 'available',
            original_file_name: 'Direct document.pdf',
            file_name: 'provider-generated-file.pdf',
            download_url: '/api/method/mock_download?attachment=FILE-1',
          },
        ],
      })
      let original = structuredClone(incoming)
      let root = mountMessages(ref([incoming]))

      expect(root.textContent).toContain('An incoming Direct message')
      expect(
        root.querySelector('[data-single-image] img').getAttribute('src'),
      ).toBe('/private/files/direct-image.jpg')
      expect(
        root.querySelector('[data-attachment-card-title]').textContent,
      ).toContain('Direct document.pdf')
      expect(
        root.querySelector('a[data-attachment-card]').getAttribute('href'),
      ).toBe('/api/method/mock_download?attachment=FILE-1')
      expect(root.querySelector('[data-message-time]').textContent).toBe(
        '12:00',
      )
      expect(root.querySelector('[data-message-delivery]')).toBeNull()
      expect(incoming).toEqual(original)
    },
  )

  it.each([
    ['accepted', 'Awaiting provider status', 'text-ink-gray-5'],
    ['sent', 'Sent', 'text-ink-gray-5'],
    ['delivered', 'Delivered', 'text-ink-gray-5'],
    ['read', 'Read by recipient', 'text-ink-blue-5'],
    ['failed', 'Delivery failed', 'text-ink-red-8'],
    ['unknown', 'Result unknown', 'text-ink-red-8'],
  ])(
    'renders canonical Instagram %s delivery status',
    (state, label, color) => {
      let root = mountMessages(
        ref([
          message('instagram', {
            direction: 'outbound',
            status: state,
            delivery_status: state,
            attachments: [image({ mime_type: 'image/bmp' })],
          }),
        ]),
      )

      let delivery = root.querySelector('[data-message-delivery]')
      expect(delivery.className).toContain(color)
      expect(delivery.closest('[data-test-tooltip]').title).toBe(label)
      expect(root.querySelector('[data-single-image]')).not.toBeNull()
    },
  )

  it('keeps unconfirmed historical Instagram delivery free of a send indicator', () => {
    let root = mountMessages(
      ref([
        message('instagram', {
          direction: 'outbound',
          status: 'accepted',
          delivery_status: 'accepted',
          ingest_source: 'provider_history',
          attempt_count: 0,
        }),
      ]),
    )

    expect(root.querySelector('[data-message-time]')).not.toBeNull()
    expect(root.querySelector('[data-message-delivery]')).toBeNull()
  })

  it('applies mocked snapshot and delta updates without dropping Instagram identity or duplicating messages', async () => {
    let incoming = message('instagram', {
      text: '',
      message_type: 'image',
      attachments: [image({ status: 'pending', url: null })],
    })
    let outgoing = message('instagram', {
      name: 'MSG-OUTBOUND',
      direction: 'outbound',
      status: 'accepted',
      delivery_status: 'accepted',
      text: 'A reply in Direct',
    })
    let receivedImage = {
      ...incoming,
      attachments: [image()],
      modified: '2026-11-03 12:00:01.000001',
    }
    let read = {
      ...outgoing,
      status: 'read',
      delivery_status: 'read',
      modified: '2026-11-03 12:00:02.000001',
    }
    let call = vi.fn(async (method) => {
      if (method.endsWith('.get_message_page')) {
        return {
          contract_version: 1,
          messages: [incoming, outgoing],
          page: { has_more: false },
          sync_cursor: 'snapshot-cursor',
        }
      }
      if (method.endsWith('.get_message_changes')) {
        return {
          contract_version: 1,
          changes: [receivedImage, read, receivedImage],
          next_cursor: 'delta-cursor',
          has_more: false,
        }
      }
      throw new Error('Unexpected mock API method')
    })
    let messages = ref([])
    let controller = createMessengerSyncController({
      call,
      onChange: (change) => (messages.value = change.messages),
    })
    controllers.push(controller)
    let root = mountMessages(messages)

    await controller.start('LEAD-INSTAGRAM-WITHOUT-PHONE')
    await nextTick()
    expect(root.querySelectorAll('[data-message]')).toHaveLength(2)
    expect(root.querySelector('[data-image-loading]')).not.toBeNull()
    expect(root.querySelector('[data-single-image] img')).toBeNull()
    expect(
      root
        .querySelector('[data-message-delivery]')
        .closest('[data-test-tooltip]').title,
    ).toBe('Awaiting provider status')

    await controller.syncDelta()
    await nextTick()
    expect(root.querySelectorAll('[data-message]')).toHaveLength(2)
    expect(
      root.querySelector('[data-single-image] img').getAttribute('src'),
    ).toBe('/private/files/direct-image.jpg')
    expect(
      root
        .querySelector('[data-message-delivery]')
        .closest('[data-test-tooltip]').title,
    ).toBe('Read by recipient')
    expect(controller.getMessages()).toEqual([receivedImage, read])
    expect(
      controller
        .getMessages()
        .every(
          (item) =>
            item.platform === 'instagram' &&
            item.channel_info.platform === 'instagram' &&
            item.external_chat_id === 'opaque-instagram-thread:001' &&
            !item.phone,
        ),
    ).toBe(true)
    expect(call).toHaveBeenCalledTimes(2)
    expect(
      call.mock.calls.every(
        ([, params]) =>
          params.reference_doctype === 'CRM Lead' &&
          params.reference_name === 'LEAD-INSTAGRAM-WITHOUT-PHONE',
      ),
    ).toBe(true)
  })
})
