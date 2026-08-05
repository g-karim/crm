/* eslint-disable vue/one-component-per-file */
import { createApp } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/components/LeadMessenger/AttachmentCard.vue', () => ({
  default: {
    props: ['attachment'],
    template: '<div data-test-attachment-card>{{ attachment.file_name }}</div>',
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
})

function mountVideo(attachment, provider = '') {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(VideoAttachment, { attachment, provider })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return root
}

describe('external messenger video', () => {
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

    expect(root.querySelector('img')?.getAttribute('src')).toBe(
      '/api/private-preview',
    )
    expect(root.textContent).toContain('Видео клиента')
    expect(root.textContent).toContain('1:05')
    expect(root.textContent).toContain('Открыть источник')
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

    expect(maxRoot.textContent).not.toContain('Открыть источник')
    expect(maxRoot.querySelector('a')).toBeNull()
    expect(vkRoot.textContent).toContain('Видео доступно только во VK')
    expect(vkRoot.textContent).toContain('Смотреть в VK Видео')
    expect(vkRoot.querySelector('a')?.getAttribute('href')).toBe('/api/open-vk')
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
    expect(root.textContent).not.toContain('Открыть источник')
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
    expect(root.textContent).toContain('Видео доступно только во VK')
    expect(root.textContent).toContain('Смотреть в VK Видео')
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
    expect(root.textContent).toContain('Видео доступно только во VK')
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
