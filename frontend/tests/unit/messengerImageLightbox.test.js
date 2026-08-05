import { createApp, nextTick } from 'vue'
import { afterEach, describe, expect, it } from 'vitest'

import ImageLightbox from '@/components/LeadMessenger/ImageLightbox.vue'

let mounted = []

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
  document.body.style.overflow = ''
})

function mountLightbox(images, initialIndex = 0) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(ImageLightbox, { images, initialIndex })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return document.body
}

const images = [
  {
    id: 'I-1',
    url: '/media/one.jpg',
    download_url: '/api/download/I-1',
    file_name: 'one.jpg',
  },
  { id: 'I-2', url: '/media/two.jpg', file_name: 'two.jpg' },
]

describe('messenger image lightbox', () => {
  it('centers navigation icons and gives every control active feedback', () => {
    let body = mountLightbox(images)
    let previous = body.querySelector('[data-lightbox-previous]')
    let next = body.querySelector('[data-lightbox-next]')

    expect(previous.className).toContain('place-items-center')
    expect(next.className).toContain('place-items-center')
    expect(previous.querySelector('span').className).toContain(
      'place-items-center',
    )
    let controls = [
      previous,
      next,
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
  })

  it('zooms with a cancelled wheel event and clamps toolbar controls', async () => {
    let body = mountLightbox(images)
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
    expect(body.querySelector('[data-lightbox-image]').style.transform).toContain(
      'scale(1.25)',
    )

    for (let index = 0; index < 30; index += 1) {
      body.querySelector('[data-lightbox-zoom-in]').click()
    }
    await nextTick()
    expect(body.querySelector('[data-lightbox-reset]').textContent).toContain(
      '500%',
    )
    expect(body.querySelector('[data-lightbox-zoom-in]').disabled).toBe(true)
  })

  it('provides the authorized download URL and resets zoom on navigation', async () => {
    let body = mountLightbox(images)
    expect(
      body.querySelector('[data-lightbox-download]').getAttribute('href'),
    ).toBe('/api/download/I-1')

    body.querySelector('[data-lightbox-zoom-in]').click()
    body.querySelector('[data-lightbox-next]').click()
    await nextTick()

    expect(body.querySelector('[data-lightbox-image]').getAttribute('src')).toBe(
      '/media/two.jpg',
    )
    expect(body.querySelector('[data-lightbox-reset]').textContent).toContain(
      '100%',
    )
    expect(body.querySelector('[data-lightbox-download]')).toBeNull()
  })

  it('locks body scrolling only while mounted', () => {
    document.body.style.overflow = 'clip'
    mountLightbox(images)
    expect(document.body.style.overflow).toBe('hidden')

    mounted[0].app.unmount()
    mounted = []
    expect(document.body.style.overflow).toBe('clip')
  })
})
