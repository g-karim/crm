import { createApp, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  call: vi.fn(),
  toast: { error: vi.fn(), success: vi.fn() },
}))

const components = vi.hoisted(() => ({
  button: {
    props: ['label', 'loading'],
    emits: ['click'],
    template:
      '<button :disabled="loading" @click="$emit(\'click\')">{{ label }}</button>',
  },
}))

vi.mock('frappe-ui', () => ({
  Badge: { props: ['label'], template: '<span>{{ label }}</span>' },
  Button: components.button,
  Dialog: {
    template: '<div><slot name="body-content" /><slot name="actions" /></div>',
  },
  ErrorMessage: { props: ['message'], template: '<div>{{ message }}</div>' },
  FeatherIcon: { template: '<span />' },
  FormControl: { template: '<input />' },
  LoadingIndicator: { template: '<span>Loading</span>' },
  Switch: { template: '<input type="checkbox" />' },
  call: mocks.call,
  toast: mocks.toast,
}))

vi.mock('@/components/Layouts/SettingsLayoutBase.vue', () => ({
  default: {
    template:
      '<div><slot name="header-actions" /><slot name="content" /></div>',
  },
}))

import MessengerSettings from '@/components/Settings/MessengerSettings.vue'

let mounted = []

afterEach(() => {
  for (let { app, root } of mounted) {
    app.unmount()
    root.remove()
  }
  mounted = []
  mocks.call.mockReset()
  mocks.toast.error.mockReset()
  mocks.toast.success.mockReset()
})

async function mountSettings() {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(MessengerSettings)
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  await nextTick()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await nextTick()
  return root
}

describe('MessengerSettings page loading', () => {
  it('shows the empty state only after a successful empty response', async () => {
    mocks.call.mockResolvedValue({ settings: {}, channels: [] })

    let root = await mountSettings()

    expect(root.textContent).toContain('No channels yet')
    expect(root.textContent).not.toContain(
      'Could not load message channel settings.',
    )
  })

  it('shows a load error instead of the empty state when settings fail to load', async () => {
    mocks.call.mockRejectedValue(new Error('request failed'))

    let root = await mountSettings()

    expect(root.textContent).toContain(
      'Could not load message channel settings.',
    )
    expect(root.textContent).not.toContain('No channels yet')
  })
})
