/* eslint-disable vue/one-component-per-file */
import { createApp, h, nextTick, reactive } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/components/LeadMessenger/MediaLightbox.vue', () => ({
  default: {
    props: ['items', 'initialIndex'],
    template:
      '<div data-test-lightbox :data-index="initialIndex">{{ items.map((item) => `${item.id}:${item.kind}`).join(",") }}</div>',
  },
}))

vi.mock('@/components/LeadMessenger/AttachmentCard.vue', () => ({
  default: {
    props: ['attachment'],
    template:
      '<div data-test-attachment-card>{{ attachment.fallback_text || attachment.file_name }}</div>',
  },
}))

vi.mock('@/components/LeadMessenger/AnimatedMediaAttachment.vue', () => ({
  default: {
    emits: ['open-media'],
    props: ['attachment', 'compactPreview'],
    template:
      '<button data-test-animation :data-id="attachment.id" :data-compact="compactPreview" @click="$emit(\'open-media\', attachment)" />',
  },
}))

vi.mock('@/components/LeadMessenger/ContactAttachment.vue', () => ({
  default: {
    props: ['contact'],
    template: '<div data-test-contact>{{ contact.display_name }}</div>',
  },
}))

vi.mock('@/components/LeadMessenger/LocationAttachment.vue', () => ({
  default: {
    props: ['attachment'],
    template:
      '<div data-test-location>{{ attachment.location.latitude }}</div>',
  },
}))

vi.mock('@/components/LeadMessenger/MessengerAudioPlayer.vue', () => ({
  default: {
    props: ['attachment', 'compactPreview'],
    template:
      '<div data-test-audio :data-id="attachment.id" :data-compact="compactPreview" />',
  },
}))

vi.mock('@/components/LeadMessenger/VideoAttachment.vue', () => ({
  default: {
    props: ['attachment'],
    template: '<div data-test-video :data-id="attachment.id" />',
  },
}))

vi.mock('@/components/LeadMessenger/VkLottieSticker.vue', () => ({
  default: {
    props: ['attachment'],
    template: '<div data-test-lottie-sticker :data-id="attachment.id" />',
  },
}))

import AttachmentRenderer from '@/components/LeadMessenger/AttachmentRenderer.vue'
import ImageGrid from '@/components/LeadMessenger/ImageGrid.vue'

let mounted = []

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
  vi.useRealTimers()
})

function image(id, overrides = {}) {
  return {
    id,
    type: 'image',
    status: 'available',
    url: `/media/${id}.jpg`,
    width: 64,
    height: 64,
    ...overrides,
  }
}

function mountGrid(images, props = {}, refreshAttachments = null) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let liveProps = reactive({ images, ...props })
  let app = createApp({ render: () => h(ImageGrid, liveProps) })
  if (refreshAttachments)
    app.provide('refreshMessengerAttachments', refreshAttachments)
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root, props: liveProps })
  return root
}

function mountRenderer(attachments, props = {}) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(AttachmentRenderer, { attachments, ...props })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return root
}

