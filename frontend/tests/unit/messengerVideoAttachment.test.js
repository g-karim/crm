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

function mountVideo(attachment) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(VideoAttachment, { attachment })
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
