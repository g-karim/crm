import { createApp } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/components/LeadMessenger/AttachmentRenderer.vue', () => ({
  default: {
    props: ['attachments', 'compactPreview'],
    template:
      '<div data-forward-attachments :data-compact="compactPreview">{{ attachments.map((item) => item.id).join(",") }}</div>',
  },
}))

import MessageForwardStack from '@/components/LeadMessenger/MessageForwardStack.vue'

let mounted = []

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
})

function mountStack(context) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(MessageForwardStack, { context, provider: 'vk_direct' })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return root
}

describe('forwarded message stack', () => {
  it('renders nested messages and their routed attachments', () => {
    let root = mountStack({
      version: 1,
      truncated: false,
      items: [
        {
          key: 'forward-0',
          sender_name: 'Мария',
          text: 'Первое сообщение',
          attachments: [{ id: 'A-1', type: 'image' }],
          items: [
            {
              key: 'forward-0-0',
              sender_name: null,
              text: 'Вложенное сообщение',
              attachments: [],
              items: [],
            },
          ],
        },
      ],
    })

    expect(root.querySelectorAll('[data-forward-item]')).toHaveLength(2)
    expect(root.textContent).toContain('Forwarded Message')
    expect(root.textContent).toContain('Мария')
    expect(root.textContent).toContain('Первое сообщение')
    expect(root.textContent).toContain('Вложенное сообщение')
    expect(root.querySelector('[data-forward-attachments]').textContent).toBe(
      'A-1',
    )
    expect(
      root
        .querySelector('[data-forward-attachments]')
        .hasAttribute('data-compact'),
    ).toBe(true)
    expect(
      root.querySelector('[data-message-forward-stack]').className,
    ).toContain('w-fit')
    let forwardItem = root.querySelector('[data-forward-item]')
    expect(forwardItem.className).toContain('w-[20rem]')
    expect(forwardItem.className).toContain('max-w-full')
    expect(forwardItem.className).not.toContain('w-fit')
  })

  it('renders an embedded reply before the forwarded response', () => {
    let root = mountStack({
      version: 1,
      items: [
        {
          key: 'forward-0',
          relation: 'forward',
          sender_name: 'Мария',
          text: 'Ответ',
          items: [
            {
              key: 'forward-0-0',
              relation: 'reply',
              text: 'Исходный текст',
              items: [],
            },
          ],
        },
      ],
    })

    expect(root.textContent).toContain('Original Message')
    expect(root.textContent.indexOf('Исходный текст')).toBeLessThan(
      root.textContent.indexOf('Ответ'),
    )
    expect(root.textContent).toContain('Мария')
  })

  it('keeps an attachment-only sticker card content-sized', () => {
    let root = mountStack({
      version: 1,
      items: [
        {
          key: 'forward-0',
          relation: 'forward',
          attachments: [{ id: 'STICKER-1', type: 'sticker' }],
          items: [],
        },
      ],
    })

    let forwardItem = root.querySelector('[data-forward-item]')
    let forwardHeader = forwardItem.firstElementChild
    expect(forwardItem.className).toContain('w-[14.5rem]')
    expect(forwardItem.className).not.toContain('w-[20rem]')
    expect(forwardHeader.className).toContain('flex-wrap')
  })

  it('uses a neutral label for an empty forwarded item', () => {
    let root = mountStack({
      version: 1,
      items: [{ key: 'forward-0', relation: 'forward', items: [] }],
    })
    expect(root.textContent).toContain('Forwarded Message')
    expect(root.textContent).not.toContain('unavailable')
  })

  it('shows unavailable and truncation fallbacks explicitly', () => {
    let root = mountStack({
      version: 1,
      truncated: true,
      items: [
        {
          key: 'forward-0',
          attachment_types: ['video'],
          attachments: [],
          items: [],
        },
      ],
    })

    expect(root.textContent).toContain('Attachment unavailable')
    expect(root.querySelector('[data-forward-truncated]')).not.toBeNull()
  })
})