describe('messenger image layout', () => {
  it.each(['pending', 'processing', 'downloading', 'retrying'])(
    'bounds the %s indicator without adding a message refresh action',
    async (status) => {
      vi.useFakeTimers()
      let refresh = vi.fn(async () => {})
      let root = mountGrid(
        [image('WAITING', { status, url: null })],
        {},
        refresh,
      )
      expect(root.querySelector('[data-image-loading]')).not.toBeNull()
      expect(root.querySelector('[data-image-refresh]')).toBeNull()

      await vi.advanceTimersByTimeAsync(29999)
      expect(root.querySelector('[data-image-loading]')).not.toBeNull()
      expect(root.querySelector('[data-image-refresh]')).toBeNull()
      await vi.advanceTimersByTimeAsync(1)
      expect(root.querySelector('[data-image-loading]')).toBeNull()
      expect(root.querySelector('[role="status"]').textContent).not.toBe('')
      expect(root.querySelector('[data-image-refresh]')).toBeNull()
      expect(refresh).not.toHaveBeenCalled()
    },
  )

  it('does not extend a pending image spinner when other album metadata updates', async () => {
    vi.useFakeTimers()
    let waiting = image('WAITING', { status: 'pending', url: null })
    let root = mountGrid([waiting, image('READY')])
    let liveProps = mounted.at(-1).props

    await vi.advanceTimersByTimeAsync(20000)
    liveProps.images = [waiting, image('READY', { width: 1280 })]
    await nextTick()
    await vi.advanceTimersByTimeAsync(10000)
    expect(root.querySelector('[data-image-loading]')).toBeNull()
    expect(root.textContent).toContain('Pending download')
  })

  it('shows a safe local image failure and retries only its existing media GET', async () => {
    let opened = vi.fn()
    let refresh = vi.fn()
    let root = mountGrid(
      [image('BROKEN', { error: 'https://secret.invalid/token=private' })],
      { onOpenImage: opened },
      refresh,
    )
    root.querySelector('img').dispatchEvent(new Event('error'))
    await nextTick()

    expect(root.querySelector('img')).toBeNull()
    expect(root.textContent).toContain('Image unavailable')
    expect(root.textContent).not.toContain('secret.invalid')
    expect(root.querySelector('[data-single-image]').disabled).toBe(true)
    expect(root.querySelector('button button')).toBeNull()
    root.querySelector('[data-single-image]').click()
    expect(opened).not.toHaveBeenCalled()
    root.querySelector('[data-image-retry]').click()
    await nextTick()

    expect(root.querySelector('img').getAttribute('src')).toBe(
      '/media/BROKEN.jpg',
    )
    expect(root.querySelector('[data-image-retry]')).toBeNull()
    expect(refresh).not.toHaveBeenCalled()
    root.querySelector('[data-single-image]').click()
    expect(opened).toHaveBeenCalledOnce()
  })

  it('clears a local image failure when delta replaces the source for the same id', async () => {
    let root = mountGrid([image('IMAGE')])
    let liveProps = mounted.at(-1).props
    root.querySelector('img').dispatchEvent(new Event('error'))
    await nextTick()
    expect(root.querySelector('[data-image-retry]')).not.toBeNull()

    liveProps.images = [image('IMAGE', { url: '/api/refreshed-image' })]
    await nextTick()

    expect(root.querySelector('img').getAttribute('src')).toBe(
      '/api/refreshed-image',
    )
    expect(root.querySelector('[data-image-retry]')).toBeNull()
    expect(root.querySelector('[data-single-image]').disabled).toBe(false)
  })

  it('isolates an album image failure while preserving available image selection', async () => {
    let opened = vi.fn()
    let root = mountGrid([image('FIRST'), image('SECOND')], {
      onOpenImage: opened,
    })
    let media = root.querySelectorAll('img')
    media[1].dispatchEvent(new Event('error'))
    await nextTick()

    expect(root.querySelectorAll('img')).toHaveLength(1)
    expect(root.querySelector('[data-image-retry]')).not.toBeNull()
    root.querySelector('img').closest('button').click()
    expect(opened.mock.calls[0][0].id).toBe('FIRST')
    root.querySelector('[data-image-retry]').click()
    await nextTick()
    expect(root.querySelectorAll('img')).toHaveLength(2)
    expect(root.querySelector('button button')).toBeNull()
  })

  it('keeps failed and unsupported media terminal without tile refresh actions', () => {
    let refresh = vi.fn()
    let root = mountGrid(
      [image('FAILED', { status: 'failed', url: null })],
      {},
      refresh,
    )
    expect(root.textContent).toContain('Attachment unavailable')
    expect(root.querySelector('[data-image-refresh]')).toBeNull()
    expect(root.querySelector('[data-image-retry]')).toBeNull()

    let unsupported = mountGrid(
      [image('UNSUPPORTED', { status: 'unsupported', url: null })],
      {},
      refresh,
    )
    expect(unsupported.textContent).toContain('Unsupported')
    expect(unsupported.querySelector('[data-image-refresh]')).toBeNull()
    expect(unsupported.querySelector('[data-image-retry]')).toBeNull()
    expect(unsupported.querySelector('[data-image-loading]')).toBeNull()
    expect(refresh).not.toHaveBeenCalled()
  })

  it('does not overlay pending or failed album tiles with refresh actions', async () => {
    vi.useFakeTimers()
    let refresh = vi.fn()
    let root = mountGrid(
      [
        image('WAITING', { status: 'retrying', url: null }),
        image('FAILED', { status: 'failed', url: null }),
        image('READY'),
      ],
      {},
      refresh,
    )
    await vi.advanceTimersByTimeAsync(30000)

    expect(root.querySelector('[data-image-refresh]')).toBeNull()
    expect(root.querySelectorAll('img')).toHaveLength(1)
    expect(root.textContent).toContain('Retrying download')
    expect(root.textContent).toContain('Attachment unavailable')
    expect(refresh).not.toHaveBeenCalled()
  })

  it.each([
    ['wazzup', 'whatsapp'],
    ['wazzup', 'telegram'],
    ['max_direct', 'max'],
    ['vk_direct', 'vk'],
    ['telegram_bot', 'telegram'],
    ['avito_direct', 'avito'],
  ])(
    'keeps %s %s image metadata stable through initial, delta and reload',
    async (provider, platform) => {
      let canonical = image('IMAGE', { width: 1080, height: 1920, platform })
      let root = mountGrid([canonical], { provider })
      let liveProps = mounted.at(-1).props
      let initialStyle = root
        .querySelector('[data-single-image]')
        .getAttribute('style')
      let media = root.querySelector('img:not([data-media-backdrop])')
      Object.defineProperties(media, {
        naturalWidth: { value: 400, configurable: true },
        naturalHeight: { value: 400, configurable: true },
      })
      media.dispatchEvent(new Event('load'))
      await nextTick()
      expect(
        root.querySelector('[data-single-image]').getAttribute('style'),
      ).toBe(initialStyle)

      liveProps.images = [{ ...canonical }]
      await nextTick()
      expect(
        root.querySelector('[data-single-image]').getAttribute('style'),
      ).toBe(initialStyle)
      let reloaded = mountGrid([{ ...canonical }], { provider })
      expect(
        reloaded.querySelector('[data-single-image]').getAttribute('style'),
      ).toBe(initialStyle)
    },
  )

  it.each(['pending', 'available'])(
    'renders a canonical Wazzup image with %s download status',
    async (status) => {
      let ready = status === 'available'
      let root = mountRenderer(
        [
          image('WAZZUP-IMAGE', {
            status,
            url: ready ? '/api/private-wazzup-image' : null,
            download_url: ready ? '/api/private-wazzup-download' : null,
          }),
        ],
        { provider: 'wazzup' },
      )
      let imageButton = root.querySelector('[data-single-image]')

      expect(imageButton.disabled).toBe(!ready)
      expect(root.querySelector('img')?.getAttribute('src') ?? null).toBe(
        ready ? '/api/private-wazzup-image' : null,
      )
      expect(root.querySelector('[data-test-attachment-card]')).toBeNull()
      imageButton.click()
      await nextTick()
      expect(Boolean(root.querySelector('[data-test-lightbox]'))).toBe(ready)
    },
  )

  it.each([
    ['audio', 'data-test-audio'],
    ['video', 'data-test-video'],
    ['file', 'data-test-attachment-card'],
  ])(
    'routes a canonical Wazzup %s attachment to the shared component',
    (type, selector) => {
      let root = mountRenderer(
        [
          {
            id: 'WAZZUP-MEDIA',
            type,
            status: 'available',
            file_name: 'document.pdf',
          },
        ],
        { provider: 'wazzup' },
      )
      expect(root.querySelector(`[${selector}]`)).not.toBeNull()
      if (type !== 'file')
        expect(root.querySelector('[data-test-attachment-card]')).toBeNull()
      else expect(root.textContent).toContain('document.pdf')
    },
  )

  it('scales a small single-image preview inside the compact media bounds', () => {
    let root = mountGrid([image('I-1')])
    let wrapper = root.querySelector('[data-single-image]')
    let media = wrapper.querySelector('img')

    expect(root.querySelector('[data-image-grid]')).toBeNull()
    expect(wrapper.className).toContain('max-w-full')
    expect(wrapper.className).toContain('rounded-md')
    expect(wrapper.style.width).toBe('320px')
    expect(wrapper.style.aspectRatio).toBe('1 / 1')
    expect(media.getAttribute('width')).toBe('64')
    expect(media.getAttribute('height')).toBe('64')
    expect(media.className).toContain('w-full')
    expect(media.className).toContain('size-full')
    expect(media.className).not.toContain('w-auto')
    expect(media.className).toContain('object-contain')
    expect(media.className).not.toContain('object-cover')
  })

  it('keeps one portrait image compact above a separate document card', () => {
    let root = mountRenderer([
      image('I-1', { width: 600, height: 1200 }),
      {
        id: 'F-1',
        type: 'file',
        status: 'available',
        file_name: 'contract.pdf',
      },
    ])
    let renderer = root.querySelector('[data-attachment-renderer]')
    let media = root.querySelector('[data-single-image]')
    let document = root.querySelector('[data-test-attachment-card]')

    expect(renderer.className).toContain('max-w-[20rem]')
    expect(renderer.className).toContain('grid-cols-1')
    expect(renderer.className).not.toContain('max-w-full')
    expect(root.querySelector('[data-mixed-single-image-row]')).toBeNull()
    expect(root.querySelector('[data-media-side-line]')).toBeNull()
    expect(media.style.width).toBe('320px')
    expect(media.style.aspectRatio).toBe(`${320 / 360} / 1`)
    expect(media.className).toContain('justify-self-start')
    expect(media.querySelector('[data-media-backdrop]')).not.toBeNull()
    expect(
      media.querySelector('img:not([data-media-backdrop])').className,
    ).toContain('object-contain')
    expect(document.textContent).toContain('contract.pdf')
    expect(media.compareDocumentPosition(document)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
  })

  it('keeps multiple images in the existing cropped grid', () => {
    let root = mountGrid(
      Array.from({ length: 5 }, (_, index) => image(`I-${index + 1}`)),
    )
    let grid = root.querySelector('[data-image-grid]')
    let media = [...grid.querySelectorAll('img')]

    expect(root.querySelector('[data-single-image]')).toBeNull()
    expect(grid.className).toContain('grid-cols-2')
    expect(grid.className).toContain('w-[min(20rem,calc(100vw-3rem))]')
    expect(grid.querySelectorAll('button')).toHaveLength(4)
    expect(media.every((item) => item.className.includes('object-cover'))).toBe(
      true,
    )
    expect(grid.textContent).toContain('+1')
  })

  it('reserves the compact presentation width before video playback starts', () => {
    let root = mountRenderer([
      {
        id: 'MAX-VIDEO-1',
        type: 'video',
        status: 'available',
        video_source: 'local_file',
        playback_url: '/api/max-video',
        file_name: 'max-video.mp4',
      },
    ])
    let renderer = root.querySelector('[data-attachment-renderer]')

    expect(renderer.className).toContain('max-w-[20rem]')
    expect(renderer.className).toContain('grid-cols-1')
    expect(renderer.className).not.toContain('max-w-full')
    expect(root.querySelector('[data-test-video]')).not.toBeNull()
  })

  it('lets a single voice player use the full message bubble width', () => {
    let root = mountRenderer([
      {
        id: 'VOICE-1',
        type: 'audio',
        is_voice: true,
        status: 'available',
        url: '/private/voice.ogg',
      },
    ])
    let renderer = root.querySelector('[data-attachment-renderer]')

    expect(renderer.className).toContain('w-full')
    expect(renderer.className).toContain('min-w-0')
    expect(renderer.className).not.toContain('max-w-[20rem]')
  })

  it('renders videos and following image runs in provider order', () => {
    let root = mountRenderer([
      { id: 'V-1', type: 'video', status: 'external' },
      { id: 'V-2', type: 'video', status: 'external' },
      image('I-1'),
    ])
    let ordered = [
      ...root.querySelectorAll('[data-test-video], [data-single-image]'),
    ]

    expect(ordered.map((item) => item.dataset.id || 'images')).toEqual([
      'V-1',
      'V-2',
      'images',
    ])
  })

  it('renders a downloaded MAX sticker and a code-only fallback', () => {
    let root = mountRenderer([
      {
        id: 'S-1',
        type: 'sticker',
        status: 'available',
        mime_type: 'image/webp',
        url: '/media/sticker.webp',
      },
      {
        id: 'S-2',
        type: 'sticker',
        status: 'unsupported',
        file_name: 'max-sticker',
        fallback_text: 'Стикер MAX недоступен для загрузки',
      },
    ])

    expect(root.querySelector('img')?.getAttribute('src')).toBe(
      '/media/sticker.webp',
    )
    expect(root.textContent).toContain('Стикер MAX недоступен для загрузки')
  })

  it('keeps a forwarded sticker renderer content-sized', () => {
    let root = mountRenderer(
      [
        {
          id: 'S-1',
          type: 'sticker',
          status: 'available',
          mime_type: 'image/webp',
          url: '/media/sticker.webp',
        },
      ],
      { compactPreview: true },
    )
    let renderer = root.querySelector('[data-attachment-renderer]')
    let wrapper = renderer.querySelector('img').parentElement

    expect(renderer.className).toContain('w-fit')
    expect(renderer.className.split(/\s+/)).not.toContain('w-full')
    expect(wrapper.className).toContain('justify-self-start')
    expect(wrapper.className).toContain('size-40')
    expect(wrapper.className).not.toContain('w-fit')
    expect(root.querySelector('img').className).toContain('size-full')
  })

  it.each([false, true])(
    'reuses the compact sticker view for a decoded Wazzup WebP with compact preview %s',
    (compactPreview) => {
      let root = mountRenderer(
        [
          image('WAZZUP-WEBP', {
            width: 512,
            height: 512,
            mime_type: 'image/webp',
            is_sticker_candidate: true,
          }),
        ],
        { provider: 'wazzup', compactPreview },
      )
      let sticker = root.querySelector('[data-sticker-attachment]')
      expect(sticker).not.toBeNull()
      expect(sticker.className).toContain('size-40')
      expect(root.querySelector('[data-single-image]')).toBeNull()
      expect(
        root.querySelector('[data-attachment-renderer]').className,
      ).toContain('w-fit')
    },
  )

  it('keeps an ordinary Wazzup WebP photo in the shared image view', () => {
    let root = mountRenderer(
      [
        image('WEBP-PHOTO', {
          mime_type: 'image/webp',
          width: 512,
          height: 512,
        }),
      ],
      { provider: 'wazzup' },
    )
    expect(root.querySelector('[data-single-image]')).not.toBeNull()
    expect(root.querySelector('[data-sticker-attachment]')).toBeNull()
  })

  it('keeps pending media disabled and opens available media in lightbox', async () => {
    let pendingRoot = mountGrid([
      image('P-1', { status: 'pending', url: null }),
    ])
    let pending = pendingRoot.querySelector('[data-single-image]')
    expect(pending.disabled).toBe(true)
    expect(pending.querySelector('img')).toBeNull()
    expect(pending.querySelector('div').className).toContain('min-h-28')

    let root = mountRenderer([image('I-1')])
    root.querySelector('[data-single-image]').click()
    await nextTick()

    expect(root.querySelector('[data-test-lightbox]')).not.toBeNull()
    expect(root.querySelector('[data-test-lightbox]').dataset.index).toBe('0')
  })

  it('keeps a failed outbound VK image preview and shows the send failure', () => {
    let root = mountRenderer([image('VK-FAILED', { status: 'failed' })], {
      provider: 'vk_direct',
      outbound: true,
    })
    let wrapper = root.querySelector('[data-single-image]')
    let media = wrapper.querySelector('img:not([data-media-backdrop])')
    let failure = wrapper.querySelector('[data-vk-image-send-failed]')

    expect(wrapper.disabled).toBe(true)
    expect(media?.getAttribute('src')).toBe('/media/VK-FAILED.jpg')
    expect(failure?.textContent.trim()).toBe('Failed to send image to VK')
    expect(wrapper.textContent).not.toContain('Upload failed')

    let otherProvider = mountGrid([image('MAX-FAILED', { status: 'failed' })], {
      provider: 'max_direct',
      outbound: true,
    })
    expect(otherProvider.querySelector('img')).toBeNull()
    expect(otherProvider.textContent).toContain('Attachment unavailable')
    expect(
      otherProvider.querySelector('[data-vk-image-send-failed]'),
    ).toBeNull()
  })

  it('opens every image in one lightbox across separated visual groups', async () => {
    let root = mountRenderer([
      image('I-1'),
      { id: 'V-1', type: 'video', status: 'external' },
      image('I-2'),
      image('I-3'),
    ])
    let imageButtons = root.querySelectorAll(
      '[data-single-image], [data-image-grid] button',
    )

    imageButtons[1].click()
    await nextTick()

    let lightbox = root.querySelector('[data-test-lightbox]')
    expect(lightbox.textContent).toBe('I-1:image,I-2:image,I-3:image')
    expect(lightbox.dataset.index).toBe('1')
  })

  it('opens images and provider animations in one ordered gallery', async () => {
    let root = mountRenderer([
      image('PHOTO-1'),
      {
        id: 'VK-GIF',
        type: 'image',
        status: 'available',
        mime_type: 'image/gif',
        is_animated: true,
        url: '/media/vk.gif',
      },
      {
        id: 'TG-GIF',
        type: 'video',
        status: 'available',
        mime_type: 'video/mp4',
        is_animated: true,
        playback_url: '/media/telegram.mp4',
      },
      image('MAX-GIF', {
        mime_type: 'image/gif',
        url: '/media/max.gif',
      }),
    ])

    root.querySelector('[data-test-animation][data-id="TG-GIF"]').click()
    await nextTick()

    let lightbox = root.querySelector('[data-test-lightbox]')
    expect(lightbox.textContent).toBe(
      'PHOTO-1:image,VK-GIF:image,TG-GIF:animation,MAX-GIF:image',
    )
    expect(lightbox.dataset.index).toBe('2')
  })

  it('does not include animated stickers in the media gallery', async () => {
    let root = mountRenderer([
      image('PHOTO-1'),
      {
        id: 'STICKER-1',
        type: 'sticker',
        status: 'available',
        mime_type: 'video/webm',
        is_animated: true,
        url: '/media/sticker.webm',
      },
    ])

    root.querySelector('[data-single-image]').click()
    await nextTick()
    expect(root.querySelector('[data-test-lightbox]').textContent).toBe(
      'PHOTO-1:image',
    )
  })

  it('routes animated JSON stickers to the Lottie renderer', () => {
    let root = mountRenderer([
      {
        id: 'VK-STICKER-1',
        type: 'sticker',
        status: 'available',
        mime_type: 'application/json',
        is_animated: true,
        url: '/api/sticker',
        preview_url: '/api/sticker-preview',
      },
    ])

    expect(root.querySelector('[data-test-lottie-sticker]')?.dataset.id).toBe(
      'VK-STICKER-1',
    )
    expect(root.querySelector('[data-test-attachment-card]')).toBeNull()
  })

  it('routes animated images and videos to the common animation renderer', () => {
    let root = mountRenderer(
      [
        {
          id: 'GIF-1',
          type: 'video',
          status: 'available',
          is_animated: true,
        },
        {
          id: 'GIF-2',
          type: 'image',
          status: 'available',
          is_animated: true,
        },
      ],
      { compactPreview: true },
    )

    let animations = [...root.querySelectorAll('[data-test-animation]')]
    expect(animations.map((item) => item.dataset.id)).toEqual([
      'GIF-1',
      'GIF-2',
    ])
    expect(animations.every((item) => item.dataset.compact === 'true')).toBe(
      true,
    )
  })

  it('constrains forwarded voice to the compact attachment container', () => {
    let root = mountRenderer(
      [
        {
          id: 'VOICE-1',
          type: 'audio',
          status: 'available',
          is_voice: true,
          url: '/media/voice.ogg',
        },
      ],
      { compactPreview: true },
    )
    let renderer = root.querySelector('[data-attachment-renderer]')
    let audio = root.querySelector('[data-test-audio]')

    expect(renderer.className).toContain('w-full')
    expect(renderer.className).toContain('min-w-0')
    expect(renderer.className).not.toContain('w-fit')
    expect(audio.dataset.id).toBe('VOICE-1')
    expect(audio.dataset.compact).toBe('true')
  })

  it('letterboxes a portrait forwarded image and keeps the lightbox source', async () => {
    let root = mountRenderer(
      [image('PORTRAIT', { width: 1080, height: 1920 })],
      { compactPreview: true },
    )
    let preview = root.querySelector('[data-single-image]')

    expect(preview.style.width).toBe('320px')
    expect(preview.style.aspectRatio).toBe(`${320 / 280} / 1`)
    expect(preview.querySelector('[data-media-backdrop]')).not.toBeNull()
    expect(
      preview.querySelector('img:not([data-media-backdrop])').className,
    ).toContain('object-contain')

    preview.click()
    await nextTick()
    expect(root.querySelector('[data-test-lightbox]')).not.toBeNull()
  })

  it('keeps a portrait frame stable while decoding, refreshing and reloading without initial dimensions', async () => {
    let root = mountGrid([image('UNKNOWN', { width: null, height: null })])
    let liveProps = mounted.at(-1).props
    let preview = root.querySelector('[data-single-image]')
    let media = preview.querySelector('img:not([data-media-backdrop])')
    let initialStyle = preview.getAttribute('style')

    expect(preview.style.aspectRatio).toBe(`${320 / 360} / 1`)
    expect(media.className).toContain('absolute')
    expect(media.className).toContain('inset-0')
    Object.defineProperty(media, 'naturalWidth', {
      configurable: true,
      value: 900,
    })
    Object.defineProperty(media, 'naturalHeight', {
      configurable: true,
      value: 1600,
    })
    media.dispatchEvent(new Event('load'))
    await nextTick()

    expect(preview.style.width).toBe('320px')
    expect(preview.style.aspectRatio).toBe(`${320 / 360} / 1`)
    expect(preview.getAttribute('style')).toBe(initialStyle)
    expect(preview.querySelector('[data-media-backdrop]')).not.toBeNull()

    // Full chat refresh replaces attachment objects without replacing the
    // already-loaded <img>. Its natural dimensions must survive that update.
    liveProps.images = [image('UNKNOWN', { width: null, height: null })]
    await nextTick()
    expect(preview.getAttribute('style')).toBe(initialStyle)
    expect(preview.querySelector('[data-media-backdrop]')).not.toBeNull()
    expect(preview.querySelector('img:not([data-media-backdrop])')).toBe(media)

    let refreshed = image('UNKNOWN', {
      url: '/api/refreshed-portrait',
      width: 900,
      height: 1600,
    })
    liveProps.images = [refreshed]
    await nextTick()
    expect(preview.getAttribute('style')).toBe(initialStyle)
    let reloaded = mountGrid([refreshed])
    expect(
      reloaded.querySelector('[data-single-image]').getAttribute('style'),
    ).toBe(initialStyle)
  })

  it('caps a forwarded album grid at 320 by 280 pixels', () => {
    let root = mountRenderer(
      Array.from({ length: 4 }, (_, index) => image(`I-${index + 1}`)),
      { compactPreview: true },
    )
    let grid = root.querySelector('[data-image-grid]')

    expect(grid.style.maxHeight).toBe('280px')
    expect(grid.style.aspectRatio).toBe(`${320 / 280} / 1`)
    expect(grid.className).toContain('grid-rows-2')
  })
})
