import { createApp, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const loadAnimation = vi.fn()
const destroy = vi.fn()

vi.mock('lottie-web/build/player/lottie_light', () => ({
  default: { loadAnimation },
}))

import VkLottieSticker from '@/components/LeadMessenger/VkLottieSticker.vue'

let mounted = []

function animationData(overrides = {}) {
  return {
    v: '5.12.0',
    fr: 30,
    ip: 0,
    op: 60,
    w: 512,
    h: 512,
    layers: [],
    assets: [],
    ...overrides,
  }
}

function mountSticker(overrides = {}) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(VkLottieSticker, {
    attachment: {
      id: 'VK-STICKER-1',
      file_name: 'sticker.json',
      url: '/api/sticker',
      preview_url: '/api/sticker-preview',
      ...overrides,
    },
  })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return root
}

async function settle() {
  await Promise.resolve()
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
}

beforeEach(() => {
  loadAnimation.mockReset()
  destroy.mockReset()
  loadAnimation.mockImplementation(() => ({
    destroy,
    addEventListener(event, callback) {
      if (event === 'DOMLoaded') queueMicrotask(callback)
    },
  }))
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(animationData()),
    }),
  )
  vi.stubGlobal('matchMedia',
    vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  )
})

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
  vi.unstubAllGlobals()
})

describe('VK Lottie sticker', () => {
  it('loads same-origin JSON with the light renderer and hides the preview', async () => {
    let root = mountSticker()
    await settle()

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/sticker'),
      expect.objectContaining({ credentials: 'same-origin', redirect: 'error' }),
    )
    await vi.waitFor(() =>
      expect(loadAnimation).toHaveBeenCalledWith(
        expect.objectContaining({
          renderer: 'svg',
          loop: true,
          autoplay: true,
          rendererSettings: expect.objectContaining({ runExpressions: false }),
        }),
      ),
    )
    await settle()
    expect(root.querySelector('img')).toBeNull()
  })

  it('uses the static preview when reduced motion is enabled', async () => {
    matchMedia.mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })
    let root = mountSticker()
    await settle()

    expect(fetch).not.toHaveBeenCalled()
    expect(loadAnimation).not.toHaveBeenCalled()
    expect(root.querySelector('img')?.getAttribute('src')).toBe(
      '/api/sticker-preview',
    )
    expect(root.firstElementChild.getAttribute('aria-label')).toBe('Стикер')
    expect(root.querySelector('img')?.getAttribute('alt')).toBe('Стикер')
    expect(root.textContent).not.toContain('sticker.json')
  })

  it('rejects animations with external assets and keeps the preview', async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(
        animationData({ assets: [{ id: 'image_0', u: 'https://evil.test/' }] }),
      ),
    })
    let root = mountSticker()
    await settle()

    expect(loadAnimation).not.toHaveBeenCalled()
    expect(root.querySelector('img')?.getAttribute('src')).toBe(
      '/api/sticker-preview',
    )
  })
})
