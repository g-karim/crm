import { createApp, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  call: vi.fn(),
  safeCall: vi.fn(),
  toast: { error: vi.fn(), success: vi.fn() },
  deferPartnerConnection: false,
  finishPartnerConnection: null,
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
    props: ['open', 'options', 'dismissible', 'showCloseButton'],
    template:
      '<div v-if="open" data-dialog :data-title="options?.title" :data-dismissible="dismissible" :data-close-button="showCloseButton"><slot name="body-content" /><slot name="actions" /></div>',
  },
  FeatherIcon: { template: '<span />' },
  FormControl: {
    props: [
      'label',
      'modelValue',
      'type',
      'options',
      'disabled',
      'description',
    ],
    emits: ['update:modelValue'],
    template: `<label>{{ label }}<select v-if="type === 'select'" :data-label="label" :value="modelValue" :disabled="disabled" @change="$emit('update:modelValue', $event.target.value)"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select><input v-else :data-label="label" :value="modelValue" :disabled="disabled" @input="$emit('update:modelValue', $event.target.value)" /><span>{{ description }}</span></label>`,
  },
  LoadingIndicator: { template: '<span>Loading</span>' },
  Switch: {
    props: ['modelValue', 'label'],
    emits: ['update:modelValue'],
    template:
      '<input type="checkbox" :data-label="label" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
  },
  call: mocks.call,
  toast: mocks.toast,
}))

vi.mock('@/components/Layouts/SettingsLayoutBase.vue', () => ({
  default: {
    template:
      '<div><slot name="header-actions" /><slot name="content" /></div>',
  },
}))

vi.mock('@/components/Settings/WazzupPartnerConnection.vue', () => ({
  default: {
    props: ['channel', 'platform', 'displayName', 'available'],
    emits: ['updated', 'deleted', 'busy'],
    methods: {
      connected() {
        this.$emit('busy', true)
        const finish = () => {
          this.$emit('updated', {
            name: 'created-partner',
            provider: 'wazzup',
            platform: this.platform,
            custom_display_name: this.displayName,
            wazzup_api_mode: 'partner_api_v2',
            wazzup_status: 'active',
            enabled: true,
            state: 'connected',
          })
          this.$emit('busy', false)
        }
        if (mocks.deferPartnerConnection) mocks.finishPartnerConnection = finish
        else finish()
      },
    },
    template: `<div data-wazzup-partner-management :data-platform="platform" :data-name="displayName" :data-available="available">{{ channel?.name || 'new-partner' }}<button v-if="!channel?.name" @click="connected">Connect</button><button v-else @click="$emit('deleted', channel.name)">Delete Channel</button></div>`,
  },
}))

