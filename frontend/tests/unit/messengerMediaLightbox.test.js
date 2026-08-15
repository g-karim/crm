import { createApp, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import MediaLightbox from '@/components/LeadMessenger/MediaLightbox.vue'

let mounted = []

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
  document.body.style.overflow = ''
})

function mountLightbox(items, initialIndex = 0, onClose) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(MediaLightbox, { items, initialIndex, onClose })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return document.body
}

const items = [
  {
    id: 'I-1',
    kind: 'image',
    url: '/media/one.jpg',
    download_url: '/api/download/I-1',
    file_name: 'one.jpg',
  },
  {
    id: 'GIF-1',
    kind: 'animation',
    url: '/media/animation.mp4',
    download_url: '/api/download/GIF-1',
    file_name: 'animation.mp4',
  },
  { id: 'I-2', kind: 'image', url: '/media/two.gif', file_name: 'two.gif' },
]

describe('messenger media lightbox', () => {
  it('uses the same toolbar and active feedback for images and animations', async () => {
    let body = mountLightbox(items)
    let controls = [
      body.querySelector('[data-lightbox-previous]'),
      body.querySelector('[data-lightbox-next]'),
      body.querySelector('[data-lightbox-download]'),
      body.querySelector('[data-lightbox-zoom-out]'),
      body.querySelector('[data-lightbox-reset]'),
      body.querySelector('[data-lightbox-zoom-in]'),
      body.querySelector('[data-lightbox-close]'),
    ]
    controls.forEach((control) => {
      expect(control.className).toContain('transition')
      expect(control.className).toContain('active:scale-90')
    })

    body.querySelector('[data-lightbox-next]').click()
    await nextTick()
    let video = body.querySelector('[data-lightbox-animation]')
    expect(video).not.toBeNull()
    expect(video.autoplay).toBe(true)
    expect(video.loop).toBe(true)
    expect(video.muted).toBe(true)
    expect(video.controls).toBe(false)
    expect(video.hasAttribute('playsinline')).toBe(true)
    expect(
      body.querySelector('[data-lightbox-download]').getAttribute('href'),
    ).toBe('/api/download/GIF-1')
  })

  it('zooms every media type and resets the view during mixed navigation', async () => {
    let body = mountLightbox(items)
    let viewport = body.querySelector('[data-lightbox-viewport]')
    let wheel = new WheelEvent('wheel', {
      bubbles: true,
      cancelable: true,
      deltaY: -100,
      clientX: 100,
      clientY: 100,
    })

    expect(viewport.dispatchEvent(wheel)).toBe(false)
    await nextTick()
    expect(
      body.querySelector('[data-lightbox-image]').style.transform,
    ).toContain('scale(1.25)')

    body.querySelector('[data-lightbox-next]').click()
    await nextTick()
    expect(
      body.querySelector('[data-lightbox-animation]').style.transform,
    ).toContain('scale(1)')
    expect(body.querySelector('[data-lightbox-reset]').textContent).toContain(
      '100%',
    )

    body.querySelector('[data-lightbox-next]').click()
    await nextTick()
    expect(
      body.querySelector('[data-lightbox-image]').getAttribute('src'),
    ).toBe('/media/two.gif')
  })

  it('clamps zoom controls and shows a safe unavailable state on load error', async () => {
    let body = mountLightbox(items, 1)
    for (let index = 0; index < 30; index += 1) {
      body.querySelector('[data-lightbox-zoom-in]').click()
    }
    await nextTick()
    expect(body.querySelector('[data-lightbox-reset]').textContent).toContain(
      '500%',
    )
    expect(body.querySelector('[data-lightbox-zoom-in]').disabled).toBe(true)

    body
      .querySelector('[data-lightbox-animation]')
      .dispatchEvent(new Event('error'))
    await nextTick()
    expect(
      body.querySelector('[data-lightbox-unavailable]').textContent,
    ).toContain('Медиа недоступно')
    expect(body.querySelector('[data-lightbox-animation]')).toBeNull()
    expect(body.querySelector('[data-lightbox-zoom-in]').disabled).toBe(true)
  })

  it('supports keyboard navigation and closes from Escape or the backdrop', async () => {
    let onClose = vi.fn()
    let body = mountLightbox(items, 0, onClose)

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }))
    await nextTick()
    expect(body.querySelector('[data-lightbox-animation]')).not.toBeNull()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    body.querySelector('[data-lightbox-viewport]').click()
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('locks body scrolling only while mounted', () => {
    document.body.style.overflow = 'clip'
    mountLightbox(items)
    expect(document.body.style.overflow).toBe('hidden')

    mounted[0].app.unmount()
    mounted = []
    expect(document.body.style.overflow).toBe('clip')
  })
})
