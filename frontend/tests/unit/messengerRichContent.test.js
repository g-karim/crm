import { createApp, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mapHandlers = {}
const markerHandlers = {}
const map = {
  setView: vi.fn(() => map),
  attributionControl: { setPrefix: vi.fn() },
  on: vi.fn((event, handler) => {
    mapHandlers[event] = handler
    return map
  }),
  remove: vi.fn(),
}
const marker = {
  setLatLng: vi.fn(() => marker),
  on: vi.fn((event, handler) => {
    markerHandlers[event] = handler
    return marker
  }),
  addTo: vi.fn(() => marker),
  getLatLng: vi.fn(() => ({ lat: 59.94, lng: 30.31 })),
}

vi.mock('leaflet/dist/leaflet.css', () => ({}))
vi.mock('leaflet', () => ({
  default: {
    map: vi.fn(() => map),
    tileLayer: vi.fn(() => ({ addTo: vi.fn() })),
    divIcon: vi.fn((options) => options),
    marker: vi.fn(() => marker),
  },
}))

vi.mock('frappe-ui', () => ({
  Button: {
    props: ['label', 'disabled'],
    emits: ['click'],
    template:
      '<button :disabled="disabled" @click="$emit(\'click\')">{{ label }}</button>',
  },
  Dialog: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<div v-if="modelValue"><slot name="body-content" /><slot name="actions" /></div>',
  },
  FeatherIcon: { template: '<span data-test-icon />' },
  call: vi.fn(),
  toast: { error: vi.fn() },
}))

vi.mock(
  '~icons/lucide/audio-lines',
  () => ({ default: { template: '<span data-test-audio-icon />' } }),
  { virtual: true },
)

import ContactAttachment from '@/components/LeadMessenger/ContactAttachment.vue'
import LocationAttachment from '@/components/LeadMessenger/LocationAttachment.vue'
import LocationPickerDialog from '@/components/LeadMessenger/LocationPickerDialog.vue'
import MessageReactions from '@/components/LeadMessenger/MessageReactions.vue'
import MessengerAudioPlayer from '@/components/LeadMessenger/MessengerAudioPlayer.vue'
import { call } from 'frappe-ui'

let mounted = []

beforeEach(() => {
  window.happyDOM.settings.disableIframePageLoading = true
  Object.keys(mapHandlers).forEach((key) => delete mapHandlers[key])
  Object.keys(markerHandlers).forEach((key) => delete markerHandlers[key])
  vi.clearAllMocks()
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      constructor(callback) {
        this.callback = callback
      }
      observe() {
        this.callback([{ isIntersecting: true }])
      }
      disconnect() {}
    },
  )
})

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
})

function mount(component, props) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(component, props)
  app.config.globalProperties.__ = globalThis.__
  root.component = app.mount(root)
  mounted.push({ app, root })
  return root
}

async function flushImports() {
  await nextTick()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await nextTick()
}

