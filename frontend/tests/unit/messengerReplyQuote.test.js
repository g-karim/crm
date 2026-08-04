import { createApp } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import MessageReplyQuote from '@/components/LeadMessenger/MessageReplyQuote.vue'
import { getForwardedContentKind } from '@/utils/messengerForwarding'

let mounted = []
afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
})

function mount(context, props = {}) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(MessageReplyQuote, { context, ...props })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return root
}

describe('message reply quote', () => {
  it('classifies forwarded trees consistently for composer snapshots', () => {
    expect(
      getForwardedContentKind({
        items: [
          {
            attachment_types: ['image'],
            items: [{ attachment_types: ['file'] }],
          },
        ],
      }),
    ).toBe('attachment')
    expect(
      getForwardedContentKind({
        items: [{ attachment_types: ['image', 'link'] }],
      }),
    ).toBe('message')
    expect(getForwardedContentKind({ items: [{ text: 'Текст' }] })).toBe(
      'message',
    )
    expect(getForwardedContentKind({ items: [{}] })).toBe('message')
  })

  it('renders a safe snapshot without provider payload fields', () => {
    let root = mount({
      message: null,
      state: 'unavailable',
      snapshot: { sender_name: 'Клиент', text: 'Исходный текст' },
    })
    expect(root.textContent).toContain('Сообщение не загружено')
    expect(root.textContent).toContain('Исходный текст')
  })

  it('does not expose a deleted snapshot', () => {
    let root = mount({
      message: 'MSG-1',
      state: 'deleted',
      snapshot: { text: 'secret old text' },
    })
    expect(root.textContent).toContain('Сообщение удалено')
    expect(root.textContent).not.toContain('secret old text')
  })

  it('renders the author role instead of a provider peer id', () => {
    let root = mount({
      message: 'MSG-1',
      state: 'available',
      snapshot: { direction: 'inbound', sender_name: '560784880', text: 'Исходный текст' },
    })
    expect(root.textContent).toContain('Клиент')
    expect(root.textContent).not.toContain('560784880')
  })

  it('uses the editable lead name for an inbound quote', () => {
    let root = mount(
      {
        message: 'MSG-1',
        state: 'available',
        snapshot: { direction: 'inbound', sender_name: 'Иван VK', text: 'Текст' },
      },
      { clientName: 'Иван Петров' },
    )
    expect(root.textContent).toContain('Иван Петров')
    expect(root.textContent).not.toContain('Иван VK')
  })

  it('describes forwarded reply targets by their normalized content kind', () => {
    let attachment = mount({
      message: 'FORWARD-FILE',
      state: 'available',
      snapshot: { forwarded_content_kind: 'attachment' },
    })
    let message = mount({
      message: 'FORWARD-LINK',
      state: 'available',
      snapshot: {
        forwarded_content_kind: 'message',
        attachment_types: ['link'],
      },
    })

    expect(attachment.textContent).toContain('Вложение')
    expect(message.textContent).toContain('Пересланное сообщение')
    expect(message.textContent).not.toContain('Исходное сообщение недоступно')
  })

  it('keeps an outer comment above forwarded-content classification', () => {
    let root = mount({
      message: 'FORWARD-WITH-COMMENT',
      state: 'available',
      snapshot: {
        text: 'Комментарий отправителя',
        forwarded_content_kind: 'attachment',
      },
    })
    expect(root.textContent).toContain('Комментарий отправителя')
    expect(root.textContent).not.toContain('Вложение')
  })
})