vi.mock('@/utils/messengerSettings', async (importOriginal) => ({
  ...(await importOriginal()),
  callWazzupSettings: (...args) => {
    mocks.safeCall(...args)
    return mocks.call(...args)
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
  mocks.safeCall.mockReset()
  mocks.toast.error.mockReset()
  mocks.toast.success.mockReset()
  mocks.deferPartnerConnection = false
  mocks.finishPartnerConnection = null
  vi.useRealTimers()
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
  const input = root.querySelector(`[data-label="${label}"]`)
  input.value = value
  input.dispatchEvent(
    new Event(input.tagName === 'SELECT' ? 'change' : 'input', {
      bubbles: true,
    }),
  )
  await nextTick()
}

describe('MessengerSettings Wazzup connection', () => {
  const whatsappId = 'b5436cae-2434-4b55-a477-99386aeeecb4'
  const telegramId = '970899f7-82ca-4fd8-9404-565ce53c8d0a'
  function channel(overrides = {}) {
    return {
      name: 'wazzup-1',
      provider: 'wazzup',
      platform: 'whatsapp',
      custom_display_name: 'Wazzup Sales',
      provider_channel_id: whatsappId,
      api_token_configured: true,
      enabled: true,
      state: 'unchecked',
      ...overrides,
    }
  }
  function connection(overrides = {}) {
    return {
      last_checked_at: '2026-10-05 12:00:00',
      api: { status: 'verified' },
      remote_channel: { status: 'verified', state: 'active' },
      subscription: {
        status: 'verified',
        url_matches: true,
        messages_and_statuses: true,
      },
      local_config: {
        status: 'verified',
        integration_enabled: true,
        channel_enabled: true,
      },
      delivery: { status: 'unverified', last_received_at: null },
      ...overrides,
    }
  }
  function button(root, label) {
    return [...root.querySelectorAll('button')].find(
      (button) => button.textContent.trim() === label,
    )
  }
  function setup({
    stored = [channel()],
    settings = { enabled: true },
    diagnostics = null,
    extra = () => {},
  } = {}) {
    mocks.call.mockImplementation((method, params) => {
      if (method === 'crm_messenger.api.settings.get_settings')
        return Promise.resolve({
          settings: { wazzup_legacy_ui_enabled: true, ...settings },
          channels: stored,
        })
      if (method === 'crm_messenger.api.diagnostics.get_health_summary')
        return Promise.resolve({ channels: diagnostics || [] })
      return extra(method, params)
    })
  }

  it('routes Partner v2 rows to onboarding without opening the legacy key form', async () => {
    setup({
      stored: [
        channel({
          wazzup_api_mode: 'partner_api_v2',
          wazzup_status: 'waiting_qr',
          api_token_configured: false,
          enabled: false,
        }),
      ],
    })
    const root = await mountSettings()
    expect(root.textContent).toContain('Waiting for QR scan')
    await clickButton(root, 'Wazzup Sales')
    expect(
      root.querySelector('[data-wazzup-partner-management]').textContent,
    ).toContain('wazzup-1')
    expect(root.querySelector('[data-label="Wazzup API key"]')).toBeNull()
    expect(mocks.call.mock.calls.map(([method]) => method)).not.toContain(
      'crm_messenger.api.wazzup_connection.check_channel',
    )
  })

  it.each([
    ['WhatsApp', 'whatsapp'],
    ['Telegram personal chats', 'telegram'],
  ])(
    'opens %s Partner onboarding from New Channel even before server configuration',
    async (label, platform) => {
      setup({
        settings: {
          wazzup_legacy_ui_enabled: false,
          wazzup_partner_available: false,
        },
      })
      const root = await mountSettings()
      await clickButton(root, 'New Channel')
      expect(root.textContent).not.toContain('Wazzup User API v3 (legacy)')
      await editField(
        root,
        'Provider',
        platform === 'telegram' ? 'partner_telegram' : 'partner_whatsapp',
      )
      expect(
        root.querySelector('[data-wazzup-partner-management]').textContent,
      ).toContain('new-partner')
      expect(
        root.querySelector('[data-wazzup-partner-management]').dataset.platform,
      ).toBe(platform)
      expect(
        root.querySelector('[data-wazzup-partner-management]').dataset
          .available,
      ).toBe('false')
      expect(button(root, 'New Channel')).toBeTruthy()
      expect(root.querySelector('[data-label="Wazzup API key"]')).toBeNull()
      expect(root.querySelector('[data-label="Channel ID"]')).toBeNull()
      expect(root.querySelector('[data-label="Provider"]')).not.toBeNull()
      expect(root.querySelectorAll('[data-dialog]')).toHaveLength(1)
      expect(root.querySelector('[data-label="Platform"]')).toBeNull()
    },
  )

  it('loads channels using a draft key without saving it and selects the UUID plus personal Telegram platform', async () => {
    setup({
      stored: [],
      extra: (method, params) => {
        expect(method).toBe('crm_messenger.api.wazzup_connection.list_channels')
        expect(params).toEqual({ api_token: 'draft-key' })
        return Promise.resolve({
          ok: true,
          channels: [
            {
              provider_channel_id: telegramId,
              platform: 'telegram',
              display_name: 'Telegram · @su***rt',
              remote_state: 'active',
            },
          ],
        })
      },
    })
    const root = await mountSettings()
    await clickButton(root, 'New Channel')
    await editField(root, 'Provider', 'wazzup')
    expect(button(root, 'Load Wazzup channels').disabled).toBe(true)
    expect(
      root.querySelector('input[data-label="Active in CRM"]').checked,
    ).toBe(false)
    expect(button(root, 'Check saved configuration')).toBeUndefined()
    await editField(root, 'Wazzup API key', 'draft-key')
    await clickButton(root, 'Load Wazzup channels')
    await editField(root, 'Available Wazzup channels', telegramId)
    expect(root.querySelector('[data-label="Channel ID"]').value).toBe(
      telegramId,
    )
    expect(root.querySelector('[data-label="Platform"]').value).toBe('telegram')
    expect(root.textContent).toContain('Telegram personal chats')
    expect(
      root.querySelector('input[data-label="Active in CRM"]').checked,
    ).toBe(false)
    expect(mocks.call.mock.calls.map(([method]) => method)).not.toContain(
      'crm_messenger.api.settings.save_channel',
    )
    expect(root.textContent).not.toContain('Channel Connected')
  })

  it('reuses a saved key server-side only on creation and never exposes it in the form', async () => {
    let created = false
    setup({
      extra: (method, params) => {
        if (method === 'crm_messenger.api.wazzup_connection.list_channels') {
          expect(params).toEqual({ channel: 'wazzup-1' })
          return Promise.resolve({
            ok: true,
            channels: [
              {
                provider_channel_id: telegramId,
                platform: 'telegram',
                display_name: 'Telegram · @su***rt',
              },
            ],
          })
        }
        if (method === 'crm_messenger.api.settings.save_channel') {
          expect(params).toMatchObject({
            provider: 'wazzup',
            platform: 'telegram',
            provider_channel_id: telegramId,
            api_token_source_channel: 'wazzup-1',
            enabled: false,
          })
          expect(params).not.toHaveProperty('api_token')
          created = true
          return Promise.resolve(
            channel({
              name: 'wazzup-new',
              platform: 'telegram',
              provider_channel_id: telegramId,
              enabled: false,
            }),
          )
        }
        throw new Error(`Unexpected method ${method}`)
      },
    })
    const root = await mountSettings()
    await clickButton(root, 'New Channel')
    await editField(root, 'Provider', 'wazzup')
    await editField(root, 'API key source', 'wazzup-1')
    await clickButton(root, 'Load Wazzup channels')
    await editField(root, 'Available Wazzup channels', telegramId)
    await clickButton(root, 'Create Channel')
    expect(created).toBe(true)
    expect(root.querySelector('[data-label="Wazzup API key"]').value).toBe('')
    expect(root.querySelector('[data-label="API key source"]')).toBeNull()
  })

  it('discards a late channel list when its credential draft changes', async () => {
    let resolveList
    setup({
      stored: [],
      extra: () =>
        new Promise((resolve) => {
          resolveList = resolve
        }),
    })
    const root = await mountSettings()
    await clickButton(root, 'New Channel')
    await editField(root, 'Provider', 'wazzup')
    await editField(root, 'Wazzup API key', 'first-key')
    await clickButton(root, 'Load Wazzup channels')
    await editField(root, 'Wazzup API key', 'second-key')
    resolveList({
      ok: true,
      channels: [
        {
          provider_channel_id: whatsappId,
          platform: 'whatsapp',
          display_name: 'Old account',
        },
      ],
    })
    await new Promise((resolve) => setTimeout(resolve, 0))
    await nextTick()
    expect(
      root.querySelector('[data-label="Available Wazzup channels"]'),
    ).toBeNull()
    expect(root.querySelector('[data-label="Wazzup API key"]').value).toBe(
      'second-key',
    )
    expect(root.textContent).not.toContain('Old account')
  })

  it('can rename and disable a saved legacy Wazzup channel while rejecting an invalid replacement ID', async () => {
    let stored = channel({ provider_channel_id: 'legacy-channel-id' })
    mocks.call.mockImplementation((method, params) => {
      if (method === 'crm_messenger.api.settings.get_settings')
        return Promise.resolve({
          settings: { wazzup_legacy_ui_enabled: true },
          channels: [stored],
        })
      if (method === 'crm_messenger.api.diagnostics.get_health_summary')
        return Promise.resolve({ channels: [] })
      if (method === 'crm_messenger.api.settings.save_channel') {
        expect(params).toMatchObject({
          provider_channel_id: 'legacy-channel-id',
          enabled: false,
          custom_display_name: 'Legacy disabled',
        })
        expect(params).not.toHaveProperty('original_wazzup_identity')
        stored = {
          ...stored,
          enabled: false,
          custom_display_name: params.custom_display_name,
        }
        return Promise.resolve(stored)
      }
      throw new Error(`Unexpected method ${method}`)
    })
    const root = await mountSettings()
    await clickButton(root, 'Wazzup Sales')
    await editField(root, 'Channel Name', 'Legacy disabled')
    const active = root.querySelector('input[data-label="Active in CRM"]')
    active.checked = false
    active.dispatchEvent(new Event('change', { bubbles: true }))
    await nextTick()
    await clickButton(root, 'Save')
    expect(root.querySelector('[data-label="Channel ID"]').value).toBe(
      'legacy-channel-id',
    )
    expect(
      root.querySelector('input[data-label="Active in CRM"]').checked,
    ).toBe(false)
    await editField(root, 'Channel ID', 'another-invalid-id')
    await clickButton(root, 'Save')
    expect(
      root.querySelector('[data-testid="channel-auth-error"]').textContent,
    ).toContain('Enter a Wazzup channel UUID.')
    expect(
      mocks.call.mock.calls.filter(
        ([method]) => method === 'crm_messenger.api.settings.save_channel',
      ),
    ).toHaveLength(1)
  })

  it('saves local activation explicitly without claiming a confirmed connection', async () => {
    let stored = channel({ enabled: false })
    mocks.call.mockImplementation((method, params) => {
      if (method === 'crm_messenger.api.settings.get_settings')
        return Promise.resolve({
          settings: { wazzup_legacy_ui_enabled: true },
          channels: [stored],
        })
      if (method === 'crm_messenger.api.diagnostics.get_health_summary')
        return Promise.resolve({ channels: [] })
      if (method === 'crm_messenger.api.settings.save_channel') {
        expect(params.enabled).toBe(true)
        expect(params).not.toHaveProperty('state')
        stored = { ...stored, enabled: true }
        return Promise.resolve(stored)
      }
      throw new Error(`Unexpected method ${method}`)
    })
    const root = await mountSettings()
    await clickButton(root, 'Wazzup Sales')
    const active = root.querySelector('input[data-label="Active in CRM"]')
    active.checked = true
    active.dispatchEvent(new Event('change', { bubbles: true }))
    await nextTick()
    await clickButton(root, 'Save')
    expect(root.textContent).toContain('Connection Not Checked')
    expect(root.textContent).not.toContain('Channel Connected')
  })

  it('checks saved configuration without turning verified reads into delivery confirmation', async () => {
    const checked = connection()
    setup({
      diagnostics: [
        {
          name: 'wazzup-1',
          provider: 'wazzup',
          webhook_queue: { queued: 2, retrying: 1, failed: 4 },
          media: { pending: 1, failed: 2 },
          error: 'private-provider-error',
        },
      ],
      extra: (method, params) => {
        expect(method).toBe('crm_messenger.api.wazzup_connection.check_channel')
        expect(params).toEqual({ channel: 'wazzup-1' })
        return Promise.resolve({
          ok: true,
          state: 'unchecked',
          message:
            'Configuration verified. Webhook delivery has not been verified.',
          connection: checked,
        })
      },
    })
    const root = await mountSettings()
    await clickButton(root, 'Wazzup Sales')
    await clickButton(root, 'Check saved configuration')
    expect(root.querySelector('[data-diagnostic="api"]').textContent).toContain(
      'Verified',
    )
    expect(
      root.querySelector('[data-diagnostic="subscription"]').textContent,
    ).toContain('Verified')
    expect(
      root.querySelector('[data-diagnostic="delivery"]').textContent,
    ).toContain('No event observed')
    expect(root.textContent).toContain('Connection Not Checked')
    expect(root.textContent).not.toContain('Channel Connected')
    expect(button(root, 'Connect / Repair')).toBeUndefined()
    expect(
      root.querySelector('[data-testid="wazzup-queue-diagnostics"]')
        .textContent,
    ).toContain('Webhook events: 3 pending, 4 failed.')
    expect(root.textContent).toContain('Attachments: 1 pending, 2 failed.')
    expect(root.textContent).not.toContain('private-provider-error')
  })

  it('blocks checks of dirty channel or global settings while preserving the edited key', async () => {
    setup()
    const root = await mountSettings()
    await clickButton(root, 'Wazzup Sales')
    await editField(root, 'Wazzup API key', 'changed-key')
    expect(button(root, 'Check saved configuration').disabled).toBe(true)
    await clickButton(root, 'Check saved configuration')
    expect(root.querySelector('[data-label="Wazzup API key"]').value).toBe(
      'changed-key',
    )
    expect(mocks.call).not.toHaveBeenCalledWith(
      'crm_messenger.api.wazzup_connection.check_channel',
      expect.anything(),
    )
    await editField(root, 'Wazzup API key', '')
    const globalSwitch = root.querySelector('input[type="checkbox"]')
    globalSwitch.checked = false
    globalSwitch.dispatchEvent(new Event('change', { bubbles: true }))
    await nextTick()
    expect(button(root, 'Check saved configuration').disabled).toBe(true)
    expect(root.textContent).toContain(
      'Save channel and messaging settings before checking the connection.',
    )
  })

  it('uses a newer channel event from refreshed settings over the earlier check response', async () => {
    let stored = channel()
    const latest = connection({
      remote_channel: { status: 'invalid', state: 'blocked' },
      delivery: {
        status: 'received',
        last_received_at: '2026-10-05 13:01:00',
        event_type: 'channel_update',
      },
    })
    mocks.call.mockImplementation((method) => {
      if (method === 'crm_messenger.api.settings.get_settings')
        return Promise.resolve({
          settings: { wazzup_legacy_ui_enabled: true, enabled: true },
          channels: [stored],
        })
      if (method === 'crm_messenger.api.diagnostics.get_health_summary')
        return Promise.resolve({ channels: [] })
      if (method === 'crm_messenger.api.wazzup_connection.check_channel') {
        stored = channel({
          state: 'degraded',
          integration: { wazzup_connection: latest },
        })
        return Promise.resolve({
          ok: true,
          state: 'unchecked',
          message:
            'Configuration verified. Webhook delivery has not been verified.',
          connection: connection(),
        })
      }
      throw new Error(`Unexpected method ${method}`)
    })
    const root = await mountSettings()
    await clickButton(root, 'Wazzup Sales')
    await clickButton(root, 'Check saved configuration')
    expect(
      root.querySelector('[data-diagnostic="remote_channel"]').textContent,
    ).toContain('Needs Attention')
    expect(
      root.querySelector('[data-diagnostic="delivery"]').textContent,
    ).toContain('Event received')
    expect(
      root.querySelector('[data-diagnostic="delivery"]').textContent,
    ).toContain('2026-10-05 13:01:00')
    expect(root.textContent).not.toContain('Configuration Checked')
  })

  it('falls back to the completed check when settings reload fails instead of using cached diagnostics', async () => {
    let loads = 0
    const cached = connection({ api: { status: 'invalid' } })
    mocks.call.mockImplementation((method) => {
      if (method === 'crm_messenger.api.settings.get_settings') {
        if (++loads > 1) return Promise.reject(new Error('reload failed'))
        return Promise.resolve({
          settings: { wazzup_legacy_ui_enabled: true, enabled: true },
          channels: [channel({ integration: { wazzup_connection: cached } })],
        })
      }
      if (method === 'crm_messenger.api.diagnostics.get_health_summary')
        return Promise.resolve({ channels: [] })
      if (method === 'crm_messenger.api.wazzup_connection.check_channel')
        return Promise.resolve({
          ok: true,
          state: 'unchecked',
          message:
            'Configuration verified. Webhook delivery has not been verified.',
          connection: connection(),
        })
      throw new Error(`Unexpected method ${method}`)
    })
    const root = await mountSettings()
    await clickButton(root, 'Wazzup Sales')
    await clickButton(root, 'Check saved configuration')
    expect(root.querySelector('[data-diagnostic="api"]').textContent).toContain(
      'Verified',
    )
    expect(
      root.querySelector('[data-diagnostic="api"]').textContent,
    ).not.toContain('Needs Attention')
    expect(mocks.toast.success).toHaveBeenCalledWith(
      'Wazzup diagnostics refreshed.',
    )
  })

  it('syncs changed server channel identity after a check without leaving an apparently clean stale form', async () => {
    let stored = channel()
    mocks.call.mockImplementation((method) => {
      if (method === 'crm_messenger.api.settings.get_settings')
        return Promise.resolve({
          settings: { wazzup_legacy_ui_enabled: true, enabled: true },
          channels: [stored],
        })
      if (method === 'crm_messenger.api.diagnostics.get_health_summary')
        return Promise.resolve({ channels: [] })
      if (method === 'crm_messenger.api.wazzup_connection.check_channel') {
        stored = channel({
          platform: 'telegram',
          provider_channel_id: telegramId,
          enabled: false,
          integration: { wazzup_connection: {} },
        })
        return Promise.resolve({
          ok: false,
          reason: 'settings_changed',
          message:
            'Channel settings changed during verification. Check the channel again.',
        })
      }
      throw new Error(`Unexpected method ${method}`)
    })
    const root = await mountSettings()
    await clickButton(root, 'Wazzup Sales')
    await clickButton(root, 'Check saved configuration')
    expect(root.querySelector('[data-label="Channel ID"]').value).toBe(
      telegramId,
    )
    expect(root.querySelector('[data-label="Platform"]').value).toBe('telegram')
    expect(
      root.querySelector('input[data-label="Active in CRM"]').checked,
    ).toBe(false)
    expect(button(root, 'Check saved configuration').disabled).toBe(false)
    expect(root.querySelector('[data-diagnostic="api"]').textContent).toContain(
      'Not checked',
    )
    expect(
      root.querySelector('[data-testid="channel-auth-error"]').textContent,
    ).toContain('Channel settings changed during verification.')
  })

  it('renders actual receipt independently from a failed subscription check and keeps errors sanitized', async () => {
    setup({
      extra: () =>
        Promise.resolve({
          ok: false,
          state: 'degraded',
          message:
            'The Wazzup webhook address or message subscription does not match this CRM.',
          connection: connection({
            subscription: { status: 'invalid' },
            delivery: {
              status: 'received',
              last_received_at: '2026-10-05 13:00:00',
              event_type: 'channel_update',
            },
            remote_event: {
              state: 'active',
              received_at: '2026-10-05 13:00:00',
            },
          }),
        }),
    })
    const root = await mountSettings()
    await clickButton(root, 'Wazzup Sales')
    await clickButton(root, 'Check saved configuration')
    expect(root.querySelector('[data-diagnostic="api"]').textContent).toContain(
      'Verified',
    )
    expect(
      root.querySelector('[data-diagnostic="subscription"]').textContent,
    ).toContain('Needs Attention')
    expect(
      root.querySelector('[data-diagnostic="delivery"]').textContent,
    ).toContain('Event received')
    expect(
      root.querySelector('[data-diagnostic="delivery"]').textContent,
    ).toContain('Channel update')
    expect(root.textContent).toContain('2026-10-05 13:00:00')
    expect(
      root.querySelector('[data-testid="channel-auth-error"]').textContent,
    ).toContain(
      'The Wazzup webhook address or message subscription does not match this CRM.',
    )
    mocks.call.mockImplementation((method) =>
      method === 'crm_messenger.api.settings.get_settings'
        ? Promise.resolve({
            settings: { wazzup_legacy_ui_enabled: true },
            channels: [channel()],
          })
        : Promise.reject({
            messages: ['Authorization: Bearer private-key; private payload'],
          }),
    )
    await clickButton(root, 'Check saved configuration')
    expect(
      root.querySelector('[data-testid="channel-auth-error"]').textContent,
    ).toContain('The provider operation failed.')
    expect(root.textContent).not.toContain('private-key')
    expect(root.textContent).not.toContain('private payload')
  })

  it('uses the silent settings boundary when saving a Shared Webhook Secret', async () => {
    setup({
      stored: [],
      extra: (method, params) => {
        expect(method).toBe('crm_messenger.api.settings.save_settings')
        expect(params.webhook_secret).toBe('test-webhook-secret')
        return Promise.resolve({
          enabled: true,
          webhook_secret_configured: true,
        })
      },
    })
    const root = await mountSettings()
    await clickButton(root, 'Webhooks')
    await editField(root, 'Shared Webhook Secret', 'test-webhook-secret')
    await clickButton(root, 'Save Settings')
    expect(mocks.safeCall).toHaveBeenCalledWith(
      'crm_messenger.api.settings.save_settings',
      expect.objectContaining({ webhook_secret: 'test-webhook-secret' }),
    )
    expect(
      root.querySelector('[data-label="Shared Webhook Secret"]').value,
    ).toBe('')
    expect(root.textContent).not.toContain('test-webhook-secret')
  })

  it('refreshes public channels and clears old diagnostics after saving global changes', async () => {
    let stored = channel({ integration: { wazzup_connection: connection() } })
    let globalEnabled = true
    mocks.call.mockImplementation((method, params) => {
      if (method === 'crm_messenger.api.settings.get_settings')
        return Promise.resolve({
          settings: { wazzup_legacy_ui_enabled: true, enabled: globalEnabled },
          channels: [stored],
        })
      if (method === 'crm_messenger.api.diagnostics.get_health_summary')
        return Promise.resolve({ channels: [] })
      if (method === 'crm_messenger.api.settings.save_settings') {
        globalEnabled = params.enabled
        stored = channel({ integration: {}, state: 'unchecked' })
        return Promise.resolve({ enabled: globalEnabled })
      }
      throw new Error(`Unexpected method ${method}`)
    })
    const root = await mountSettings()
    await clickButton(root, 'Wazzup Sales')
    expect(root.querySelector('[data-diagnostic="api"]').textContent).toContain(
      'Verified',
    )
    const globalSwitch = root.querySelector('input[type="checkbox"]')
    globalSwitch.checked = false
    globalSwitch.dispatchEvent(new Event('change', { bubbles: true }))
    await nextTick()
    await clickButton(root, 'Save Settings')
    expect(root.querySelector('[data-diagnostic="api"]').textContent).toContain(
      'Not checked',
    )
    expect(root.textContent).not.toContain('Last checked: 2026-10-05 12:00:00')
    expect(
      mocks.call.mock.calls.filter(
        ([method]) => method === 'crm_messenger.api.settings.get_settings',
      ),
    ).toHaveLength(2)
  })

  it('hides old Wazzup proof after a successful global save even if the subsequent settings reload fails', async () => {
    let loads = 0
    mocks.call.mockImplementation((method) => {
      if (method === 'crm_messenger.api.settings.get_settings') {
        if (++loads > 1) return Promise.reject(new Error('reload failed'))
        return Promise.resolve({
          settings: { wazzup_legacy_ui_enabled: true, enabled: true },
          channels: [
            channel({ integration: { wazzup_connection: connection() } }),
          ],
        })
      }
      if (method === 'crm_messenger.api.diagnostics.get_health_summary')
        return Promise.resolve({ channels: [] })
      if (method === 'crm_messenger.api.settings.save_settings')
        return Promise.resolve({ enabled: false })
      throw new Error(`Unexpected method ${method}`)
    })
    const root = await mountSettings()
    await clickButton(root, 'Wazzup Sales')
    const globalSwitch = root.querySelector('input[type="checkbox"]')
    globalSwitch.checked = false
    globalSwitch.dispatchEvent(new Event('change', { bubbles: true }))
    await nextTick()
    await clickButton(root, 'Save Settings')
    expect(root.querySelector('[data-diagnostic="api"]').textContent).toContain(
      'Not checked',
    )
    await clickButton(root, 'Close')
    expect(root.textContent).toContain(
      'Could not load message channel settings.',
    )
    expect(root.textContent).not.toContain('Wazzup Sales')
    expect(root.textContent).not.toContain('Configuration Checked')
  })

  it('uses the saved Wazzup result after a replacement key save when the settings reload fails', async () => {
    let loads = 0
    const previous = channel({
      state: 'connected',
      integration: { wazzup_connection: connection() },
    })
    const saved = channel({
      integration: {
        wazzup_connection: {
          api: { status: 'unverified' },
          delivery: { status: 'unverified', last_received_at: null },
        },
      },
    })
    mocks.call.mockImplementation((method, params) => {
      if (method === 'crm_messenger.api.settings.get_settings') {
        if (++loads > 1) return Promise.reject(new Error('reload failed'))
        return Promise.resolve({
          settings: { wazzup_legacy_ui_enabled: true, enabled: true },
          channels: [previous],
        })
      }
      if (method === 'crm_messenger.api.diagnostics.get_health_summary')
        return Promise.resolve({ channels: [] })
      if (method === 'crm_messenger.api.settings.save_channel') {
        expect(params.api_token).toBe('replacement-key')
        return Promise.resolve(saved)
      }
      throw new Error(`Unexpected method ${method}`)
    })
    const root = await mountSettings()
    await clickButton(root, 'Wazzup Sales')
    await editField(root, 'Wazzup API key', 'replacement-key')
    await clickButton(root, 'Save')
    expect(root.querySelector('[data-diagnostic="api"]').textContent).toContain(
      'Not checked',
    )
    expect(root.querySelector('[data-label="Wazzup API key"]').value).toBe('')
    expect(root.textContent).not.toContain('Channel Connected')
    expect(root.textContent).not.toContain('Configuration Checked')
  })
})

describe('MessengerSettings Avito chat scan status', () => {
  const statusMethod = 'crm_messenger.api.provider_sync.get_channel_sync_status'
  const scanMethod = 'crm_messenger.api.provider_sync.enqueue_channel_sync'
  const savedChannel = (overrides = {}) => ({
    name: 'avito-1',
    provider: 'avito_direct',
    platform: 'avito',
    auth_type: 'client_credentials',
    custom_display_name: 'Avito Sales',
    client_id: 'saved-id',
    client_secret_configured: true,
    enabled: true,
    state: 'connected',
    avito_import_mode: 'all',
    ...overrides,
  })
  const completed = {
    status: 'succeeded',
    counts: { chat_unchanged: 359 },
    incomplete: false,
  }
  function setup(extra, channels = [savedChannel()]) {
    mocks.call.mockImplementation((method, params) => {
      if (method === 'crm_messenger.api.settings.get_settings') {
        return Promise.resolve({ settings: {}, channels })
      }
      return extra(method, params)
    })
  }
  const statusCalls = () =>
    mocks.call.mock.calls.filter(([method]) => method === statusMethod)
  async function timedMount() {
    vi.useFakeTimers()
    const mounting = mountSettings()
    await nextTick()
    await vi.advanceTimersByTimeAsync(0)
    return mounting
  }
  async function timedClick(root, label) {
    const clicking = clickButton(root, label)
    await vi.advanceTimersByTimeAsync(0)
    return clicking
  }

  it('polls an active scan to completion and keeps the last completed result visible', async () => {
    const statuses = [
      {
        status: 'queued',
        counts: {},
        last_completed_at: '2026-10-12 09:00:00',
        last_completed: completed,
      },
      {
        status: 'running',
        counts: { chat_unchanged: 100 },
        last_completed_at: '2026-10-12 09:00:00',
        last_completed: completed,
      },
      {
        ...completed,
        last_completed_at: '2026-10-12 09:05:00',
        last_completed: completed,
      },
    ]
    setup((method) => {
      expect(method).toBe(statusMethod)
      return Promise.resolve({ ok: true, ...statuses.shift() })
    })
    const root = await timedMount()
    await timedClick(root, 'Avito Sales')
    expect(
      root.querySelector('[data-testid="avito-import-status"]').textContent,
    ).toContain('Chat scan queued')
    expect(
      root.querySelector('[data-testid="avito-import-completed"]').textContent,
    ).toContain('2026-10-12 09:00:00')
    expect(
      root.querySelector('[data-testid="avito-import-counts"]').textContent,
    ).toContain('Chats checked: 359')
    expect(root.textContent).toContain('New chats in last scan: 0')
    expect(root.textContent).toContain('Unchanged chats: 359')
    await vi.advanceTimersByTimeAsync(5000)
    expect(
      root.querySelector('[data-testid="avito-import-status"]').textContent,
    ).toContain('Chats checked in current scan: 100')
    await vi.advanceTimersByTimeAsync(5000)
    expect(
      root.querySelector('[data-testid="avito-import-status"]').textContent,
    ).toContain('Chat scan completed')
    expect(
      root.querySelector('[data-testid="avito-import-completed"]').textContent,
    ).toContain('2026-10-12 09:05:00')
    await vi.advanceTimersByTimeAsync(20000)
    expect(statusCalls()).toHaveLength(3)
  })

  it('coalesces status reads and schedules the next poll only after the current read finishes', async () => {
    let finishStatus
    setup(
      () =>
        new Promise((resolve) => {
          finishStatus = resolve
        }),
    )
    const root = await timedMount()
    await timedClick(root, 'Avito Sales')
    const state = mounted[0].app._instance.setupState
    const first = state.loadAvitoImportStatus()
    expect(state.loadAvitoImportStatus()).toBe(first)
    await vi.advanceTimersByTimeAsync(20000)
    expect(statusCalls()).toHaveLength(1)
    finishStatus({ ok: true, status: 'running', counts: {} })
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(5000)
    expect(statusCalls()).toHaveLength(2)
    state.loadAvitoImportStatus()
    await vi.advanceTimersByTimeAsync(20000)
    expect(statusCalls()).toHaveLength(2)
    finishStatus({ ok: true, ...completed })
    await vi.advanceTimersByTimeAsync(0)
    expect(state.loadingAvitoImport).toBe(false)
  })

  it('retains the known status on a refresh failure and recovers on the next poll', async () => {
    let reads = 0
    setup(() => {
      reads += 1
      if (reads === 2) return Promise.reject(new Error('offline'))
      return Promise.resolve({
        ok: true,
        status: reads === 1 ? 'running' : 'succeeded',
        counts: {},
      })
    })
    const root = await timedMount()
    await timedClick(root, 'Avito Sales')
    await vi.advanceTimersByTimeAsync(5000)
    expect(root.textContent).toContain('Scanning chats')
    expect(root.textContent).toContain(
      'Could not refresh the Avito chat scan status.',
    )
    await vi.advanceTimersByTimeAsync(5000)
    expect(root.textContent).toContain('Chat scan completed')
    expect(
      root.querySelector('[data-testid="avito-import-refresh-error"]'),
    ).toBeNull()
  })

  it('stops polling on close and ignores a delayed response after the same channel reopens', async () => {
    const finishes = []
    setup(
      () =>
        new Promise((resolve) => {
          finishes.push(resolve)
        }),
    )
    const root = await timedMount()
    await timedClick(root, 'Avito Sales')
    await timedClick(root, 'Close')
    await vi.advanceTimersByTimeAsync(10000)
    expect(statusCalls()).toHaveLength(1)
    await timedClick(root, 'Avito Sales')
    finishes[0]({ ok: true, status: 'failed', counts: {} })
    await vi.advanceTimersByTimeAsync(0)
    const state = mounted[0].app._instance.setupState
    expect(state.avitoImportStatus).toBeNull()
    expect(state.loadingAvitoImport).toBe(true)
    finishes[1]({ ok: true, status: 'queued', counts: {} })
    await vi.advanceTimersByTimeAsync(0)
    await timedClick(root, 'Close')
    await vi.advanceTimersByTimeAsync(15000)
    expect(statusCalls()).toHaveLength(2)
  })

  it('keeps a different channel status and loading state isolated from old responses', async () => {
    const finishes = []
    setup(
      () =>
        new Promise((resolve) => {
          finishes.push(resolve)
        }),
      [
        savedChannel(),
        savedChannel({ name: 'avito-2', custom_display_name: 'Avito Support' }),
      ],
    )
    const root = await timedMount()
    await timedClick(root, 'Avito Sales')
    await timedClick(root, 'Avito Support')
    finishes[0]({
      ok: true,
      status: 'incomplete',
      counts: { chat_unverified: 50 },
    })
    await vi.advanceTimersByTimeAsync(0)
    const state = mounted[0].app._instance.setupState
    expect(state.avitoImportStatus).toBeNull()
    expect(state.loadingAvitoImport).toBe(true)
    finishes[1]({ ok: true, ...completed })
    await vi.advanceTimersByTimeAsync(0)
    expect(root.textContent).toContain('Chat scan completed')
    expect(root.textContent).not.toContain('Chats awaiting verification: 50')
    expect(statusCalls().map(([, params]) => params.channel)).toEqual([
      'avito-1',
      'avito-2',
    ])
  })

  it('clears the scheduled poll when the settings page unmounts', async () => {
    setup(() => Promise.resolve({ ok: true, status: 'running', counts: {} }))
    const root = await timedMount()
    await timedClick(root, 'Avito Sales')
    const current = mounted.pop()
    current.app.unmount()
    current.root.remove()
    await vi.advanceTimersByTimeAsync(20000)
    expect(statusCalls()).toHaveLength(1)
  })

  it('refreshes the new run after enqueue and discards an older in-flight status', async () => {
    let finishOldStatus
    let reads = 0
    setup((method) => {
      if (method === scanMethod)
        return Promise.resolve({ ok: true, status: 'queued' })
      expect(method).toBe(statusMethod)
      reads += 1
      if (reads === 1)
        return new Promise((resolve) => {
          finishOldStatus = resolve
        })
      return Promise.resolve({
        ok: true,
        status: 'queued',
        counts: {},
        last_completed: completed,
      })
    })
    const root = await timedMount()
    await timedClick(root, 'Avito Sales')
    await timedClick(root, 'Scan chats now')
    expect(root.textContent).toContain('Chat scan queued')
    finishOldStatus({ ok: true, status: 'succeeded', counts: {} })
    await vi.advanceTimersByTimeAsync(0)
    expect(statusCalls()).toHaveLength(2)
    expect(
      root.querySelector('[data-testid="avito-import-status"]').textContent,
    ).toContain('Chat scan queued')
    expect(mounted[0].app._instance.setupState.scanningAvitoImport).toBe(false)
  })

  it('refreshes status after saving and does not reopen a dialog closed during save', async () => {
    let finishSave
    setup((method) => {
      if (method === statusMethod)
        return Promise.resolve({ ok: true, ...completed })
      if (method === 'crm_messenger.api.settings.save_channel') {
        return new Promise((resolve) => {
          finishSave = resolve
        })
      }
      throw new Error(`Unexpected method ${method}`)
    })
    const root = await timedMount()
    await timedClick(root, 'Avito Sales')
    await timedClick(root, 'Save')
    finishSave(savedChannel())
    await vi.advanceTimersByTimeAsync(0)
    expect(statusCalls()).toHaveLength(2)
    await timedClick(root, 'Save')
    await timedClick(root, 'Close')
    finishSave(savedChannel())
    await vi.advanceTimersByTimeAsync(0)
    expect(mounted[0].app._instance.setupState.showChannelDialog).toBe(false)
    expect(statusCalls()).toHaveLength(2)
  })

  it('describes a pagination limit as an incomplete scan', async () => {
    setup(() =>
      Promise.resolve({
        ok: true,
        status: 'incomplete',
        counts: { chat_unchanged: 1100 },
        incomplete: true,
        incomplete_reason: 'max_offset_reached',
        truncated: true,
      }),
    )
    const root = await timedMount()
    await timedClick(root, 'Avito Sales')
    expect(root.textContent).toContain('Chat scan incomplete')
    expect(root.textContent).toContain(
      'The Avito API pagination limit was reached. Chats beyond this limit may not have been checked.',
    )
    expect(root.textContent).toContain('Chats checked: 1100')
    expect(root.textContent).not.toContain('Chat scan completed')
  })
})

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

  it('preserves the visible legacy end date when only the start date changes', async () => {
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
        channel = {
          ...channel,
          avito_import_from_date: params.avito_import_from_date,
          avito_import_to_date: params.avito_import_to_date,
          avito_import_started_at: '2026-10-12 12:00:00',
        }
        return Promise.resolve(channel)
      }
      throw new Error(`Unexpected method ${method}`)
    })
    const root = await mountSettings()
    await clickButton(root, 'Avito Sales')
    await editField(root, 'From date', '2026-08-01')
    await clickButton(root, 'Save')
    expect(mocks.call).toHaveBeenCalledWith(
      'crm_messenger.api.settings.save_channel',
      expect.objectContaining({
        avito_import_from_date: '2026-08-01',
        avito_import_to_date: '2026-09-04',
      }),
    )
    expect(root.querySelector('input[data-label="Through date"]').value).toBe(
      '2026-09-04',
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

describe('MessengerSettings ordinary channel creation', () => {
  it('refreshes server connection flags without overwriting unsaved messaging settings', async () => {
    let loads = 0
    mocks.call.mockImplementation(() =>
      Promise.resolve({
        settings: {
          enabled: true,
          wazzup_partner_available: ++loads > 1,
          wazzup_legacy_ui_enabled: loads > 1,
        },
        channels: [],
      }),
    )
    const root = await mountSettings()
    const toggle = root.querySelector('input[type="checkbox"]')
    toggle.checked = false
    toggle.dispatchEvent(new Event('change', { bubbles: true }))
    await nextTick()
    const refresh = [...root.querySelectorAll('button')].find(
      (button) => !button.textContent.trim(),
    )
    refresh.click()
    await new Promise((resolve) => setTimeout(resolve, 0))
    await clickButton(root, 'New Channel')
    expect(root.textContent).toContain('Wazzup User API v3 (legacy)')
    await editField(root, 'Provider', 'partner_whatsapp')
    expect(
      root.querySelector('[data-wazzup-partner-management]').dataset.available,
    ).toBe('true')
    expect(toggle.checked).toBe(false)
  })

  it('hides legacy rows and creation controls by default while keeping Partner channels visible', async () => {
    mocks.call.mockResolvedValue({
      settings: {},
      channels: [
        {
          name: 'old',
          provider: 'wazzup',
          platform: 'whatsapp',
          custom_display_name: 'Old legacy channel',
        },
        {
          name: 'partner',
          provider: 'wazzup',
          platform: 'telegram',
          wazzup_api_mode: 'partner_api_v2',
          provider_channel_id: 'private-provider-uuid',
          external_account_id: 'private-account-id',
        },
      ],
    })
    const root = await mountSettings()
    expect(root.textContent).not.toContain('Old legacy channel')
    expect(root.textContent).toContain('Telegram personal chats')
    expect(root.textContent).not.toContain('private-provider-uuid')
    expect(root.textContent).not.toContain('private-account-id')
    await clickButton(root, 'New Channel')
    const provider = root.querySelector('[data-label="Provider"]')
    expect([...provider.options].map((option) => option.textContent)).toEqual([
      'WhatsApp',
      'Telegram personal chats',
      'Telegram Bot',
      'VK',
      'MAX',
      'Avito',
    ])
    expect(provider.value).toBe('partner_whatsapp')
    expect(root.querySelectorAll('[data-dialog]')).toHaveLength(1)
    expect(root.querySelector('[data-channel-picker]')).toBeNull()
    expect(root.querySelector('[data-label="Platform"]')).toBeNull()
    expect(root.querySelector('[data-label="Wazzup API key"]')).toBeNull()
    expect(root.textContent).not.toContain('Wazzup')
  })

  it('restores legacy creation and existing channel settings only with the explicit flag', async () => {
    mocks.call.mockResolvedValue({
      settings: { wazzup_legacy_ui_enabled: true },
      channels: [
        {
          name: 'old',
          provider: 'wazzup',
          platform: 'whatsapp',
          custom_display_name: 'Old legacy channel',
          api_token_configured: true,
        },
      ],
    })
    const root = await mountSettings()
    expect(root.textContent).toContain('Old legacy channel')
    await clickButton(root, 'New Channel')
    await editField(root, 'Provider', 'wazzup')
    expect(root.querySelector('[data-label="Wazzup API key"]')).not.toBeNull()
    expect(root.querySelector('[data-label="Channel ID"]')).not.toBeNull()
  })

  it.each([
    ['VK', 'vk_direct', 'Community Access Token'],
    ['MAX', 'max_direct', 'Bot Token'],
    ['Telegram Bot', 'telegram_bot', 'Bot Token'],
    ['Avito', 'avito_direct', 'Client ID'],
  ])(
    'keeps the existing %s connection form',
    async (label, provider, credentialLabel) => {
      mocks.call.mockResolvedValue({ settings: {}, channels: [] })
      const root = await mountSettings()
      await clickButton(root, 'New Channel')
      await editField(root, 'Provider', provider)
      expect(root.querySelector('[data-label="Provider"]').value).toBe(provider)
      expect(
        root.querySelector(`[data-label="${credentialLabel}"]`),
      ).not.toBeNull()
      expect(root.querySelector('[data-wazzup-partner-management]')).toBeNull()
      expect(
        [...root.querySelector('[data-label="Provider"]').options].map(
          (option) => option.value,
        ),
      ).not.toContain('wazzup')
    },
  )

  it.each([
    ['WhatsApp', 'whatsapp'],
    ['Telegram personal chats', 'telegram'],
  ])(
    'uses the same ordinary %s entry with the simulator available',
    async (label, platform) => {
      mocks.call.mockResolvedValue({
        settings: { wazzup_partner_available: true },
        channels: [],
      })
      const root = await mountSettings()
      await clickButton(root, 'New Channel')
      await editField(
        root,
        'Provider',
        platform === 'telegram' ? 'partner_telegram' : 'partner_whatsapp',
      )
      const dialog = root.querySelector('[data-wazzup-partner-management]')
      expect(dialog.dataset.platform).toBe(platform)
      expect(dialog.dataset.available).toBe('true')
      expect(root.querySelector('[data-channel-picker]')).toBeNull()
      expect(root.querySelectorAll('[data-dialog]')).toHaveLength(1)
    },
  )

  it('keeps Partner creation, active state, settings and deletion in the same channel shell', async () => {
    mocks.call.mockResolvedValue({
      settings: { wazzup_partner_available: true },
      channels: [],
    })
    const root = await mountSettings()
    await clickButton(root, 'New Channel')
    const dialog = root.querySelector('[data-dialog]')
    expect(dialog.dataset.title).toBe('New Channel')
    await editField(root, 'Channel Name', 'Support WhatsApp')
    expect(
      root.querySelector('[data-wazzup-partner-management]').dataset.name,
    ).toBe('Support WhatsApp')
    await clickButton(root, 'Connect')
    expect(root.querySelectorAll('[data-dialog]')).toHaveLength(1)
    expect(root.querySelector('[data-dialog]')).toBe(dialog)
    expect(dialog.dataset.title).toBe('Channel Settings')
    expect(dialog.textContent).toContain('Support WhatsApp')
    expect(dialog.textContent).toContain('WhatsApp')
    expect(dialog.textContent).toContain('Channel Connected')
    expect(root.querySelector('[data-label="Provider"]').disabled).toBe(true)
    expect(root.querySelector('[data-label="Channel Name"]').disabled).toBe(
      true,
    )
    expect(root.querySelector('[data-label="Wazzup API key"]')).toBeNull()
    expect(root.querySelector('[data-label="Channel ID"]')).toBeNull()
    expect(root.querySelector('[data-label="Platform"]')).toBeNull()
    await clickButton(root, 'Close')
    expect(root.querySelector('[data-dialog]')).toBeNull()
    await clickButton(root, 'Support WhatsApp')
    expect(root.querySelector('[data-dialog]').dataset.title).toBe(
      'Channel Settings',
    )
    expect(root.querySelectorAll('[data-dialog]')).toHaveLength(1)
    expect(root.textContent).not.toContain('Connect WhatsApp / Telegram')
    await clickButton(root, 'Delete Channel')
    expect(root.querySelector('[data-dialog]')).toBeNull()
    expect(root.textContent).not.toContain('Support WhatsApp')
  })

  it('protects a pending Partner creation from provider changes and modal dismissal, then restores closing', async () => {
    mocks.call.mockResolvedValue({
      settings: { wazzup_partner_available: true },
      channels: [],
    })
    mocks.deferPartnerConnection = true
    const root = await mountSettings()
    await clickButton(root, 'New Channel')
    await editField(root, 'Channel Name', 'Pending WhatsApp')
    const dialog = root.querySelector('[data-dialog]')
    await clickButton(root, 'Connect')
    expect(root.querySelector('[data-label="Provider"]').disabled).toBe(true)
    expect(root.querySelector('[data-label="Channel Name"]').disabled).toBe(
      true,
    )
    expect(dialog.dataset.dismissible).toBe('false')
    expect(dialog.dataset.closeButton).toBe('false')
    const close = [...dialog.querySelectorAll('button')].find(
      (item) => item.textContent === 'Close',
    )
    expect(close.disabled).toBe(true)
    await clickButton(root, 'Close')
    expect(root.querySelector('[data-dialog]')).toBe(dialog)
    mocks.finishPartnerConnection()
    await nextTick()
    expect(dialog.dataset.title).toBe('Channel Settings')
    expect(dialog.dataset.dismissible).toBe('true')
    expect(dialog.dataset.closeButton).toBe('true')
    expect(close.disabled).toBe(false)
    await clickButton(root, 'Close')
    expect(root.querySelector('[data-dialog]')).toBeNull()
    expect(root.textContent).toContain('Pending WhatsApp')
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
