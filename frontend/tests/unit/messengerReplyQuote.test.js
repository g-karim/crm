import { createApp } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import MessageReplyQuote from '@/components/LeadMessenger/MessageReplyQuote.vue'

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
})
