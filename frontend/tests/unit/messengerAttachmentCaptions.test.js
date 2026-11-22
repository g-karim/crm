import AttachmentRenderer from '@/components/LeadMessenger/AttachmentRenderer.vue'
import MessageContent from '@/components/LeadMessenger/MessageContent.vue'
import { shouldShowMessengerMessageText } from '@/utils/messengerMessagePresentation'
import { createApp, h, nextTick, reactive } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('frappe-ui', () => ({
  Button: { template: '<button />' },
  Textarea: { template: '<textarea />' },
}))

const filename = 'Требования к оформлению проекта (1).pptx'
const integrations = [
  ['wazzup', 'whatsapp'],
  ['wazzup', 'telegram'],
  ['wazzup', 'max'],
  ['wazzup', 'viber'],
  ['telegram_bot', 'telegram'],
  ['max_direct', 'max'],
  ['vk_direct', 'vk'],
  ['avito_direct', 'avito'],
]
const routes = integrations.flatMap(([provider, platform]) =>
  ['inbound', 'outbound'].map((direction) => [provider, platform, direction]),
)
let mounted = []

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
})

function file(overrides = {}) {
  return {
    id: 'DOCUMENT',
    type: 'file',
    status: 'available',
    file_name: filename,
    display_title: filename,
    mime_type:
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    ...overrides,
  }
}

function message(provider, platform, direction, overrides = {}) {
  return {
    name: 'SAVED-MESSAGE',
    provider,
    direction,
    channel_info: { platform, wazzup_api_mode: 'partner_api_v2' },
    message_type: 'file',
    status: direction === 'inbound' ? 'received' : 'sent',
    text: null,
    attachments: [file()],
    ...overrides,
  }
}

function mountBubble(value, renderAttachments = true) {
  let current = reactive(value)
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp({
    render: () =>
      h('div', [
        h(MessageContent, {
          message: current,
          shouldShowText: shouldShowMessengerMessageText(current),
        }),
        renderAttachments &&
          h(AttachmentRenderer, {
            attachments: current.attachments,
            provider: current.provider,
            outbound: current.direction === 'outbound',
          }),
      ]),
  })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return { root, current }
}

describe('attachment captions in the shared message renderer', () => {
  it.each(routes)(
    'renders a captionless %s %s %s document name once, including saved DTOs',
    (provider, platform, direction) => {
      let saved = message(provider, platform, direction, {
        display_text: filename,
      })
      let original = structuredClone(saved)
      let { root } = mountBubble(JSON.parse(JSON.stringify(saved)))

      expect(root.querySelector('[data-message-text]')).toBeNull()
      expect(
        root.querySelector('[data-attachment-card-title]').textContent,
      ).toBe(filename)
      expect(root.textContent.split(filename)).toHaveLength(2)
      expect(saved).toEqual(original)
    },
  )

  it.each(routes)(
    'preserves an actual %s %s %s document caption verbatim',
    (provider, platform, direction) => {
      for (let text of ['Настоящая подпись', `${filename} `, ` ${filename}`]) {
        let { root } = mountBubble(
          message(provider, platform, direction, { text }),
        )
        expect(root.querySelector('[data-message-text]').textContent).toBe(text)
        expect(
          root.querySelector('[data-attachment-card-title]').textContent,
        ).toBe(filename)
      }
    },
  )

  it.each(routes)(
    'applies the explicit equal-caption policy only to inbound Wazzup: %s %s %s',
    (provider, platform, direction) => {
      // This payload also represents a user intentionally typing the filename.
      // The provider gives no discriminator; the agreed display policy hides it.
      let saved = message(provider, platform, direction, { text: filename })
      let original = structuredClone(saved)
      let { root } = mountBubble(saved)
      let hidden = provider === 'wazzup' && direction === 'inbound'

      expect(root.querySelectorAll('[data-message-text]')).toHaveLength(
        hidden ? 0 : 1,
      )
      expect(
        root.querySelector('[data-attachment-card-title]').textContent,
      ).toBe(filename)
      expect(root.textContent.split(filename)).toHaveLength(hidden ? 2 : 3)
      expect(saved).toEqual(original)
    },
  )

  it.each(integrations)(
    'preserves %s %s captions with several documents or mixed attachments',
    (provider, platform) => {
      for (let attachments of [
        [
          file(),
          file({
            id: 'OTHER',
            file_name: 'Other.pdf',
            display_title: 'Other.pdf',
          }),
        ],
        [file(), { id: 'IMAGE', type: 'image', status: 'failed' }],
      ]) {
        let { root } = mountBubble(
          message(provider, platform, 'inbound', {
            text: filename,
            attachments,
          }),
        )
        expect(root.querySelector('[data-message-text]').textContent).toBe(
          filename,
        )
        expect(
          root.querySelector('[data-attachment-card-title]').textContent,
        ).toBe(filename)
      }
    },
  )

  it.each(['pending', 'available', 'failed', 'unsupported'])(
    'keeps a saved Wazzup document deduplicated through a %s DTO update',
    async (status) => {
      let { root, current } = mountBubble(
        message('wazzup', 'whatsapp', 'inbound', {
          text: filename,
          attachments: [
            file({
              file_name: '0123456789abcdef0123456789abcdef',
              original_file_name: filename,
            }),
          ],
        }),
      )
      current.attachments = [file({ status })]
      await nextTick()

      expect(root.querySelector('[data-message-text]')).toBeNull()
      expect(
        root.querySelector('[data-attachment-card-title]').textContent,
      ).toBe(filename)
      expect(current.text).toBe(filename)
    },
  )

  it.each([
    'image',
    'audio',
    'video',
    'sticker',
    'link',
    'location',
    'contact',
    'unsupported',
  ])('keeps filename-like captions on %s attachments', (type) => {
    let value = message('wazzup', 'whatsapp', 'inbound', {
      text: filename,
      message_type: type,
      attachments: [file({ type })],
    })
    expect(
      mountBubble(value, false).root.querySelector('[data-message-text]')
        .textContent,
    ).toBe(filename)
  })

  it('does not treat a generic document label as a known filename', () => {
    let { root } = mountBubble(
      message('wazzup', 'whatsapp', 'inbound', {
        text: 'File',
        attachments: [
          file({
            file_name: '0123456789abcdef0123456789abcdef',
            display_title: 'File',
          }),
        ],
      }),
    )
    expect(root.querySelector('[data-message-text]').textContent).toBe('File')
  })

  it('keeps legacy technical-filename DTOs supported without changing stored text', () => {
    let saved = message('wazzup', 'whatsapp', 'inbound', {
      text: filename,
      text_is_attachment_filename: true,
    })
    expect(
      mountBubble(saved).root.querySelector('[data-message-text]'),
    ).toBeNull()
    expect(saved.text).toBe(filename)
  })
})
