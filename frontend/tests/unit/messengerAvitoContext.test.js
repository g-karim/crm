import { createApp, h, nextTick, reactive } from 'vue'
import { afterEach, describe, expect, it } from 'vitest'
import AvitoItemCard from '@/components/LeadMessenger/AvitoItemCard.vue'
import {
  getAvitoItem,
  avitoConversationLabel,
} from '@/utils/messengerAvitoContext'
import { messengerConversationOption } from '@/utils/messengerRouting'

const conversation = (id = '1', title = 'Bicycle') => ({
  name: `CHAT-${id}`,
  provider: 'avito_direct',
  channel: 'AVITO-ACCOUNT',
  avito_item: {
    id,
    title,
    price_string: '10 000 ₽',
    url: `https://www.avito.ru/item_${id}`,
    images_main: {
      '140x105': 'https://img.example.test/small.jpg',
      '640x480': 'https://img.example.test/main.jpg',
    },
  },
})
let mounted = []
afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
})
function mount(value) {
  let props = reactive({ conversation: value })
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp({ render: () => h(AvitoItemCard, props) })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return { root, props }
}

describe('Avito listing context', () => {
  it('renders only selected listing data and updates on selection', async () => {
    let { root, props } = mount(conversation())
    expect(root.textContent).toContain('Bicycle')
    expect(root.textContent).toContain('10 000 ₽')
    expect(root.textContent).toContain('Listing ID: 1')
    expect(root.querySelector('img').src).toContain('main.jpg')
    expect(root.querySelector('a').href).toBe('https://www.avito.ru/item_1')
    expect(root.querySelector('a').rel).toContain('noreferrer')
    props.conversation = conversation('2', 'Scooter')
    await nextTick()
    expect(root.textContent).toContain('Scooter')
    expect(root.textContent).not.toContain('Bicycle')
    expect(root.querySelector('a').href).toBe('https://www.avito.ru/item_2')
  })

  it('handles missing data, legacy ID-only context, and other providers', async () => {
    let { root, props } = mount({ provider: 'avito_direct' })
    expect(root.querySelector('section')).toBeNull()
    props.conversation = { provider: 'avito_direct', avito_item: {} }
    await nextTick()
    expect(root.querySelector('section')).toBeNull()
    props.conversation = { provider: 'avito_direct', avito_item: { id: '300' } }
    await nextTick()
    expect(root.textContent).toContain('Listing ID: 300')
    props.conversation = { ...conversation(), provider: 'vk_direct' }
    await nextTick()
    expect(root.querySelector('section')).toBeNull()
    expect(getAvitoItem(null)).toBeNull()
  })

  it('hides failed images and never renders provider HTML', async () => {
    let { root } = mount(conversation('1', '<img src=x onerror=alert(1)>'))
    expect(root.textContent).toContain('<img src=x onerror=alert(1)>')
    expect(root.querySelectorAll('img')).toHaveLength(1)
    root.querySelector('img').dispatchEvent(new Event('error'))
    await nextTick()
    expect(root.querySelector('img')).toBeNull()
    expect(root.querySelector('a')).not.toBeNull()
  })

  it.each([
    'javascript:alert(1)',
    'http://avito.ru/item',
    'https://avito.ru.evil.test/item',
    'https://user:password@avito.ru/item',
    '//avito.ru/item',
  ])('rejects unsafe listing URL %s', (url) => {
    let row = conversation()
    row.avito_item.url = url
    row.avito_item.images_main = { '640x480': 'data:image/svg+xml,bad' }
    expect(getAvitoItem(row)).toMatchObject({ url: '', image: '' })
  })

  it('distinguishes same-account conversations including identical or missing titles', () => {
    let a = conversation('1', 'Bicycle')
    let b = conversation('2', 'Bicycle')
    expect(messengerConversationOption(a).label).toContain('Bicycle · #1')
    expect(messengerConversationOption(b).label).toContain('Bicycle · #2')
    expect(avitoConversationLabel(a)).not.toBe(avitoConversationLabel(b))
    delete a.avito_item
    delete b.avito_item
    expect(avitoConversationLabel(a)).toBe('')
    expect(avitoConversationLabel(b)).toBe('')
    expect(avitoConversationLabel({ provider: 'telegram_bot' })).toBe('')
  })
})
