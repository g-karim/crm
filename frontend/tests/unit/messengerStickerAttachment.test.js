import { createApp, nextTick, reactive } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/components/LeadMessenger/AttachmentCard.vue', () => ({
  default: {
    props: ['attachment'],
    template:
      '<div data-sticker-fallback :data-status="attachment.status">{{ attachment.display_title || attachment.status }}</div>',
  },
}))
vi.mock('@/components/LeadMessenger/VkLottieSticker.vue', () => ({
  default: {
    props: ['attachment'],
    template: '<div data-lottie-sticker />',
  },
}))
vi.mock('@/components/Icons/LoadingIndicator.vue', () => ({
  default: { template: '<span data-test-loading />' },
}))

import StickerAttachment from '@/components/LeadMessenger/StickerAttachment.vue'

let mounted = []

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
  vi.useRealTimers()
})

function mountSticker(attachment) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(StickerAttachment, { attachment })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return root
}

function sticker(overrides = {}) {
  return {
    id: 'STICKER',
    type: 'sticker',
    status: 'available',
    mime_type: 'image/webp',
    url: '/api/private-sticker',
    ...overrides,
  }
}

describe('common messenger sticker', () => {
  it.each([
    ['wazzup', 'whatsapp'],
    ['wazzup', 'telegram'],
    ['max_direct', 'max'],
    ['vk_direct', 'vk'],
    ['telegram_bot', 'telegram'],
  ])(
    'preserves compact %s %s stickers and retries browser media errors explicitly',
    async (provider, platform) => {
      vi.useFakeTimers()
      let attachment = reactive(sticker({ provider, platform }))
      let root = mountSticker(attachment)
      expect(root.firstElementChild.className).toContain('size-52')
      expect(root.firstElementChild.className).toContain('max-w-full')
      let image = root.querySelector('[data-sticker-image]')
      expect(image.className).toContain('object-contain')
      expect(image.getAttribute('alt')).toBe('Sticker')
      image.dispatchEvent(new Event('load'))
      await nextTick()
      expect(root.querySelector('[data-sticker-loading]')).toBeNull()

      image.dispatchEvent(new Event('error'))
      await nextTick()
      expect(root.querySelector('[data-sticker-image]')).toBeNull()
      expect(root.querySelector('[data-sticker-fallback]').dataset.status).toBe(
        'failed',
      )
      expect(root.textContent).toContain('Sticker unavailable')
      await vi.advanceTimersByTimeAsync(60000)
      expect(root.querySelector('[data-sticker-image]')).toBeNull()
      root.querySelector('button').click()
      await nextTick()
      expect(
        root.querySelector('[data-sticker-image]').getAttribute('src'),
      ).toBe('/api/private-sticker')

      root
        .querySelector('[data-sticker-image]')
        .dispatchEvent(new Event('error'))
      await nextTick()
      attachment.url = '/api/refreshed-sticker'
      await nextTick()
      expect(
        root.querySelector('[data-sticker-image]').getAttribute('src'),
      ).toBe('/api/refreshed-sticker')
    },
  )

  it('retains animation on video stickers and bounds stalled local loading', async () => {
    vi.useFakeTimers()
    let root = mountSticker(sticker({ mime_type: 'video/webm' }))
    let video = root.querySelector('[data-sticker-video]')
    expect(video.autoplay).toBe(true)
    expect(video.loop).toBe(true)
    expect(video.muted).toBe(true)
    expect(video.hasAttribute('playsinline')).toBe(true)
    expect(video.getAttribute('aria-label')).toBe('Sticker')

    await vi.advanceTimersByTimeAsync(20000)
    expect(root.querySelector('[data-sticker-loading]')).toBeNull()
    expect(root.querySelector('[data-sticker-video]')).toBeNull()
    expect(root.textContent).toContain('Try Again')
    root.querySelector('button').click()
    await nextTick()
    video = root.querySelector('[data-sticker-video]')
    video.dispatchEvent(new Event('loadeddata'))
    await vi.advanceTimersByTimeAsync(20000)
    expect(root.querySelector('[data-sticker-video]')).not.toBeNull()
    expect(root.querySelector('[data-sticker-loading]')).toBeNull()
  })

  it.each(['pending', 'downloading', 'retrying', 'failed', 'unsupported'])(
    'shows the %s DTO fallback without fetching inactive media',
    async (status) => {
      vi.useFakeTimers()
      let attachment = reactive(sticker({ status }))
      let root = mountSticker(attachment)
      expect(root.querySelector('[data-sticker-image]')).toBeNull()
      expect(root.querySelector('[data-sticker-video]')).toBeNull()
      expect(root.querySelector('[data-sticker-loading]')).toBeNull()
      expect(root.querySelector('button')).toBeNull()
      expect(root.querySelector('[data-sticker-fallback]').dataset.status).toBe(
        status,
      )
      await vi.advanceTimersByTimeAsync(60000)
      expect(root.querySelector('button')).toBeNull()

      attachment.status = 'available'
      await nextTick()
      expect(root.querySelector('[data-sticker-image]')).not.toBeNull()
    },
  )

  it('delegates only available TGS/JSON stickers to the shared Lottie renderer', async () => {
    let attachment = reactive(
      sticker({ mime_type: 'application/json', is_animated: true }),
    )
    let root = mountSticker(attachment)
    expect(root.querySelector('[data-lottie-sticker]')).not.toBeNull()
    expect(root.querySelector('[data-sticker-loading]')).toBeNull()
    attachment.status = 'unsupported'
    await nextTick()
    expect(root.querySelector('[data-lottie-sticker]')).toBeNull()
    expect(root.querySelector('[data-sticker-fallback]')).not.toBeNull()
  })

  it('uses an unsupported fallback for an available sticker with no usable representation', () => {
    let root = mountSticker(sticker({ mime_type: 'application/octet-stream' }))
    expect(root.querySelector('[data-sticker-fallback]').dataset.status).toBe(
      'unsupported',
    )
    expect(root.querySelector('[data-sticker-loading]')).toBeNull()
  })
})
