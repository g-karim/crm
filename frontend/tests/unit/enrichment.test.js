import { createApp, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import EnrichFromWebsite from '@/components/EnrichFromWebsite.vue'

const mocks = vi.hoisted(() => ({
  enabled: true,
  pending: {},
  call: vi.fn(),
  listeners: new Map(),
  reload: vi.fn(),
  toast: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
}))

vi.mock('frappe-ui', () => ({
  Button: {
    props: ['label', 'loading', 'loadingText'],
    template:
      '<button :disabled="loading">{{ loading ? loadingText : label }}</button>',
  },
  call: mocks.call,
  toast: mocks.toast,
}))
vi.mock('frappe-ui/frappe', () => ({
  useTelemetry: () => ({ capture: vi.fn() }),
}))
vi.mock('@/stores/enrichment', async () => {
  const { reactive } = await import('vue')
  mocks.pending = reactive({})
  return {
    enrichmentStore: () => ({
      isEnabled: () => mocks.enabled,
      pending: mocks.pending,
    }),
  }
})
vi.mock('@/stores/organizations', () => ({
  organizationsStore: () => ({ organizations: { reload: mocks.reload } }),
}))
vi.mock('@/stores/global', () => ({
  globalStore: () => ({
    $socket: {
      on: (name, callback) => mocks.listeners.set(name, callback),
      off: (name) => mocks.listeners.delete(name),
    },
  }),
}))

let mounted
const reference = {
  doctype: 'CRM Lead',
  docname: 'L1',
  website: 'https://example.com',
}

function mount(props = reference) {
  const root = document.createElement('div')
  document.body.appendChild(root)
  const done = vi.fn()
  const app = createApp(EnrichFromWebsite, { ...props, onDone: done })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted = { app, root, done }
  return mounted
}

async function flush() {
  await Promise.resolve()
  await nextTick()
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.clearAllMocks()
  mocks.enabled = true
  for (const key of Object.keys(mocks.pending)) delete mocks.pending[key]
  mocks.listeners.clear()
  mocks.call.mockResolvedValue({ queued_at: '2026-10-07 12:00:00' })
})

afterEach(() => {
  mounted?.app.unmount()
  mounted?.root.remove()
  mounted = null
  vi.useRealTimers()
})

describe('website enrichment', () => {
  it('hides the action when enrichment is disabled for this record type', () => {
    mocks.enabled = false
    expect(mount().root.querySelector('button')).toBeNull()
  })

  it('explains a missing website without enqueueing a job', async () => {
    const { root } = mount({ ...reference, website: '' })
    root.querySelector('button').click()
    await flush()
    expect(mocks.call).not.toHaveBeenCalled()
    expect(mocks.toast.warning).toHaveBeenCalledWith(
      'Set a Website on this record before enriching.',
    )
  })

  it('reloads the record and organizations after a realtime completion', async () => {
    const { root, done } = mount()
    root.querySelector('button').click()
    await flush()
    mocks.listeners.get('domain_enrichment_progress')({
      reference_doctype: 'CRM Lead',
      reference_name: 'L1',
      status: 'completed',
      payload: { filled_fields: ['Email'] },
    })
    await flush()
    expect(done).toHaveBeenCalledOnce()
    expect(mocks.reload).toHaveBeenCalledOnce()
    expect(mocks.toast.success).toHaveBeenCalledWith('Enriched. Filled: Email')
    expect(root.querySelector('button').disabled).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('recovers completion when the realtime event was missed', async () => {
    const { root, done } = mount()
    mocks.call
      .mockResolvedValueOnce({ queued_at: '2026-10-07 12:00:00' })
      .mockResolvedValueOnce({
        status: 'completed',
        payload: { filled_fields: ['Email'] },
      })
    root.querySelector('button').click()
    await flush()
    await vi.advanceTimersByTimeAsync(3000)
    expect(mocks.call).toHaveBeenLastCalledWith(
      'crm.domain_enrichment.api.get_progress',
      {
        reference_doctype: 'CRM Lead',
        reference_name: 'L1',
        queued_at: '2026-10-07 12:00:00',
      },
    )
    expect(done).toHaveBeenCalledOnce()
    expect(root.querySelector('button').disabled).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('stops the spinner after a failed background run', async () => {
    const { root, done } = mount()
    root.querySelector('button').click()
    await flush()
    mocks.listeners.get('domain_enrichment_progress')({
      reference_doctype: 'CRM Lead',
      reference_name: 'L1',
      status: 'error',
      message: 'Site unavailable',
    })
    await flush()
    expect(mocks.toast.error).toHaveBeenCalledWith('Site unavailable')
    expect(done).not.toHaveBeenCalled()
    expect(root.querySelector('button').disabled).toBe(false)
  })

  it('removes listeners and polling when leaving the record', async () => {
    const { root, app } = mount()
    root.querySelector('button').click()
    await flush()
    app.unmount()
    mounted = null
    root.remove()
    await vi.advanceTimersByTimeAsync(9000)
    expect(mocks.call).toHaveBeenCalledTimes(1)
    expect(mocks.listeners.size).toBe(0)
  })

  it('resumes a queued run after changing tabs remounts the record', async () => {
    const first = mount()
    first.root.querySelector('button').click()
    await flush()
    first.app.unmount()
    first.root.remove()
    const second = mount()
    expect(second.root.querySelector('button').disabled).toBe(true)
    mocks.call.mockResolvedValueOnce({
      status: 'completed',
      payload: { filled_fields: ['Description'] },
    })
    await vi.advanceTimersByTimeAsync(3000)
    expect(second.done).toHaveBeenCalledOnce()
    expect(second.root.querySelector('button').disabled).toBe(false)
  })

  it('keeps tracking a run if the enqueue response arrives after remounting', async () => {
    let resolveEnqueue
    mocks.call.mockReturnValueOnce(
      new Promise((resolve) => (resolveEnqueue = resolve)),
    )
    const first = mount()
    first.root.querySelector('button').click()
    first.app.unmount()
    first.root.remove()
    const second = mount()
    resolveEnqueue({ queued_at: '2026-10-07 12:00:00' })
    await flush()
    mocks.call.mockResolvedValueOnce({
      status: 'completed',
      payload: { filled_fields: ['Description'] },
    })
    await vi.advanceTimersByTimeAsync(3000)
    expect(second.done).toHaveBeenCalledOnce()
    expect(mocks.call).toHaveBeenCalledTimes(2)
    expect(second.root.querySelector('button').disabled).toBe(false)
  })
})
