import { createApp, nextTick, reactive } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/components/LeadMessenger/AttachmentCard.vue', () => ({
  default: {
    props: ['attachment'],
    template:
      '<div data-test-attachment-card :data-status="attachment.status">{{ attachment.file_name }}</div>',
  },
}))

vi.mock('@/components/Icons/LoadingIndicator.vue', () => ({
  default: { template: '<span data-test-loading />' },
}))

vi.mock(
  '~icons/lucide/play',
  () => ({ default: { template: '<span data-test-play-icon />' } }),
  { virtual: true },
)

import VideoAttachment from '@/components/LeadMessenger/VideoAttachment.vue'

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

function mountVideo(attachment, provider = '', props = {}, refreshAttachments) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(VideoAttachment, { attachment, provider, ...props })
  if (refreshAttachments)
    app.provide('refreshMessengerAttachments', refreshAttachments)
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return root
}

describe('external messenger video', () => {
  it.each(['pending', 'failed'])(
    'waits for a %s video snapshot without per-media refresh controls',
    async (status) => {
      vi.useFakeTimers()
      let refresh = vi.fn().mockResolvedValue(undefined)
      let attachment = reactive({
        id: 'PARTNER-POSTER-ONLY',
        type: 'video',
        status,
        preview_url: '/api/private-poster',
        width: 1080,
        height: 1920,
      })
      let root = mountVideo(attachment, 'wazzup', {}, refresh)
      expect(root.querySelector('[data-test-attachment-card]')).toBeNull()
      expect(root.querySelector('video[controls]')).toBeNull()
      if (status === 'pending') {
        expect(root.querySelector('[data-video-refresh]')).toBeNull()
        await vi.advanceTimersByTimeAsync(30000)
      }
      expect(root.querySelector('[data-video-refresh]')).toBeNull()
      expect(refresh).not.toHaveBeenCalled()
      expect(root.querySelector('[data-video-loading]')).toBeNull()

      Object.assign(attachment, {
        status: 'available',
        mime_type: 'video/mp4',
        playback_url: '/api/private-video',
      })
      await nextTick()
      expect(root.querySelector('[data-video-refresh]')).toBeNull()
      root.querySelector('button[aria-label="Play Video"]').click()
      await nextTick()
      expect(
        root.querySelector('video[controls]').getAttribute('aria-label'),
      ).toBe('Video')
    },
  )

  it('keeps poster-only failure safe without adding a refresh action', async () => {
    let refresh = vi
      .fn()
      .mockRejectedValue(new Error('https://provider.test/?secret=private'))
    let root = mountVideo(
      {
        id: 'PARTNER-REFRESH-ERROR',
        type: 'video',
        status: 'failed',
        preview_url: '/api/private-poster',
      },
      'wazzup',
      {},
      refresh,
    )
    expect(root.querySelector('[data-video-refresh]')).toBeNull()
    expect(refresh).not.toHaveBeenCalled()
    expect(root.textContent).not.toContain('secret=private')
  })

  it('keeps pending VK external-only video on its existing source action', () => {
    let refresh = vi.fn()
    let root = mountVideo(
      {
        id: 'VK-PENDING-EXTERNAL-POSTER',
        type: 'video',
        status: 'pending',
        video_source: 'provider_embed',
        preview_url: '/api/private-poster',
        open_url: '/api/open-vk',
      },
      'vk_direct',
      {},
      refresh,
    )
    expect(root.querySelector('[data-video-refresh]')).toBeNull()
    expect(root.textContent).toContain('Available only on VK')
    expect(
      root.querySelector('[data-video-external-action]').getAttribute('href'),
    ).toBe('/api/open-vk')
    expect(refresh).not.toHaveBeenCalled()
  })

  it.each(['whatsapp', 'telegram'])(
    'keeps %s Partner geometry across initial load, delta, refresh and reload',
    async (platform) => {
      let attachment = reactive({
        id: `PARTNER-${platform}-VIDEO`,
        type: 'video',
        status: 'available',
        mime_type: 'video/mp4',
        playback_url: '/api/private-partner-video',
        preview_url: '/api/private-partner-poster',
        width: 1080,
        height: 1920,
        duration_ms: 4500,
      })
      let root = mountVideo(attachment, 'wazzup')
      let geometry = () => ({
        width: root.firstElementChild.style.width,
        maxWidth: root.firstElementChild.style.maxWidth,
        ratio: root.querySelector('[data-video-frame]').style.aspectRatio,
      })
      let initialGeometry = geometry()

      // A landscape poster must not replace the portrait video's geometry.
      let poster = root.querySelector('img:not([data-media-backdrop])')
      Object.defineProperties(poster, {
        naturalWidth: { configurable: true, value: 640 },
        naturalHeight: { configurable: true, value: 360 },
      })
      poster.dispatchEvent(new Event('load'))
      await nextTick()
      expect(geometry()).toEqual(initialGeometry)

      Object.assign(attachment, { duration_ms: 4600, status: 'available' })
      await nextTick()
      expect(geometry()).toEqual(initialGeometry)

      root.querySelector('button[aria-label="Play Video"]').click()
      await nextTick()
      let video = root.querySelector('video[controls]')
      Object.defineProperties(video, {
        videoWidth: { configurable: true, value: 1080 },
        videoHeight: { configurable: true, value: 1920 },
        duration: { configurable: true, value: 4.6 },
      })
      video.dispatchEvent(new Event('loadedmetadata'))
      video.dispatchEvent(new Event('playing'))
      await nextTick()
      expect(geometry()).toEqual(initialGeometry)

      // Reload/refresh changes the projection, not the media identity.
      attachment.playback_url = '/api/private-partner-video?refresh=1'
      await nextTick()
      expect(root.querySelector('video[controls]')).toBeNull()
      expect(
        root.querySelector('button[aria-label="Play Video"]'),
      ).not.toBeNull()
      expect(geometry()).toEqual(initialGeometry)

      let reloaded = mountVideo({ ...attachment }, 'wazzup')
      expect(reloaded.firstElementChild.style.width).toBe(initialGeometry.width)
      expect(
        reloaded.querySelector('[data-video-frame]').style.aspectRatio,
      ).toBe(initialGeometry.ratio)
      expect(root.firstElementChild.className).toContain('min-w-0')
    },
  )

  it.each(['whatsapp', 'telegram'])(
    'recovers a %s Partner video when a pending delta becomes available',
    async (platform) => {
      let attachment = reactive({
        id: `PARTNER-${platform}-PENDING`,
        type: 'video',
        status: 'downloading',
        mime_type: 'video/mp4',
      })
      let root = mountVideo(attachment, 'wazzup')
      expect(root.querySelector('button[aria-label="Play Video"]')).toBeNull()
      Object.assign(attachment, {
        status: 'available',
        playback_url: '/api/downloaded-video',
        width: 720,
        height: 720,
      })
      await nextTick()

      expect(root.querySelector('[data-test-attachment-card]')).toBeNull()
      expect(root.querySelector('[data-video-frame]').style.aspectRatio).toBe(
        '1 / 1',
      )
      root.querySelector('button[aria-label="Play Video"]').click()
      await nextTick()
      expect(root.querySelector('video[controls]').getAttribute('src')).toBe(
        '/api/downloaded-video',
      )
    },
  )

  it('renders generic square video notes with native video controls', async () => {
    let root = mountVideo(
      {
        id: 'PARTNER-GENERIC-NOTE',
        type: 'video',
        status: 'available',
        mime_type: 'video/mp4',
        playback_url: '/api/private-note',
        width: 384,
        height: 384,
      },
      'wazzup',
    )
    root.querySelector('button[aria-label="Play Video"]').click()
    await nextTick()

    expect(root.querySelector('[data-video-frame]').style.aspectRatio).toBe(
      '1 / 1',
    )
    expect(
      root.querySelector('video[controls]').hasAttribute('playsinline'),
    ).toBe(true)
    expect(root.querySelector('video[controls]').className).toContain(
      'object-contain',
    )
  })

  it('ends stalled browser loading and retries only on a user action', async () => {
    vi.useFakeTimers()
    let play = vi
      .spyOn(HTMLMediaElement.prototype, 'play')
      .mockResolvedValue(undefined)
    let root = mountVideo(
      {
        id: 'PARTNER-STALLED',
        type: 'video',
        status: 'available',
        mime_type: 'video/mp4',
        playback_url: '/api/private-video',
      },
      'wazzup',
    )
    root.querySelector('button[aria-label="Play Video"]').click()
    await nextTick()
    expect(root.querySelector('[data-video-loading]')).not.toBeNull()

    await vi.advanceTimersByTimeAsync(15000)
    root.querySelector('video[controls]').dispatchEvent(new Event('stalled'))
    await vi.advanceTimersByTimeAsync(5000)
    await nextTick()
    expect(root.querySelector('[data-video-loading]')).toBeNull()
    expect(root.textContent).toContain('Video unavailable')
    expect(root.textContent).toContain('Try Again')
    expect(play).toHaveBeenCalledTimes(1)

    root.querySelector('button').click()
    await nextTick()
    expect(play).toHaveBeenCalledTimes(2)
    expect(root.querySelector('video[controls]')).not.toBeNull()
    root.querySelector('video[controls]').dispatchEvent(new Event('playing'))
    await vi.advanceTimersByTimeAsync(20000)
    expect(root.querySelector('[data-video-loading]')).toBeNull()
    expect(root.textContent).not.toContain('Video unavailable')
  })

  it('clears a failed local player after the same attachment receives a fresh projection', async () => {
    let attachment = reactive({
      id: 'PARTNER-FAILED-PLAYER',
      type: 'video',
      status: 'available',
      mime_type: 'video/mp4',
      playback_url: '/api/private-video',
    })
    let root = mountVideo(attachment, 'wazzup')
    root.querySelector('button[aria-label="Play Video"]').click()
    await nextTick()
    root.querySelector('video[controls]').dispatchEvent(new Event('error'))
    await nextTick()
    expect(root.querySelector('button[aria-label="Play Video"]')).toBeNull()
    expect(root.textContent).toContain('Try Again')

    attachment.playback_url = '/api/private-video?refresh=1'
    await nextTick()
    expect(root.querySelector('button[aria-label="Play Video"]')).not.toBeNull()
    expect(root.textContent).not.toContain('Try Again')
  })

  it('leaves native controls available when the browser blocks programmatic playback', async () => {
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockRejectedValue(
      new DOMException('Playback blocked', 'NotAllowedError'),
    )
    let root = mountVideo(
      {
        id: 'PARTNER-BROWSER-POLICY',
        type: 'video',
        status: 'available',
        mime_type: 'video/mp4',
        playback_url: '/api/private-video',
      },
      'wazzup',
    )
    root.querySelector('button[aria-label="Play Video"]').click()
    await nextTick()
    await Promise.resolve()
    await nextTick()

    expect(root.querySelector('[data-video-loading]')).toBeNull()
    expect(root.querySelector('video[controls]')).not.toBeNull()
    expect(root.textContent).not.toContain('Try Again')
  })

  it('shows a safe retry after a rejected codec without exposing browser diagnostics', async () => {
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockRejectedValue(
      new DOMException(
        'Secret provider URL in browser diagnostics',
        'NotSupportedError',
      ),
    )
    let root = mountVideo(
      {
        id: 'PARTNER-CODEC-FAILURE',
        type: 'video',
        status: 'available',
        mime_type: 'video/mp4',
        playback_url: '/api/private-video',
      },
      'wazzup',
    )
    root.querySelector('button[aria-label="Play Video"]').click()
    await nextTick()
    await Promise.resolve()
    await nextTick()

    expect(root.querySelector('[data-video-loading]')).toBeNull()
    expect(root.querySelector('video[controls]')).toBeNull()
    expect(root.textContent).toContain('Video unavailable')
    expect(root.textContent).toContain('Try Again')
    expect(root.textContent).not.toContain('Secret provider URL')
  })

  it.each(['max_direct', 'vk_direct', 'telegram_bot'])(
    'preserves %s local playback after buffering and a browser error',
    async (provider) => {
      let root = mountVideo(
        {
          id: `${provider}-LOCAL`,
          type: 'video',
          status: 'available',
          video_source: 'local_file',
          mime_type: 'video/mp4',
          playback_url: '/api/private-video',
          width: 1920,
          height: 1080,
        },
        provider,
      )
      let ratio = root.querySelector('[data-video-frame]').style.aspectRatio
      root.querySelector('button[aria-label="Play Video"]').click()
      await nextTick()
      let video = root.querySelector('video[controls]')
      video.dispatchEvent(new Event('waiting'))
      video.dispatchEvent(new Event('playing'))
      await nextTick()
      expect(root.querySelector('[data-video-loading]')).toBeNull()
      expect(root.querySelector('[data-video-frame]').style.aspectRatio).toBe(
        ratio,
      )

      video.dispatchEvent(new Event('error'))
      await nextTick()
      expect(root.textContent).toContain('Try Again')
      root.querySelector('button').click()
      await nextTick()
      expect(root.querySelector('video[controls]')).not.toBeNull()
      expect(root.querySelector('[data-video-frame]').style.aspectRatio).toBe(
        ratio,
      )
    },
  )

  it('plays a downloaded Wazzup video through the protected projection', async () => {
    let root = mountVideo(
      {
        id: 'WAZZUP-VIDEO',
        type: 'video',
        status: 'available',
        mime_type: 'video/mp4',
        file_name: 'clip.mp4',
        url: '/api/private-wazzup-video',
      },
      'wazzup',
    )

    root.querySelector('button[aria-label="Play Video"]').click()
    await nextTick()
    expect(root.querySelector('video[controls]')?.getAttribute('src')).toBe(
      '/api/private-wazzup-video',
    )
    expect(root.querySelector('a')).toBeNull()
    expect(root.querySelector('[data-test-attachment-card]')).toBeNull()
  })

  it('translates attachment processing status at the display boundary', () => {
    let originalTranslate = globalThis.__
    globalThis.__ = (message) =>
      message === 'Processing' ? 'Обрабатывается' : message
    try {
      let root = mountVideo({
        id: 'VIDEO-PROCESSING',
        type: 'video',
        status: 'processing',
        file_name: 'video.mp4',
      })

      expect(root.textContent).toContain('Обрабатывается')
      expect(root.textContent).not.toContain('Processing')
    } finally {
      globalThis.__ = originalTranslate
    }
  })

  it('letterboxes portrait previews and keeps landscape proportions', () => {
    let portrait = mountVideo({
      id: 'VIDEO-PORTRAIT',
      type: 'video',
      status: 'external',
      video_source: 'external',
      preview_url: '/api/portrait-preview',
      width: 1080,
      height: 1920,
    })
    let landscape = mountVideo({
      id: 'VIDEO-LANDSCAPE',
      type: 'video',
      status: 'external',
      video_source: 'external',
      preview_url: '/api/landscape-preview',
      width: 1920,
      height: 1080,
    })

    expect(portrait.firstElementChild.style.width).toBe('320px')
    expect(portrait.firstElementChild.style.maxWidth).toBe('100%')
    expect(portrait.querySelector('[data-video-frame]').style.aspectRatio).toBe(
      `${320 / 360} / 1`,
    )
    expect(portrait.querySelector('[data-media-backdrop]')).not.toBeNull()
    expect(
      portrait.querySelector('img:not([data-media-backdrop])').className,
    ).toContain('object-contain')
    expect(landscape.firstElementChild.style.width).toBe('320px')
    expect(
      landscape.querySelector('[data-video-frame]').style.aspectRatio,
    ).toBe(`${1920 / 1080} / 1`)
  })

  it('shows the saved preview and metadata with a neutral source action', () => {
    let root = mountVideo({
      id: 'VIDEO-1',
      type: 'video',
      status: 'external',
      video_source: 'external',
      mime_type: 'image/jpeg',
      file_name: 'preview.jpg',
      preview_url: '/api/private-preview',
      open_url: '/api/open-vk',
      title: 'Видео клиента',
      duration_ms: 65000,
    })

    expect(
      root.querySelector('img:not([data-media-backdrop])')?.getAttribute('src'),
    ).toBe('/api/private-preview')
    expect(root.textContent).not.toContain('Видео клиента')
    expect(root.textContent).not.toContain('preview.jpg')
    expect(root.textContent).toContain('1:05')
    expect(root.textContent).toContain('Open Source')
    expect(root.textContent).not.toContain('Открыть в VK')
    expect(root.querySelector('a')?.getAttribute('href')).toBe('/api/open-vk')
    expect(root.querySelector('video')).toBeNull()
    expect(root.querySelector('iframe')).toBeNull()
    expect(root.querySelector('[data-test-attachment-card]')).toBeNull()
  })

  it('hides the source action only for MAX video', () => {
    let maxRoot = mountVideo(
      {
        id: 'MAX-VIDEO-1',
        type: 'video',
        status: 'external',
        video_source: 'external',
        file_name: 'max-video.mp4',
        preview_url: '/api/private-preview',
        open_url: '/api/open-max',
      },
      'max_direct',
    )
    let vkRoot = mountVideo(
      {
        id: 'VK-VIDEO-1',
        type: 'video',
        status: 'external',
        video_source: 'external',
        file_name: 'vk-video.mp4',
        preview_url: '/api/private-preview',
        open_url: '/api/open-vk',
      },
      'vk_direct',
    )

    expect(maxRoot.textContent).not.toContain('Open Source')
    expect(maxRoot.querySelector('a')).toBeNull()
    expect(vkRoot.textContent).toContain('Available only on VK')
    expect(vkRoot.textContent).toContain('Watch on VK Video')
    expect(vkRoot.querySelector('a')?.getAttribute('href')).toBe('/api/open-vk')
    expect(
      vkRoot.querySelector('[data-video-external-action]').className,
    ).toContain('w-full')
  })

  it('letterboxes a portrait forwarded VK preview and stacks the action', () => {
    let root = mountVideo(
      {
        id: 'VK-PORTRAIT',
        type: 'video',
        status: 'external',
        video_source: 'external',
        mime_type: 'image/jpeg',
        file_name: 'vk-video-1.jpg',
        preview_url: '/api/private-preview',
        open_url: '/api/open-vk',
        width: 1080,
        height: 1920,
      },
      'vk_direct',
      { compactPreview: true },
    )

    let container = root.firstElementChild
    let frame = root.querySelector('[data-video-frame]')
    expect(container.style.width).toBe('320px')
    expect(frame.style.aspectRatio).toBe(`${320 / 280} / 1`)
    expect(frame.tagName).toBe('DIV')
    expect(frame.querySelector('[data-media-backdrop]')).not.toBeNull()
    expect(
      frame.querySelector('img:not([data-media-backdrop])').className,
    ).toContain('object-contain')
    expect(root.textContent).toContain('Available only on VK')
    expect(root.textContent).toContain('Watch on VK Video')
    expect(
      root.querySelector('[data-video-external-action]').getAttribute('href'),
    ).toBe('/api/open-vk')
    expect(root.textContent).not.toContain('vk-video-1.jpg')
  })

  it('uses contain after a compact local preview starts playing', async () => {
    let root = mountVideo(
      {
        id: 'LOCAL-PORTRAIT',
        type: 'video',
        status: 'available',
        video_source: 'local_file',
        mime_type: 'video/mp4',
        playback_url: '/api/video',
        width: 1080,
        height: 1920,
      },
      'telegram_bot',
      { compactPreview: true },
    )

    expect(root.querySelector('[data-video-preview]').className).toContain(
      'object-contain',
    )
    root.querySelector('button').click()
    await Promise.resolve()
    await Promise.resolve()
    expect(root.querySelector('video').className).toContain('object-contain')
  })

  it('uses browser metadata as the local duration fallback', async () => {
    let root = mountVideo(
      {
        id: 'MAX-VIDEO-2',
        type: 'video',
        status: 'available',
        video_source: 'local_file',
        mime_type: 'video/mp4',
        file_name: 'max-video.mp4',
        playback_url: '/api/max-video',
        duration_ms: 4000000,
      },
      'max_direct',
    )

    expect(root.textContent).toContain('66:40')
    root.querySelector('button')?.click()
    await Promise.resolve()
    await Promise.resolve()

    let video = root.querySelector('video')
    Object.defineProperty(video, 'duration', { configurable: true, value: 4 })
    video.dispatchEvent(new Event('loadedmetadata'))
    window.dispatchEvent(
      new CustomEvent('crm-messenger-video-play', { detail: 'another-video' }),
    )
    await Promise.resolve()

    expect(root.textContent).toContain('0:04')
    expect(root.textContent).not.toContain('66:40')
    expect(root.textContent).not.toContain('Open Source')
  })

  it('shows a local first-frame preview before playback', async () => {
    let root = mountVideo(
      {
        id: 'MAX-VIDEO-PREVIEW',
        type: 'video',
        status: 'available',
        video_source: 'local_file',
        mime_type: 'video/mp4',
        file_name: 'max-video.mp4',
        playback_url: '/api/max-video',
        duration_ms: 4000,
      },
      'max_direct',
    )

    let previewFrame = root.querySelector('[data-video-frame]')
    let previewFrameStyle = previewFrame.getAttribute('style')
    let preview = root.querySelector('[data-video-preview]')
    expect(preview).not.toBeNull()
    expect(preview.getAttribute('src')).toBe('/api/max-video#t=0.001')
    expect(preview.getAttribute('preload')).toBe('metadata')
    expect(preview.controls).toBe(false)
    expect(preview.muted).toBe(true)

    Object.defineProperty(preview, 'duration', {
      configurable: true,
      value: 4,
    })
    preview.dispatchEvent(new Event('loadedmetadata'))
    expect(preview.currentTime).toBe(0.1)

    root.querySelector('button')?.click()
    await Promise.resolve()
    await Promise.resolve()

    expect(root.querySelector('[data-video-preview]')).toBeNull()
    expect(root.querySelector('video')?.controls).toBe(true)
    expect(root.querySelector('[data-video-frame]').getAttribute('style')).toBe(
      previewFrameStyle,
    )
  })

  it('keeps the loading state inside the video frame while buffering', async () => {
    let root = mountVideo(
      {
        id: 'MAX-VIDEO-LOADING',
        type: 'video',
        status: 'available',
        video_source: 'local_file',
        mime_type: 'video/mp4',
        playback_url: '/api/max-video',
      },
      'max_direct',
    )

    root.querySelector('button')?.click()
    await Promise.resolve()
    await Promise.resolve()

    let video = root.querySelector('video')
    let loading = root.querySelector('[data-video-loading]')
    expect(loading).not.toBeNull()
    expect(loading.parentElement).toBe(root.querySelector('[data-video-frame]'))
    expect(loading.classList.contains('inset-0')).toBe(true)
    expect(loading.classList.contains('pointer-events-none')).toBe(true)

    video.dispatchEvent(new Event('playing'))
    await Promise.resolve()
    expect(root.querySelector('[data-video-loading]')).toBeNull()

    video.dispatchEvent(new Event('waiting'))
    await Promise.resolve()
    expect(root.querySelector('[data-video-loading]')).not.toBeNull()

    video.dispatchEvent(new Event('canplay'))
    await Promise.resolve()
    expect(root.querySelector('[data-video-loading]')).toBeNull()
  })

  it('does not imitate a VK player for preview-only or embed video', () => {
    let root = mountVideo(
      {
        id: 'VK-EMBED-1',
        type: 'video',
        status: 'external',
        video_source: 'provider_embed',
        mime_type: 'image/jpeg',
        preview_url: '/api/private-preview',
        embed_available: true,
        embed_url: 'https://vk.com/video_ext.php?id=1',
        open_url: 'https://vk.com/video1_1',
      },
      'vk_direct',
    )

    expect(root.querySelector('iframe')).toBeNull()
    expect(root.querySelector('[data-test-play-icon]')).toBeNull()
    expect(root.querySelector('button')).toBeNull()
    expect(root.textContent).toContain('Available only on VK')
    expect(root.textContent).toContain('Watch on VK Video')
  })

  it('shows the VK fallback immediately for a pending external-only video', () => {
    let root = mountVideo(
      {
        id: 'VK-PENDING-EXTERNAL',
        type: 'video',
        status: 'pending',
        video_source: 'provider_embed',
        mime_type: 'image/jpeg',
        file_name: 'vk-video-preview.jpg',
        open_url: '/api/open-vk-pending',
      },
      'vk_direct',
    )

    expect(root.textContent).toContain('Available only on VK')
    expect(root.textContent).toContain('Watch on VK Video')
    expect(
      root.querySelector('[data-video-external-action]').getAttribute('href'),
    ).toBe('/api/open-vk-pending')
    expect(
      root.querySelector('[data-test-attachment-card]').dataset.status,
    ).toBe('external')
    expect(root.querySelector('[data-video-loading]')).toBeNull()
  })

  it('keeps waiting for a pending provider-file video', () => {
    let root = mountVideo(
      {
        id: 'VK-PENDING-FILE',
        type: 'video',
        status: 'pending',
        video_source: 'provider_file',
        file_name: 'vk-video.mp4',
        open_url: '/api/open-vk-file',
      },
      'vk_direct',
    )

    expect(root.textContent).toContain('Pending download')
    expect(root.querySelector('[data-video-external-action]')).toBeNull()
    expect(
      root.querySelector('[data-test-attachment-card]').dataset.status,
    ).toBe('pending')
  })

  it('uses inline playback for VK only when the local file is MP4', () => {
    let root = mountVideo(
      {
        id: 'VK-WEBM-1',
        type: 'video',
        status: 'available',
        video_source: 'local_file',
        mime_type: 'video/webm',
        playback_url: '/api/local-webm',
        preview_url: '/api/private-preview',
        open_url: 'https://vk.com/video1_2',
      },
      'vk_direct',
    )

    expect(root.querySelector('video')).toBeNull()
    expect(root.querySelector('[data-test-play-icon]')).toBeNull()
    expect(root.textContent).toContain('Available only on VK')
  })

  it('captures a safe blurred backdrop from a local portrait video', async () => {
    const drawImage = vi.fn()
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      drawImage,
    })
    vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue(
      'data:image/jpeg;base64,frame',
    )
    let root = mountVideo(
      {
        id: 'LOCAL-PORTRAIT-NO-POSTER',
        type: 'video',
        status: 'available',
        video_source: 'local_file',
        mime_type: 'video/mp4',
        playback_url: '/api/video',
      },
      'telegram_bot',
    )
    let preview = root.querySelector('[data-video-preview]')
    Object.defineProperty(preview, 'videoWidth', {
      configurable: true,
      value: 900,
    })
    Object.defineProperty(preview, 'videoHeight', {
      configurable: true,
      value: 1600,
    })
    Object.defineProperty(preview, 'duration', {
      configurable: true,
      value: 5,
    })

    preview.dispatchEvent(new Event('loadedmetadata'))
    preview.dispatchEvent(new Event('loadeddata'))
    await Promise.resolve()

    expect(drawImage).toHaveBeenCalledOnce()
    expect(root.firstElementChild.style.width).toBe('320px')
    expect(
      root.querySelector('[data-media-backdrop]').getAttribute('src'),
    ).toBe('data:image/jpeg;base64,frame')
  })

  it('uses the unavailable card when no preview or player exists', () => {
    let root = mountVideo({
      id: 'VIDEO-2',
      type: 'video',
      status: 'failed',
      video_source: 'unavailable',
      file_name: 'Недоступное видео',
    })

    expect(root.querySelector('[data-test-attachment-card]')).not.toBeNull()
    expect(root.querySelector('img')).toBeNull()
    expect(root.querySelector('video')).toBeNull()
    expect(root.querySelector('iframe')).toBeNull()
  })
})
