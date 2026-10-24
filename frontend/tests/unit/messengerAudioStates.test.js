import { createApp, h, nextTick, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('frappe-ui', () => ({
  Button: {
    props: ['label', 'disabled'],
    emits: ['click'],
    template:
      '<button :disabled="disabled" @click="$emit(\'click\')">{{ label }}</button>',
  },
}))
vi.mock('@/components/Icons/LoadingIndicator.vue', () => ({
  default: { template: '<span data-loading-indicator />' },
}))

import MessengerAudioPlayer from '@/components/LeadMessenger/MessengerAudioPlayer.vue'
import AttachmentCard from '@/components/LeadMessenger/AttachmentCard.vue'

let mounted = []

beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
  vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => {})
})

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
  vi.useRealTimers()
  vi.restoreAllMocks()
})

function mountAttachment(component, attachment, refresh) {
  let props = reactive({ attachment })
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp({ render: () => h(component, props) })
  app.config.globalProperties.__ = globalThis.__
  if (refresh) app.provide('refreshMessengerAttachments', refresh)
  app.mount(root)
  mounted.push({ app, root })
  return { root, props }
}

function mountAudio(attachment) {
  return mountAttachment(MessengerAudioPlayer, attachment)
}

function voiceAttachment(overrides = {}) {
  return {
    id: 'VOICE-1',
    type: 'audio',
    is_voice: true,
    status: 'available',
    mime_type: 'audio/ogg',
    url: '/api/private-voice',
    download_url: '/api/private-voice?download=1',
    duration_ms: 4250,
    waveform: [0, 20, 40, 80, 255, 80, 40],
    ...overrides,
  }
}