describe('messenger rich content', () => {
  it('renders the common voice title for a Telegram technical filename', () => {
    let root = mount(MessengerAudioPlayer, {
      attachment: {
        type: 'audio',
        status: 'pending',
        is_voice: true,
        file_name: 'voice.ogg',
      },
    })

    expect(root.textContent).toContain('Voice message')
    expect(root.textContent).not.toContain('voice.ogg')
    expect(root.querySelector('[data-messenger-audio]').className).toContain(
      'w-[min(22rem,calc(100vw-3rem))]',
    )
  })

  it('uses the parent width for a compact forwarded voice player', () => {
    let root = mount(MessengerAudioPlayer, {
      attachment: {
        type: 'audio',
        status: 'pending',
        is_voice: true,
      },
      compactPreview: true,
    })
    let player = root.querySelector('[data-messenger-audio]')

    expect(player.className).toContain('w-full')
    expect(player.className).toContain('min-w-0')
    expect(player.className).not.toContain('w-[min(22rem,calc(100vw-3rem))]')
  })

  it('renders a location card without the OpenStreetMap embed footer', async () => {
    let root = mount(LocationAttachment, {
      attachment: {
        location: {
          latitude: 55.75,
          longitude: 37.61,
          title: 'Москва',
        },
      },
    })

    await flushImports()

    expect(root.textContent).toContain('55.750000, 37.610000')
    expect(root.querySelector('a').href).toContain('openstreetmap.org')
    expect(root.querySelector('iframe')).toBeNull()
    expect(map.attributionControl.setPrefix).toHaveBeenCalledWith(false)
  })

  it('renders a contact card and telephone action without technical MAX status', () => {
    let root = mount(ContactAttachment, {
      contact: {
        display_name: 'Иван Иванов',
        phones: ['+79990000000'],
        verified: true,
      },
    })

    expect(root.textContent).toContain('Contact')
    expect(root.textContent).toContain('Иван Иванов')
    expect(root.textContent).not.toContain('Подтверждён MAX')
    expect(root.textContent).not.toContain('Не подтверждён MAX')
    expect(root.querySelector('a').getAttribute('href')).toBe(
      'tel:+79990000000',
    )
  })

  it('renders a contact without a name, phone block or verification status', () => {
    let root = mount(ContactAttachment, {
      contact: { phones: [], verified: false, max_user_id: '12345' },
    })

    expect(root.textContent).toContain('Contact')
    expect(root.textContent).toContain('Name not provided')
    expect(root.textContent).not.toContain('Не подтверждён MAX')
    expect(root.textContent).not.toContain('12345')
    expect(root.querySelector('a')).toBeNull()
  })

  it('keeps manual map selection available after geolocation denial', async () => {
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: {
        getCurrentPosition: vi.fn((success, error) =>
          error(new Error('permission denied')),
        ),
      },
    })
    let root = mount(LocationPickerDialog, { modelValue: true })
    await flushImports()

    expect(navigator.geolocation.getCurrentPosition).toHaveBeenCalledOnce()
    mapHandlers.click({ latlng: { lat: 55.75, lng: 37.61 } })
    await nextTick()
    expect(root.textContent).toContain('55.750000, 37.610000')
    expect(marker.on).toHaveBeenCalledWith('dragend', expect.any(Function))
    expect(map.attributionControl.setPrefix).toHaveBeenCalledWith(false)
    expect(root.querySelector('[class*="55dvh"]').className).toContain(
      'h-[clamp(10rem,55dvh,26.25rem)]',
    )

    markerHandlers.dragend({ target: marker })
    await nextTick()
    expect(root.textContent).toContain('59.940000, 30.310000')
  })

  it('shows counts, unknown IDs and highlights the operator reaction', async () => {
    let root = mount(MessageReactions, {
      message: {
        name: 'message-1',
        reactions: {
          items: [
            { reaction_id: 8, count: 2, emoji: '🔥' },
            { reaction_id: 64, count: 1, emoji: null },
            {
              reaction_id: 'custom_emoji:custom-1',
              count: 1,
              emoji: null,
              reaction_type: 'custom_emoji',
              supported: false,
            },
          ],
          own_reaction_id: 8,
          catalog_version: 'vk-message-reactions-40-v1',
          catalog_signature: 'catalog-signature',
          catalog: Array.from({ length: 40 }, (_, index) => ({
            reaction_id: index + 1,
            emoji: index === 0 ? '👍' : `R${index + 1}`,
          })),
        },
      },
      canSend: true,
    })

    let buttons = root.querySelectorAll('button')
    expect(buttons[0].textContent).toContain('🔥 2')
    expect(buttons[0].getAttribute('aria-pressed')).toBe('true')
    expect(buttons[1].textContent).toContain('#64 1')
    expect(buttons[2].textContent).toContain('✦ 1')
    expect(buttons[2].getAttribute('title')).toBe('Custom Telegram Reaction')
    expect(buttons[2].disabled).toBe(true)
    expect(buttons).toHaveLength(3)

    root.component.openPicker(
      new MouseEvent('contextmenu', { clientX: 20, clientY: 30 }),
    )
    await nextTick()
    let picker = document.body.querySelector('[role="menu"]')
    expect(picker).not.toBeNull()
    expect(picker.className).toContain('w-[calc(100vw-1rem)]')
    expect(picker.className).toContain('max-h-[calc(100dvh-1rem)]')
    expect(picker.className).toContain('overflow-y-auto')
    expect(picker.className).toContain(
      'grid-cols-[repeat(auto-fit,minmax(2.25rem,1fr))]',
    )
    expect(picker.querySelectorAll('[role="menuitemradio"]')).toHaveLength(40)
    picker.querySelector('[role="menuitemradio"]').click()
    await nextTick()
    expect(call).toHaveBeenCalledWith(
      'crm_messenger.api.messages.set_reaction',
      expect.objectContaining({
        reaction_id: 1,
        catalog_version: 'vk-message-reactions-40-v1',
        catalog_signature: 'catalog-signature',
      }),
    )
  })

  it('keeps reactions visible but immutable without operator permission', async () => {
    let root = mount(MessageReactions, {
      message: {
        name: 'read-only-message',
        reactions: {
          items: [{ reaction_id: 'emoji:👍', count: 1, emoji: '👍' }],
          catalog: [{ reaction_id: 'emoji:👍', emoji: '👍' }],
        },
      },
      canSend: false,
    })

    let button = root.querySelector('button')
    expect(button.textContent).toContain('👍 1')
    expect(button.disabled).toBe(true)
    expect(
      root.component.openPicker(
        new MouseEvent('contextmenu', { clientX: 20, clientY: 30 }),
      ),
    ).toBe(false)
    button.click()
    await nextTick()
    expect(call).not.toHaveBeenCalled()
  })

  it('uses string Telegram reaction IDs and toggles the operator reaction', async () => {
    call.mockResolvedValueOnce({
      ok: true,
      reaction_state: { items: [], own_reaction_id: null },
    })
    let root = mount(MessageReactions, {
      message: {
        name: 'telegram-message-1',
        reactions: {
          items: [{ reaction_id: 'emoji:👍', count: 2, emoji: '👍' }],
          own_reaction_id: 'emoji:👍',
          catalog_version: 'telegram-bot-api-10.2-emoji-v1',
          catalog_signature: 'telegram-signature',
          catalog: [{ reaction_id: 'emoji:👍', emoji: '👍' }],
        },
      },
      canSend: true,
    })

    root.querySelector('button').click()
    await nextTick()

    expect(call).toHaveBeenCalledWith(
      'crm_messenger.api.messages.set_reaction',
      {
        message: 'telegram-message-1',
        reaction_id: null,
        catalog_version: 'telegram-bot-api-10.2-emoji-v1',
        catalog_signature: 'telegram-signature',
      },
    )
  })

  it('keeps the full Telegram reaction catalog inside a scrollable picker', async () => {
    let catalog = Array.from({ length: 73 }, (_, index) => ({
      reaction_id: `emoji:${index}`,
      emoji: `${index}`,
    }))
    let root = mount(MessageReactions, {
      message: {
        name: 'telegram-message-catalog',
        reactions: {
          items: [],
          catalog,
          catalog_version: 'telegram-bot-api-10.2-emoji-v1',
          catalog_signature: 'telegram-signature',
        },
      },
      canSend: true,
    })

    root.component.openPicker(
      new MouseEvent('contextmenu', { clientX: 310, clientY: 560 }),
    )
    await nextTick()
    let picker = document.body.querySelector('[role="menu"]')

    expect(picker.querySelectorAll('[role="menuitemradio"]')).toHaveLength(73)
    expect(picker.className).toContain('max-w-[19rem]')
    expect(picker.className).toContain('overscroll-contain')
  })
})
