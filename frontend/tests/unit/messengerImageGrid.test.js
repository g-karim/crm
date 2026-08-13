/* eslint-disable vue/one-component-per-file */
import { createApp, nextTick } from 'vue'
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
  default: { template: '<div data-test-audio />' },
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

function mountGrid(images) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(ImageGrid, { images })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
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
    expect(renderer.className).toContain('w-fit')
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
    expect(renderer.className).toContain('max-w-full')
    expect(renderer.className.split(/\s+/)).toContain('w-fit')
    expect(root.querySelector('[data-test-video]')).not.toBeNull()
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

  it('uses loaded image dimensions when provider metadata is missing', async () => {
    let root = mountGrid([image('UNKNOWN', { width: null, height: null })])
    let preview = root.querySelector('[data-single-image]')
    let media = preview.querySelector('img:not([data-media-backdrop])')

    expect(preview.style.aspectRatio).toBe('')
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
    expect(preview.querySelector('[data-media-backdrop]')).not.toBeNull()
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
