import { createApp, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/components/LeadMessenger/AttachmentCard.vue', () => ({
  default: {
    props: ['attachment'],
    template:
      '<div data-test-animation-fallback>{{ attachment.file_name }}</div>',
  },
}))

import AnimatedMediaAttachment from '@/components/LeadMessenger/AnimatedMediaAttachment.vue'

let mounted = []

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
})

function mountAnimation(attachment, compactPreview = false, onOpenMedia) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(AnimatedMediaAttachment, {
    attachment,
    compactPreview,
    onOpenMedia,
  })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return root
}

function animation(overrides = {}) {
  return {
    id: 'ANIMATION-1',
    type: 'video',
    status: 'available',
    mime_type: 'video/mp4',
    file_name: 'animation.gif.mp4',
    playback_url: '/api/animation',
    download_url: '/api/download-animation',
    width: 220,
    height: 166,
    is_animated: true,
    ...overrides,
  }
}

describe('animated messenger media', () => {
  it('autoplays an MP4 animation without inline controls or a file card', () => {
    let root = mountAnimation(animation())
    let video = root.querySelector('[data-animated-video]')

    expect(video.autoplay).toBe(true)
    expect(video.loop).toBe(true)
    expect(video.muted).toBe(true)
    expect(video.controls).toBe(false)
    expect(video.hasAttribute('playsinline')).toBe(true)
    expect(root.querySelector('[data-test-animation-fallback]')).toBeNull()
    expect(root.textContent).not.toContain('animation.gif.mp4')
  })

  it('delegates fullscreen opening to the common media lightbox', async () => {
    let onOpenMedia = vi.fn()
    let attachment = animation({ width: 1080, height: 1920 })
    let root = mountAnimation(attachment, true, onOpenMedia)
    let preview = root.querySelector('[data-animated-media]')

    expect(preview.style.width).toBe('320px')
    expect(preview.style.aspectRatio).toBe(`${320 / 280} / 1`)
    expect(preview.querySelector('video').className).toContain('object-contain')

    preview.click()
    await nextTick()
    expect(onOpenMedia).toHaveBeenCalledOnce()
    expect(onOpenMedia).toHaveBeenCalledWith(attachment)
    expect(document.body.querySelector('[data-animated-viewer]')).toBeNull()
  })

  it('renders a real GIF through an image and falls back safely on error', async () => {
    let root = mountAnimation(
      animation({
        type: 'image',
        mime_type: 'image/gif',
        url: '/api/animation.gif',
        playback_url: null,
      }),
    )
    let image = root.querySelector('[data-animated-image]')
    expect(image.getAttribute('src')).toBe('/api/animation.gif')
    expect(root.querySelector('video')).toBeNull()

    image.dispatchEvent(new Event('error'))
    await nextTick()
    expect(root.querySelector('[data-test-animation-fallback]')).not.toBeNull()
  })

  it('adds a blurred backdrop without cropping a portrait animation', () => {
    let root = mountAnimation(
      animation({
        type: 'image',
        mime_type: 'image/gif',
        url: '/api/portrait.gif',
        playback_url: null,
        width: 900,
        height: 1600,
      }),
    )
    let frame = root.querySelector('[data-animated-media]')

    expect(frame.style.width).toBe('320px')
    expect(frame.style.aspectRatio).toBe(`${320 / 360} / 1`)
    expect(frame.querySelector('[data-media-backdrop]')).not.toBeNull()
    expect(frame.querySelector('[data-animated-image]').className).toContain(
      'object-contain',
    )
  })
})
