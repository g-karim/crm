import { createApp, h, nextTick, reactive, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

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
  vi.restoreAllMocks()
  vi.useRealTimers()
})

function mountSticker(attachment) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let currentAttachment = ref(attachment)
  let app = createApp({
    render: () => h(StickerAttachment, { attachment: currentAttachment.value }),
  })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root, currentAttachment })
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
    ['wazzup', 'max'],
    ['wazzup', 'viber'],
    ['max_direct', 'max'],
    ['vk_direct', 'vk'],
    ['telegram_bot', 'telegram'],
  ])(
    'preserves compact %s %s stickers and retries browser media errors explicitly',
    async (provider, platform) => {
      vi.useFakeTimers()
      let attachment = reactive(sticker({ provider, platform }))
      let root = mountSticker(attachment)
      expect(root.firstElementChild.className).toContain('size-40')
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

  it('keeps a slow sticker playable and fails only on an actual media error', async () => {
    vi.useFakeTimers()
    let root = mountSticker(sticker({ mime_type: 'video/webm' }))
    let video = root.querySelector('[data-sticker-video]')
    expect(video.autoplay).toBe(true)
    expect(video.loop).toBe(true)
    expect(video.muted).toBe(true)
    expect(video.hasAttribute('playsinline')).toBe(true)
    expect(video.getAttribute('aria-label')).toBe('Sticker')

    await vi.advanceTimersByTimeAsync(20000)
    expect(root.querySelector('[data-sticker-loading]')).not.toBeNull()
    expect(root.querySelector('[data-sticker-video]')).toBe(video)
    expect(root.textContent).not.toContain('Try Again')
    video.dispatchEvent(new Event('error'))
    await nextTick()
    expect(root.textContent).toContain('Try Again')
    root.querySelector('button').click()
    await nextTick()
    video = root.querySelector('[data-sticker-video]')
    video.dispatchEvent(new Event('loadeddata'))
    await vi.advanceTimersByTimeAsync(20000)
    expect(root.querySelector('[data-sticker-video]')).not.toBeNull()
    expect(root.querySelector('[data-sticker-loading]')).toBeNull()
  })

  it.each(['image/gif', 'image/webp', 'image/apng', 'image/png'])(
    'keeps an animated %s sticker in the compact image renderer',
    async (mime_type) => {
      let root = mountSticker(sticker({ mime_type, is_animated: true }))
      expect(root.firstElementChild.className).toContain('size-40')
      expect(root.querySelector('[data-sticker-image]')).not.toBeNull()
      expect(root.querySelector('video')).toBeNull()
      root.querySelector('img').dispatchEvent(new Event('load'))
      await nextTick()
      expect(root.querySelector('[data-sticker-loading]')).toBeNull()
    },
  )

  it('uses the video playback rendition and resets browser failure when it changes', async () => {
    let attachment = reactive(
      sticker({
        mime_type: 'video/webm',
        is_animated: true,
        url: null,
        playback_url: '/api/sticker-playback',
      }),
    )
    let root = mountSticker(attachment)
    let video = root.querySelector('[data-sticker-video]')
    expect(video.getAttribute('src')).toBe('/api/sticker-playback')
    video.dispatchEvent(new Event('error'))
    await nextTick()
    expect(root.querySelector('[data-sticker-fallback]')).not.toBeNull()

    attachment.playback_url = '/api/refreshed-sticker-playback'
    await nextTick()
    expect(root.querySelector('[data-sticker-video]').getAttribute('src')).toBe(
      '/api/refreshed-sticker-playback',
    )
    expect(root.querySelector('[data-sticker-fallback]')).toBeNull()
  })

  it('keeps a loaded static sticker ready when realtime refresh replaces its DTO', async () => {
    vi.useFakeTimers()
    let attachment = sticker({ provider: 'wazzup' })
    let root = mountSticker(attachment)
    let image = root.querySelector('[data-sticker-image]')
    image.dispatchEvent(new Event('load'))
    await nextTick()
    expect(root.querySelector('[data-sticker-loading]')).toBeNull()

    let currentAttachment = mounted.find(
      (entry) => entry.root === root,
    ).currentAttachment
    currentAttachment.value = { ...attachment, size_bytes: 8192 }
    await nextTick()
    expect(root.querySelector('[data-sticker-image]')).toBe(image)
    expect(root.querySelector('[data-sticker-loading]')).toBeNull()
    await vi.advanceTimersByTimeAsync(60000)
    expect(root.querySelector('[data-sticker-image]')).toBe(image)
    expect(root.querySelector('[data-sticker-fallback]')).toBeNull()
  })

  it('recognizes an image already decoded from the browser cache without a load event', async () => {
    vi.spyOn(HTMLImageElement.prototype, 'complete', 'get').mockReturnValue(
      true,
    )
    vi.spyOn(HTMLImageElement.prototype, 'naturalWidth', 'get').mockReturnValue(
      128,
    )
    let root = mountSticker(sticker())
    await nextTick()
    await nextTick()
    expect(root.querySelector('[data-sticker-image]')).not.toBeNull()
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
      let fallback = root.querySelector('[data-sticker-fallback]')
      expect(fallback.parentElement.className).toContain('size-40')
      expect(fallback.dataset.status).toBe(status)
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
