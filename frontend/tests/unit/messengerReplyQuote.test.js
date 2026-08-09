import { createApp } from 'vue'
import { afterEach, describe, expect, it } from 'vitest'
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

  it.each([
    ['image', 'Изображение'],
    ['photo', 'Изображение'],
    ['video', 'Видео'],
    ['audio', 'Аудио'],
    ['audio_message', 'Аудио'],
    ['file', 'Документ'],
    ['doc', 'Документ'],
    ['document', 'Документ'],
    ['link', 'Ссылка'],
    ['sticker', 'Стикер'],
    ['location', 'Геолокация'],
    ['geo', 'Геолокация'],
    ['contact', 'Контакт'],
    ['unsupported', 'Вложение'],
    ['provider-specific', 'Вложение'],
  ])('labels a single %s attachment as %s', (type, label) => {
    let root = mount({
      message: 'MSG-ATTACHMENT',
      state: 'available',
      snapshot: { attachment_types: [type] },
    })

    expect(root.textContent).toContain(label)
  })

  it.each([
    ['image', 'Изображения'],
    ['photo', 'Изображения'],
    ['video', 'Видео'],
    ['audio_message', 'Аудио'],
    ['doc', 'Документы'],
    ['link', 'Ссылки'],
    ['sticker', 'Стикеры'],
    ['geo', 'Геолокации'],
    ['contact', 'Контакты'],
    ['provider-specific', 'Вложения'],
  ])('labels repeated %s attachments as %s', (type, label) => {
    let root = mount({
      message: 'MSG-ATTACHMENTS',
      state: 'available',
      snapshot: { attachment_types: [type, type] },
    })

    expect(root.textContent).toContain(label)
  })

  it('labels mixed attachments generically', () => {
    let root = mount({
      message: 'MSG-MIXED',
      state: 'available',
      snapshot: { attachment_types: ['photo', 'doc'] },
    })

    expect(root.textContent).toContain('Вложения')
  })

  it('uses a normalized or legacy message type when attachment types are absent', () => {
    let contact = mount({
      message: 'MSG-CONTACT',
      state: 'available',
      snapshot: { message_type: 'contact' },
    })
    let photo = mount({
      message: 'MSG-PHOTO',
      state: 'available',
      snapshot: { message_type: 'photo' },
    })

    expect(contact.textContent).toContain('Контакт')
    expect(photo.textContent).toContain('Изображение')
  })
})