describe('shared messenger audio states', () => {
  it.each(['whatsapp', 'telegram', 'max', 'vk', 'telegram_bot', 'avito'])(
    'uses the common voice metadata and controls for %s',
    (provider) => {
      let { root } = mountAudio(
        voiceAttachment({ provider, url: `/api/private-voice/${provider}` }),
      )
      let slider = root.querySelector('[role="slider"]')

      expect(root.textContent).toContain('Voice message')
      expect(root.textContent).toContain('0:00 / 0:04')
      expect(slider.children).toHaveLength(64)
      expect(slider.getAttribute('aria-valuetext')).toBe('0:00 / 0:04')
      expect(root.querySelector('[aria-label="Play"]')).not.toBeNull()
      expect(root.querySelector('[aria-label="Mute"]')).not.toBeNull()
      expect(root.querySelector('[aria-label="Volume"]')).not.toBeNull()
      expect(root.querySelector('audio').getAttribute('src')).toBe(
        `/api/private-voice/${provider}`,
      )
    },
  )

  it('keeps generic audio and a range fallback when Opus was not identified', () => {
    let { root } = mountAudio(
      voiceAttachment({
        is_voice: false,
        waveform: null,
        file_name: 'interview.mp3',
      }),
    )
    expect(root.textContent).toContain('interview.mp3')
    expect(root.textContent).not.toContain('Voice message')
    expect(root.querySelector('[role="slider"]')).toBeNull()
    expect(
      root.querySelector('input[aria-label="Playback Position"]'),
    ).not.toBeNull()
  })

  it('replaces a stuck browser spinner with a safe retry and download action', async () => {
    vi.useFakeTimers()
    let { root } = mountAudio(voiceAttachment())
    let audio = root.querySelector('audio')
    audio.dispatchEvent(new Event('loadstart'))
    await nextTick()
    expect(root.querySelector('[data-loading-indicator]')).not.toBeNull()

    await vi.advanceTimersByTimeAsync(20000)
    expect(root.querySelector('[data-loading-indicator]')).toBeNull()
    expect(root.textContent).toContain('Could not play the audio')
    expect(root.querySelector('[aria-label="Play"]').disabled).toBe(true)
    expect(root.querySelector('a').getAttribute('href')).toBe(
      '/api/private-voice?download=1',
    )

    let retry = [...root.querySelectorAll('button')].find(
      (button) => button.textContent === 'Try Again',
    )
    retry.click()
    await nextTick()
    expect(audio.load).toHaveBeenCalledOnce()
    expect(root.textContent).not.toContain('Could not play the audio')
    audio.dispatchEvent(new Event('canplay'))
    await nextTick()
    expect(root.querySelector('[data-loading-indicator]')).toBeNull()
    expect(root.querySelector('[aria-label="Play"]').disabled).toBe(false)
    await vi.advanceTimersByTimeAsync(20000)
    expect(root.textContent).not.toContain('Could not play the audio')
  })

  it('hides native error details and allows retry after codec/network failure', async () => {
    let { root } = mountAudio(voiceAttachment())
    let audio = root.querySelector('audio')
    Object.defineProperty(audio, 'error', {
      configurable: true,
      value: { message: 'secret provider URL and token', code: 4 },
    })
    audio.dispatchEvent(new Event('error'))
    await nextTick()
    expect(root.textContent).toContain('Could not play the audio')
    expect(root.textContent).not.toContain('secret')
    expect(root.textContent).toContain('Try Again')
  })

  it('keeps the first loading deadline during repeated waiting events', async () => {
    vi.useFakeTimers()
    let { root } = mountAudio(voiceAttachment())
    let audio = root.querySelector('audio')
    audio.dispatchEvent(new Event('waiting'))
    await vi.advanceTimersByTimeAsync(15000)
    audio.dispatchEvent(new Event('waiting'))
    await vi.advanceTimersByTimeAsync(5000)
    expect(root.textContent).toContain('Could not play the audio')
    expect(root.querySelector('[data-loading-indicator]')).toBeNull()
  })

  it('clears buffering when playback is paused', async () => {
    vi.useFakeTimers()
    let { root } = mountAudio(voiceAttachment())
    let audio = root.querySelector('audio')
    audio.dispatchEvent(new Event('waiting'))
    audio.dispatchEvent(new Event('pause'))
    await vi.advanceTimersByTimeAsync(20000)
    expect(root.querySelector('[data-loading-indicator]')).toBeNull()
    expect(root.textContent).not.toContain('Could not play the audio')
  })

  it('applies available delta metadata and resets stale playback on a new source', async () => {
    let { root, props } = mountAudio(
      voiceAttachment({ status: 'pending', url: null, waveform: null }),
    )
    expect(root.querySelector('audio')).toBeNull()

    props.attachment = voiceAttachment()
    await nextTick()
    let audio = root.querySelector('audio')
    Object.defineProperty(audio, 'duration', { configurable: true, value: 50 })
    audio.dispatchEvent(new Event('loadedmetadata'))
    audio.currentTime = 20
    audio.dispatchEvent(new Event('timeupdate'))
    audio.dispatchEvent(new Event('error'))
    await nextTick()
    expect(root.textContent).toContain('0:20 / 0:50')

    props.attachment = voiceAttachment({
      url: '/api/reloaded-voice',
      duration_ms: 8500,
    })
    await nextTick()
    expect(root.textContent).not.toContain('Could not play the audio')
    expect(root.textContent).toContain('0:00 / 0:08')
    expect(root.querySelector('audio').getAttribute('src')).toBe(
      '/api/reloaded-voice',
    )
  })

  it('uses provider duration when a browser reports unbounded Opus duration', async () => {
    let { root } = mountAudio(voiceAttachment())
    Object.defineProperty(root.querySelector('audio'), 'duration', {
      configurable: true,
      value: Infinity,
    })
    root.querySelector('audio').dispatchEvent(new Event('durationchange'))
    await nextTick()
    expect(root.textContent).toContain('0:00 / 0:04')
    expect(root.textContent).not.toContain('Infinity')
  })

  it.each(['failed', 'unsupported'])(
    'does not start browser playback or invent a provider retry for %s downloads',
    (status) => {
      let { root } = mountAudio(voiceAttachment({ status, url: null }))
      expect(root.querySelector('audio')).toBeNull()
      expect(root.querySelector('[data-loading-indicator]')).toBeNull()
      expect(root.textContent).not.toContain('Try Again')
      expect(root.querySelector('a')).toBeNull()
    },
  )

  it('shows a safe fallback for available audio without a playable URL', () => {
    let { root } = mountAudio(voiceAttachment({ url: null }))
    expect(root.querySelector('audio')).toBeNull()
    expect(root.textContent).toContain('Attachment unavailable')
  })
})

