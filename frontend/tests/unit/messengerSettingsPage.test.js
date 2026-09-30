import { createApp, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  call: vi.fn(),
  toast: { error: vi.fn(), success: vi.fn() },
}))

const components = vi.hoisted(() => ({
  button: {
    props: ['label', 'loading', 'disabled'],
    emits: ['click'],
    template:
      '<button :disabled="loading || disabled" @click="$emit(\'click\')">{{ label }}</button>',
  },
}))

vi.mock('frappe-ui', () => ({
  Badge: { props: ['label'], template: '<span>{{ label }}</span>' },
  Button: components.button,
  Dialog: {
    template: '<div><slot name="body-content" /><slot name="actions" /></div>',
  },
  FeatherIcon: { template: '<span />' },
  FormControl: {
    props: ['label', 'modelValue', 'type'],
    emits: ['update:modelValue'],
    template:
      '<input :data-label="label" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
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

async function clickButton(root, label) {
  const buttons = [...root.querySelectorAll('button')]
  const button =
    buttons.find((button) => button.textContent.trim() === label) ||
    buttons.find((button) => button.textContent.includes(label))
  expect(button).toBeTruthy()
  button.click()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await nextTick()
}

async function editField(root, label, value) {
  const input = root.querySelector(`input[data-label="${label}"]`)
  input.value = value
  input.dispatchEvent(new Event('input', { bubbles: true }))
  await nextTick()
}

describe('MessengerSettings unsaved channel changes', () => {
  function avitoChannel() {
    return {
      name: 'avito-1',
      provider: 'avito_direct',
      platform: 'avito',
      auth_type: 'client_credentials',
      custom_display_name: 'Avito Sales',
      client_id: 'saved-id',
      client_secret_configured: true,
      enabled: 1,
      state: 'disconnected',
    }
  }

  it.each(['Test', 'Connect / Repair', 'Refresh Status', 'Disconnect'])(
    '%s keeps unsaved credentials and asks to save without calling the provider',
    async (action) => {
      mocks.call.mockResolvedValue({ settings: {}, channels: [avitoChannel()] })
      const root = await mountSettings()
      await clickButton(root, 'Avito Sales')
      await editField(root, 'Client ID', 'new-id')
      await editField(root, 'Client Secret', 'new-secret')
      await clickButton(root, action)

      expect(mocks.call).toHaveBeenCalledTimes(1)
      expect(root.querySelector('input[data-label="Client ID"]').value).toBe(
        'new-id',
      )
      expect(
        root.querySelector('input[data-label="Client Secret"]').value,
      ).toBe('new-secret')
      expect(
        root.querySelector('[data-testid="channel-auth-error"]').textContent,
      ).toContain('Save channel changes before running connection actions.')
      expect(mocks.toast.success).not.toHaveBeenCalled()
    },
  )

  it('shows one editable Avito end date and saves a changed date', async () => {
    let channel = {
      ...avitoChannel(),
      avito_import_mode: 'period',
      avito_import_from_date: '2026-09-01',
      avito_import_started_at: '2026-09-04 12:00:00',
    }
    mocks.call.mockImplementation((method, params) => {
      if (method === 'crm_messenger.api.settings.get_settings') {
        return Promise.resolve({ settings: {}, channels: [channel] })
      }
      if (method === 'crm_messenger.api.settings.save_channel') {
        expect(params.avito_import_to_date).toBe('2026-09-10')
        channel = {
          ...channel,
          avito_import_to_date: params.avito_import_to_date,
        }
        return Promise.resolve(channel)
      }
      throw new Error(`Unexpected method ${method}`)
    })
    const root = await mountSettings()
    await clickButton(root, 'Avito Sales')
    expect(root.querySelector('input[data-label="Through"]')).toBeNull()
    expect(
      root.querySelectorAll('input[data-label="Through date"]'),
    ).toHaveLength(1)
    expect(root.querySelector('input[data-label="Through date"]').value).toBe(
      '2026-09-04',
    )
    await editField(root, 'Through date', '2026-09-10')
    await clickButton(root, 'Save')
    expect(mocks.call).toHaveBeenCalledWith(
      'crm_messenger.api.settings.save_channel',
      expect.objectContaining({ avito_import_to_date: '2026-09-10' }),
    )
  })

  it('allows testing after the edited credentials have been saved', async () => {
    let channel = avitoChannel()
    mocks.call.mockImplementation((method, params) => {
      if (method === 'crm_messenger.api.settings.get_settings') {
        return Promise.resolve({ settings: {}, channels: [channel] })
      }
      if (method === 'crm_messenger.api.settings.save_channel') {
        expect(params.client_secret).toBe('new-secret')
        channel = {
          ...channel,
          client_id: params.client_id,
          state: 'unchecked',
        }
        return Promise.resolve(channel)
      }
      if (method === 'crm_messenger.api.channels.test_provider_connection') {
        expect(channel.client_id).toBe('new-id')
        return Promise.resolve({ ok: true })
      }
      throw new Error(`Unexpected method ${method}`)
    })
    const root = await mountSettings()
    await clickButton(root, 'Avito Sales')
    await editField(root, 'Client ID', 'new-id')
    await editField(root, 'Client Secret', 'new-secret')
    await clickButton(root, 'Save')
    await clickButton(root, 'Test')

    expect(mocks.call).toHaveBeenCalledWith(
      'crm_messenger.api.channels.test_provider_connection',
      { channel: 'avito-1' },
    )
    expect(root.querySelector('input[data-label="Client ID"]').value).toBe(
      'new-id',
    )
    expect(root.querySelector('input[data-label="Client Secret"]').value).toBe(
      '',
    )
    expect(root.querySelector('[data-testid="channel-auth-error"]')).toBeNull()
  })

  it('preserves the draft when saving replacement credentials fails', async () => {
    mocks.call.mockImplementation((method) => {
      if (method === 'crm_messenger.api.settings.get_settings') {
        return Promise.resolve({ settings: {}, channels: [avitoChannel()] })
      }
      return Promise.reject({
        messages: ['Avito token belongs to another account.'],
      })
    })
    const root = await mountSettings()
    await clickButton(root, 'Avito Sales')
    await editField(root, 'Client Secret', 'rejected-secret')
    await clickButton(root, 'Save')
    await clickButton(root, 'Test')

    expect(mocks.call).toHaveBeenCalledTimes(2)
    expect(root.querySelector('input[data-label="Client Secret"]').value).toBe(
      'rejected-secret',
    )
    expect(mocks.toast.success).not.toHaveBeenCalled()
  })

  it('keeps edits made during a request and prevents overlapping connection actions', async () => {
    let resolveTest
    mocks.call.mockImplementation((method) => {
      if (method === 'crm_messenger.api.settings.get_settings') {
        return Promise.resolve({ settings: {}, channels: [avitoChannel()] })
      }
      return new Promise((resolve) => {
        resolveTest = resolve
      })
    })
    const root = await mountSettings()
    await clickButton(root, 'Avito Sales')
    await clickButton(root, 'Test')
    await editField(root, 'Client Secret', 'typed-during-request')
    await clickButton(root, 'Connect / Repair')
    await clickButton(root, 'Save')
    expect(mocks.call).toHaveBeenCalledTimes(2)
    resolveTest({ ok: true })
    await new Promise((resolve) => setTimeout(resolve, 0))
    await nextTick()

    expect(root.querySelector('input[data-label="Client Secret"]').value).toBe(
      'typed-during-request',
    )
    await clickButton(root, 'Test')
    expect(mocks.call).toHaveBeenCalledTimes(3)
    expect(
      root.querySelector('[data-testid="channel-auth-error"]').textContent,
    ).toContain('Save channel changes before running connection actions.')
  })

  it('does not reopen a channel closed during a request', async () => {
    let resolveTest
    mocks.call.mockImplementation((method) => {
      if (method === 'crm_messenger.api.settings.get_settings') {
        return Promise.resolve({ settings: {}, channels: [avitoChannel()] })
      }
      return new Promise((resolve) => {
        resolveTest = resolve
      })
    })
    const root = await mountSettings()
    await clickButton(root, 'Avito Sales')
    await clickButton(root, 'Test')
    await clickButton(root, 'Close')
    resolveTest({ ok: true })
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(mounted[0].app._instance.setupState.showChannelDialog).toBe(false)
  })
})

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

  it.each([
    ['', false],
    ['http://crm.example.com', false],
    ['https://localhost:8000', false],
    ['https://127.0.0.1', false],
    ['https://0.0.0.0', false],
    ['https://[::1]', false],
    ['https://crm.local', false],
    ['https://example.ngrok.app', true],
  ])(
    'shows the webhook warning only when effective URL %s is unsuitable',
    async (webhookBaseUrl, isPublicHttps) => {
      let channel = {
        name: 'avito-1',
        provider: 'avito_direct',
        platform: 'avito',
        auth_type: 'client_credentials',
        custom_display_name: 'Avito Sales',
        state: 'unchecked',
      }
      mocks.call.mockResolvedValue({
        settings: {
          webhook_base_url: webhookBaseUrl,
          webhook_base_url_is_public_https: isPublicHttps,
        },
        channels: [channel],
      })

      let root = await mountSettings()
      let channelButton = [...root.querySelectorAll('button')].find((button) =>
        button.textContent.includes('Avito Sales'),
      )
      channelButton.click()
      await nextTick()

      let warning = root.querySelector('[data-testid="webhook-url-warning"]')
      expect(Boolean(warning)).toBe(!isPublicHttps)
      if (warning) {
        expect(warning.className).toContain('text-ink-blue-9')
        expect(warning.className).toContain('bg-surface-blue-2')
      }
    },
  )

  it('uses the common connect action for Avito client credentials', async () => {
    let channel = {
      name: 'avito-1',
      provider: 'avito_direct',
      platform: 'avito',
      auth_type: 'client_credentials',
      custom_display_name: 'Avito Sales',
      client_id: 'client-id',
      client_secret_configured: true,
      enabled: 0,
      state: 'unchecked',
    }
    mocks.call.mockImplementation((method) => {
      if (method === 'crm_messenger.api.settings.get_settings') {
        return Promise.resolve({ settings: {}, channels: [channel] })
      }
      if (method === 'crm_messenger.api.channels.register_provider_webhook') {
        return Promise.resolve({ ok: true, message: 'connected' })
      }
      return Promise.reject(new Error(`unexpected method: ${method}`))
    })
    let root = await mountSettings()
    let channelButton = [...root.querySelectorAll('button')].find((button) =>
      button.textContent.includes('Avito Sales'),
    )

    channelButton.click()
    await nextTick()
    let connectButton = [...root.querySelectorAll('button')].find(
      (button) => button.textContent === 'Connect / Repair',
    )
    connectButton.click()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(mocks.call).toHaveBeenCalledWith(
      'crm_messenger.api.channels.register_provider_webhook',
      { channel: 'avito-1' },
    )
    expect(root.textContent).not.toContain('Register Webhook')
    expect(root.textContent).not.toContain('Avito Account ID')
    expect(root.textContent).not.toContain('Avito Connection Method')
    expect(root.textContent).not.toContain('OAuth')
    expect(root.querySelector('input[data-label="API Token"]')).toBeNull()
  })

  it('translates the specific Avito Messenger subscription error after Test', async () => {
    const source =
      'This account does not have access to the Avito Messenger API. Switch to a subscription that includes the Messenger API, then try again.'
    const localized = 'localized Avito subscription message'
    const originalTranslate = globalThis.__
    globalThis.__ = vi.fn((message, args) =>
      message === source ? localized : originalTranslate(message, args),
    )
    let channel = {
      name: 'avito-1',
      provider: 'avito_direct',
      platform: 'avito',
      auth_type: 'client_credentials',
      custom_display_name: 'Avito Sales',
      client_id: 'client-id',
      client_secret_configured: true,
      auth_error: 'Avito account id is not configured.',
      enabled: 0,
      state: 'unchecked',
    }
    mocks.call.mockImplementation((method) => {
      if (method === 'crm_messenger.api.settings.get_settings') {
        return Promise.resolve({ settings: {}, channels: [channel] })
      }
      if (method === 'crm_messenger.api.channels.test_provider_connection') {
        return Promise.resolve({
          ok: false,
          reason: 'messenger_subscription_required',
          message: 'generic provider failure',
        })
      }
      return Promise.reject(new Error(`unexpected method: ${method}`))
    })
    try {
      let root = await mountSettings()
      let channelButton = [...root.querySelectorAll('button')].find((button) =>
        button.textContent.includes('Avito Sales'),
      )

      channelButton.click()
      await nextTick()
      let testButton = [...root.querySelectorAll('button')].find(
        (button) => button.textContent === 'Test',
      )
      testButton.click()
      await new Promise((resolve) => setTimeout(resolve, 0))

      expect(root.textContent).toContain(localized)
      expect(globalThis.__).toHaveBeenCalledWith(source)
      expect(root.textContent).not.toContain('generic provider failure')
      expect(root.textContent).not.toContain(
        'Avito account id is not configured.',
      )
      expect(
        root.querySelectorAll('[data-testid="channel-auth-error"]'),
      ).toHaveLength(1)
    } finally {
      globalThis.__ = originalTranslate
    }
  })

  it('renders stored channel errors with high contrast', async () => {
    let channel = {
      name: 'avito-1',
      provider: 'avito_direct',
      platform: 'avito',
      auth_type: 'client_credentials',
      custom_display_name: 'Avito Sales',
      auth_error: 'Avito account id is not configured.',
      state: 'error',
    }
    mocks.call.mockResolvedValue({ settings: {}, channels: [channel] })

    let root = await mountSettings()
    let channelButton = [...root.querySelectorAll('button')].find((button) =>
      button.textContent.includes('Avito Sales'),
    )
    channelButton.click()
    await nextTick()

    let errorAlert = root.querySelector('[data-testid="channel-auth-error"]')
    expect(errorAlert.textContent).toContain(
      'Avito account id is not configured.',
    )
    expect(errorAlert.className).toContain('text-ink-red-8')
    expect(errorAlert.className).toContain('bg-surface-red-2')
  })
})
