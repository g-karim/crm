/* eslint-disable vue/one-component-per-file */
import { createApp, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/components/LeadMessenger/ImageLightbox.vue', () => ({
  default: {
    props: ['images', 'initialIndex'],
    template:
      '<div data-test-lightbox :data-index="initialIndex">{{ images.length }}</div>',
  },
}))

vi.mock('@/components/LeadMessenger/AttachmentCard.vue', () => ({
  default: {
    props: ['attachment'],
    template: '<div data-test-attachment-card>{{ attachment.file_name }}</div>',
  },
}))

vi.mock('@/components/LeadMessenger/MessengerAudioPlayer.vue', () => ({
  default: { template: '<div data-test-audio />' },
}))

vi.mock('@/components/LeadMessenger/VideoAttachment.vue', () => ({
  default: { template: '<div data-test-video />' },
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

function mountRenderer(attachments) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(AttachmentRenderer, { attachments })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return root
}

describe('messenger image layout', () => {
  it('scales a small single-image preview to the presentation width', () => {
    let root = mountGrid([image('I-1')])
    let wrapper = root.querySelector('[data-single-image]')
    let media = wrapper.querySelector('img')

    expect(root.querySelector('[data-image-grid]')).toBeNull()
    expect(wrapper.className).toContain('w-[22.5rem]')
    expect(wrapper.className).toContain('max-w-full')
    expect(wrapper.className).toContain('rounded-md')
    expect(media.getAttribute('width')).toBe('64')
    expect(media.getAttribute('height')).toBe('64')
    expect(media.className).toContain('w-full')
    expect(media.className).toContain('h-auto')
    expect(media.className).not.toContain('w-auto')
    expect(media.className).not.toContain('max-h-[22rem]')
    expect(media.className).not.toContain('size-full')
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
    let mediaRow = root.querySelector('[data-mixed-single-image-row]')
    let media = root.querySelector('[data-single-image]')
    let document = root.querySelector('[data-test-attachment-card]')

    expect(renderer.className).toContain('max-w-[28rem]')
    expect(mediaRow.className).toContain('justify-center')
    expect(mediaRow.querySelectorAll('[data-media-side-line]')).toHaveLength(2)
    expect(
      [...mediaRow.querySelectorAll('[data-media-side-line]')].every((line) =>
        line.className.includes('bg-outline-gray-1'),
      ),
    ).toBe(true)
    expect(media.className).toContain('w-[16.5rem]')
    expect(media.className).toContain('justify-self-start')
    expect(media.querySelector('img').className).toContain('h-auto')
    expect(media.querySelector('img').className).not.toContain('object-cover')
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
    expect(grid.className).toContain('w-[min(28rem,calc(100vw-3rem))]')
    expect(grid.querySelectorAll('button')).toHaveLength(4)
    expect(media.every((item) => item.className.includes('object-cover'))).toBe(
      true,
    )
    expect(grid.textContent).toContain('+1')
  })

  it('keeps pending media disabled and opens available media in lightbox', async () => {
    let pendingRoot = mountGrid([
      image('P-1', { status: 'pending', url: null }),
    ])
    let pending = pendingRoot.querySelector('[data-single-image]')
    expect(pending.disabled).toBe(true)
    expect(pending.querySelector('img')).toBeNull()
    expect(pending.querySelector('div').className).toContain('min-h-28')

    let root = mountGrid([image('I-1')])
    root.querySelector('[data-single-image]').click()
    await nextTick()

    expect(root.querySelector('[data-test-lightbox]')).not.toBeNull()
    expect(root.querySelector('[data-test-lightbox]').dataset.index).toBe('0')
  })
})