describe('shared attachment card states', () => {
  it('fills the document bubble while retaining an accessible full filename', () => {
    let { root } = mountAttachment(AttachmentCard, {
      type: 'file',
      status: 'available',
      file_name: 'contract.pdf',
      url: '/private/document',
    })
    let card = root.querySelector('[data-attachment-card]')
    expect(card.tagName).toBe('A')
    expect(card.classList.contains('w-full')).toBe(true)
    expect(card.classList.contains('w-fit')).toBe(false)
    expect(root.querySelector('[data-attachment-card-title]').title).toBe(
      'contract.pdf',
    )
  })

  it('refreshes a pending snapshot without starting a provider download and stops long spinners', async () => {
    vi.useFakeTimers()
    let resolveRefresh
    let refresh = vi.fn(
      () => new Promise((resolve) => (resolveRefresh = resolve)),
    )
    let { root, props } = mountAttachment(
      AttachmentCard,
      {
        id: 'DOC',
        type: 'file',
        status: 'pending',
        file_name: 'contract.pdf',
      },
      refresh,
    )
    let button = root.querySelector('button')
    expect(root.querySelector('[data-loading-indicator]')).not.toBeNull()
    button.click()
    button.click()
    await nextTick()
    expect(refresh).toHaveBeenCalledOnce()
    expect(button.disabled).toBe(true)
    expect(root.querySelector('a')).toBeNull()
    resolveRefresh()
    await Promise.resolve()
    await nextTick()
    expect(button.disabled).toBe(false)
    await vi.advanceTimersByTimeAsync(30000)
    expect(root.querySelector('[data-loading-indicator]')).toBeNull()
    expect(root.textContent).toContain('Pending download')
    expect(root.textContent).toContain('Refresh')

    props.attachment = {
      ...props.attachment,
      status: 'available',
      url: '/private/document',
    }
    await nextTick()
    expect(root.querySelector('button')).toBeNull()
    expect(root.querySelector('a').getAttribute('href')).toBe(
      '/private/document',
    )
  })

  it('shows a fixed safe refresh error and keeps failed downloads terminal', async () => {
    let refresh = vi.fn(async () => {
      throw new Error('secret provider token')
    })
    let { root } = mountAttachment(
      AttachmentCard,
      {
        type: 'file',
        status: 'failed',
        error: 'secret remote exception',
        file_name: 'contract.pdf',
      },
      refresh,
    )
    root.querySelector('button').click()
    await nextTick()
    await nextTick()
    expect(root.textContent).toContain('Could not refresh messages.')
    expect(root.textContent).not.toContain('secret')
    expect(root.querySelector('[data-loading-indicator]')).toBeNull()
    expect(root.querySelector('a')).toBeNull()
    expect(root.querySelector('button').disabled).toBe(false)
  })

  it('does not expose raw status/error values or a fake retry for unsupported media', () => {
    let refresh = vi.fn()
    let { root } = mountAttachment(
      AttachmentCard,
      {
        type: 'unsupported',
        status: 'secret_status',
        error: 'secret exception',
      },
      refresh,
    )
    expect(root.textContent).not.toContain('secret')
    expect(root.textContent).toContain('Unsupported')
    expect(root.querySelector('button')).toBeNull()
    expect(refresh).not.toHaveBeenCalled()
  })
})
