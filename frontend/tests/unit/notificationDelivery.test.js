import { createApp, h } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

const request = vi.hoisted(() => vi.fn())
vi.mock('frappe-ui', () => ({ frappeRequest: request }))
vi.mock('@/stores/global', () => ({
  globalStore: () => ({ $socket: { on: vi.fn(), off: vi.fn() } }),
}))
import { useNotificationDelivery } from '@/composables/useNotificationDelivery'

let app, host, control
function settings(revision = 0, viewer = 'demo@example.invalid') {
  return {
    viewer,
    one_available: true,
    senders: [{ id: 'sender', label: 'Sender' }],
    sources: [
      { id: 'crm', enabled: false, revision, sender: null, push_route: 'None' },
    ],
  }
}
async function mount() {
  request.mockResolvedValue(settings())
  host = document.createElement('div')
  app = createApp({
    setup() {
      control = useNotificationDelivery()
      return () => h('div')
    },
  })
  app.mount(host)
  await Promise.resolve()
  await Promise.resolve()
}
afterEach(() => {
  app?.unmount()
  host?.remove()
  vi.clearAllMocks()
})

describe('shared CRM delivery settings', () => {
  it('replays the exact mutation after losing the response', async () => {
    await mount()
    request.mockRejectedValueOnce(new TypeError('Network response lost'))
    const draft = { enabled: true, sender: 'sender', push: false, revision: 0 }
    expect(await control.save(draft)).toBe(false)
    const first = request.mock.calls.at(-1)[0].params
    request.mockResolvedValueOnce(settings(1))
    expect(
      await control.save({ ...draft, sender: 'changed-after-timeout' }),
    ).toBe(true)
    expect(request.mock.calls.at(-1)[0].params).toEqual(first)
    expect(control.pending.value).toBeNull()
  })

  it('shows a server conflict without inventing a newer revision', async () => {
    await mount()
    request.mockRejectedValueOnce({
      exc_type: 'TimestampMismatchError',
      messages: ['Reload before saving.'],
    })
    await control.save({
      enabled: true,
      sender: 'sender',
      push: false,
      revision: 0,
    })
    expect(control.error.value).toBe('Reload before saving.')
    expect(control.source.value.revision).toBe(0)
    expect(control.pending.value).toBeNull()
  })

  it('clears the previous account instead of displaying another account state', async () => {
    await mount()
    request.mockResolvedValueOnce(settings(0, 'another@example.invalid'))
    await control.reload()
    expect(control.state.value).toBeNull()
    expect(control.pending.value).toBeNull()
  })
})
