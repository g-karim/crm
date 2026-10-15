import { createApp, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ call: vi.fn() }))

vi.mock('frappe-ui', () => ({
  Badge: { props: ['label'], template: '<span>{{ label }}</span>' },
  Button: {
    props: ['label', 'disabled', 'loading'],
    emits: ['click'],
    template:
      '<button type="button" :disabled="disabled || loading" @click="$emit(\'click\')">{{ label }}</button>',
  },
  Dialog: {
    props: ['open'],
    template:
      '<div v-if="open" data-dialog><slot name="body-content" /><slot name="actions" /></div>',
  },
  FormControl: {
    props: ['modelValue', 'label', 'type', 'disabled', 'options'],
    emits: ['update:modelValue'],
    template: `<label>{{ label }}<select v-if="type === 'select'" :data-label="label" :value="modelValue" :disabled="disabled" @change="$emit('update:modelValue', $event.target.value)"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select><input v-else :data-label="label" :type="type || 'text'" :value="modelValue" :disabled="disabled" @input="$emit('update:modelValue', $event.target.value)" /></label>`,
  },
  LoadingIndicator: { template: '<span>Loading</span>' },
}))

vi.mock('@/utils/wazzupPartnerConnection', async (original) => ({
  ...(await original()),
  callWazzupPartner: (...args) => mocks.call(...args),
}))

import WazzupPartnerConnection from '@/components/Settings/WazzupPartnerConnection.vue'
import { normalizePartnerConnection } from '@/utils/wazzupPartnerConnection'

const PNG = 'data:image/png;base64,aGVsbG8='
let mounted = []

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-07T12:00:00Z'))
})

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
  mocks.call.mockReset()
  vi.useRealTimers()
})

function result(status = 'waiting_qr', overrides = {}) {
  return normalizePartnerConnection({
    ok: true,
    ...overrides,
    channel: {
      name: 'PARTNER-1',
      platform: 'whatsapp',
      enabled: status === 'active',
      wazzup_status: status,
      state: status === 'active' ? 'connected' : 'unchecked',
      ...overrides.channel,
    },
    onboarding: {
      status,
      qr_code: PNG,
      qr_expires_at: '2026-10-07T12:02:00Z',
      can_submit_2fa: status === 'waiting_2fa',
      can_reconnect: true,
      ...overrides.onboarding,
    },
    simulator: overrides.simulator !== false,
  })
}

async function settle() {
  for (let index = 0; index < 6; index++) await Promise.resolve()
  await nextTick()
}

async function mount(channel = null, props = {}) {
  const root = document.createElement('div')
  const updated = vi.fn()
  const deleted = vi.fn()
  const busy = vi.fn()
  document.body.appendChild(root)
  const app = createApp(WazzupPartnerConnection, {
    channel,
    platform: channel?.platform || 'whatsapp',
    displayName: '',
    ...props,
    onUpdated: updated,
    onDeleted: deleted,
    onBusy: busy,
  })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  const entry = { root, app, updated, deleted, busy }
  mounted.push(entry)
  await settle()
  return entry
}

async function click(root, label) {
  const button = [...root.querySelectorAll('button')].find(
    (item) => item.textContent.trim() === label,
  )
  expect(button).toBeTruthy()
  button.click()
  await settle()
}

async function edit(root, label, value) {
  const input = root.querySelector(`[data-label="${label}"]`)
  expect(input).toBeTruthy()
  input.value = value
  input.dispatchEvent(
    new Event(input.tagName === 'SELECT' ? 'change' : 'input', {
      bubbles: true,
    }),
  )
  await nextTick()
}

describe('embedded Partner connection state and actions', () => {
  it('explains unavailable configuration without asking for credentials or making a request', async () => {
    const { root } = await mount(null, {
      available: false,
      platform: 'telegram',
    })
    expect(root.querySelector('[data-dialog]')).toBeNull()
    expect(root.querySelector('[data-label="Platform"]')).toBeNull()
    expect(root.querySelector('[data-label="Channel Name"]')).toBeNull()
    expect(root.textContent).toContain('Connection is not configured.')
    expect(
      [...root.querySelectorAll('button')].find(
        (button) => button.textContent === 'Connect',
      ).disabled,
    ).toBe(true)
    expect(root.querySelector('[data-label="Wazzup API key"]')).toBeNull()
    expect(root.querySelector('[data-label="Channel ID"]')).toBeNull()
    expect(mocks.call).not.toHaveBeenCalled()
  })

  it.each(['whatsapp', 'telegram'])(
    'starts the selected %s platform without a manual provider UUID or API key',
    async (platform) => {
      mocks.call.mockResolvedValue(
        result('waiting_qr', { channel: { platform } }),
      )
      const { root } = await mount(null, {
        platform,
        displayName: '  Support  ',
      })
      await click(root, 'Connect')
      expect(mocks.call).toHaveBeenCalledWith('start_connection', {
        platform,
        custom_display_name: 'Support',
        client_request_id: expect.any(String),
      })
      expect(root.querySelector('[data-label="Wazzup API key"]')).toBeNull()
      expect(root.querySelector('[data-label="Channel ID"]')).toBeNull()
      expect(root.querySelector('[data-label="Platform"]')).toBeNull()
      expect(root.querySelector('[data-label="Channel Name"]')).toBeNull()
      expect(root.querySelector('[data-dialog]')).toBeNull()
      expect(root.textContent).not.toContain('Wazzup')
    },
  )

  it('reports manual connection busy until the request finishes and rejects duplicate clicks', async () => {
    let finish
    mocks.call.mockImplementation(
      () => new Promise((resolve) => (finish = resolve)),
    )
    const { root, busy, updated } = await mount(null, {
      platform: 'whatsapp',
      displayName: 'Support',
    })
    await click(root, 'Connect')
    expect(busy).toHaveBeenLastCalledWith(true)
    expect(root.querySelector('button').disabled).toBe(true)
    await click(root, 'Connect')
    expect(mocks.call).toHaveBeenCalledTimes(1)
    finish(result('waiting_qr'))
    await settle()
    expect(busy.mock.calls.map(([value]) => value)).toEqual([true, false])
    expect(updated).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'PARTNER-1' }),
    )
    expect(root.querySelector('[data-wazzup-qr]')).not.toBeNull()
  })
  it('connects WhatsApp, displays QR and becomes active without emitting QR in the public channel', async () => {
    mocks.call.mockImplementation(async (method) =>
      method === 'simulator_scan' ? result('active') : result(),
    )
    const { root, updated } = await mount()
    await click(root, 'Connect')
    expect(mocks.call.mock.calls[0]).toEqual([
      'start_connection',
      {
        platform: 'whatsapp',
        custom_display_name: '',
        client_request_id: expect.any(String),
      },
    ])
    expect(root.querySelector('[data-wazzup-qr]').getAttribute('src')).toBe(PNG)
    expect(root.textContent).toContain('Waiting for QR scan')
    expect(root.textContent).toContain('Use the simulator button below')
    expect(root.textContent).not.toContain(
      'Scan this QR code in the messenger app.',
    )
    expect(JSON.stringify(updated.mock.calls)).not.toContain(PNG)
    await click(root, 'Simulate QR scan')
    expect(mocks.call).toHaveBeenCalledWith('simulator_scan', {
      channel: 'PARTNER-1',
      require_2fa: false,
    })
    expect(root.textContent).toContain('Channel Connected')
    expect(root.querySelector('[data-wazzup-qr]')).toBeNull()
    expect(root.querySelector('[data-label="Wazzup API key"]')).toBeNull()
  })

  it('handles Telegram 2FA, clears password after rejection and after success', async () => {
    let submits = 0
    mocks.call.mockImplementation(async (method) => {
      if (method === 'start_connection')
        return result('waiting_qr', {
          channel: { name: 'PARTNER-1', platform: 'telegram' },
        })
      if (method === 'simulator_scan')
        return result('waiting_2fa', {
          channel: { name: 'PARTNER-1', platform: 'telegram' },
        })
      if (method === 'submit_2fa' && ++submits === 1)
        return result('waiting_2fa', {
          channel: { name: 'PARTNER-1', platform: 'telegram' },
          onboarding: { error: 'raw-provider-private', can_submit_2fa: true },
        })
      return result('active', {
        channel: { name: 'PARTNER-1', platform: 'telegram' },
      })
    })
    const { root } = await mount(null, { platform: 'telegram' })
    await click(root, 'Connect')
    await click(root, 'Simulate QR scan')
    expect(mocks.call).toHaveBeenCalledWith('simulator_scan', {
      channel: 'PARTNER-1',
      require_2fa: true,
    })
    await edit(
      root,
      'Two-factor authentication password',
      'wrong-private-password',
    )
    await click(root, 'Submit password')
    expect(root.querySelector('[data-wazzup-2fa] input').value).toBe('')
    expect(root.textContent).toContain(
      'The two-factor authentication password was rejected.',
    )
    expect(root.textContent).not.toContain('wrong-private-password')
    await edit(
      root,
      'Two-factor authentication password',
      'correct-private-password',
    )
    await click(root, 'Submit password')
    expect(root.textContent).toContain('Channel Connected')
    expect(root.querySelector('[data-wazzup-2fa]')).toBeNull()
    expect(root.textContent).not.toContain('correct-private-password')
  })

  it('expires QR locally, hides the old image and refreshes using reconnect', async () => {
    let reconnected = false
    mocks.call.mockImplementation(async (method) => {
      if (method === 'reconnect') reconnected = true
      return result('waiting_qr', {
        onboarding: {
          status: 'waiting_qr',
          qr_code: PNG,
          qr_expires_at: reconnected
            ? '2026-10-07T12:05:00Z'
            : '2026-10-07T12:00:01Z',
          can_reconnect: true,
        },
      })
    })
    const { root } = await mount({
      name: 'PARTNER-1',
      platform: 'whatsapp',
      wazzup_status: 'waiting_qr',
    })
    expect(root.querySelector('[data-wazzup-qr]')).not.toBeNull()
    await vi.advanceTimersByTimeAsync(2500)
    await settle()
    expect(root.querySelector('[data-wazzup-qr]')).toBeNull()
    expect(root.textContent).toContain('QR code has expired.')
    await click(root, 'Refresh QR code')
    expect(mocks.call).toHaveBeenCalledWith('reconnect', {
      channel: 'PARTNER-1',
    })
    expect(root.querySelector('[data-wazzup-qr]')).not.toBeNull()
  })

  it('clears the password before HTTP completes and ignores a result after the parent unmounts it', async () => {
    let resolvePassword
    mocks.call.mockImplementation((method) => {
      if (method === 'submit_2fa') {
        return new Promise((resolve) => {
          resolvePassword = resolve
        })
      }
      return Promise.resolve(
        result('waiting_2fa', {
          channel: { name: 'PARTNER-1', platform: 'telegram' },
        }),
      )
    })
    const entry = await mount({
      name: 'PARTNER-1',
      platform: 'telegram',
      wazzup_status: 'waiting_2fa',
    })
    const { root, updated } = entry
    await edit(
      root,
      'Two-factor authentication password',
      'private-pending-password',
    )
    await click(root, 'Submit password')
    expect(root.querySelector('[data-wazzup-2fa] input').value).toBe('')
    expect(root.textContent).not.toContain('private-pending-password')
    const updates = updated.mock.calls.length
    entry.app.unmount()
    mounted = mounted.filter((item) => item !== entry)
    resolvePassword(result('active'))
    await settle()
    await vi.advanceTimersByTimeAsync(10000)
    expect(updated).toHaveBeenCalledTimes(updates)
    expect(root.querySelector('[data-wazzup-partner-connection]')).toBeNull()
    expect(mocks.call).toHaveBeenCalledTimes(2)
    root.remove()
  })

  it('polls active state, displays unauthorized and permits explicit reconnect', async () => {
    let reads = 0
    mocks.call.mockImplementation(async (method) =>
      method === 'reconnect'
        ? result()
        : result(++reads === 1 ? 'active' : 'unauthorized'),
    )
    const { root } = await mount({ name: 'PARTNER-1', wazzup_status: 'active' })
    expect(root.textContent).toContain('Channel Connected')
    await vi.advanceTimersByTimeAsync(2500)
    await settle()
    expect(root.textContent).toContain('Authorization expired')
    await click(root, 'Reconnect')
    expect(root.querySelector('[data-wazzup-qr]')).not.toBeNull()
  })

  it('checks Partner diagnostics and recovers the channel without a status webhook', async () => {
    mocks.call.mockImplementation(async (method) =>
      method === 'check_channel'
        ? result('active', {
            simulator: false,
            integration: {
              wazzup_partner: {
                status: 'active',
                last_checked_at: '2026-10-07 12:00:01',
                reconciliation: { status: 'verified' },
                account: { status: 'ready', enabled: true },
                webhook_subscription: {
                  status: 'configured',
                  last_checked_at: '2026-10-07 12:00:00',
                },
                delivery: { status: 'unverified' },
              },
            },
          })
        : result('waiting_qr', { simulator: false }),
    )
    const { root, updated } = await mount({
      name: 'PARTNER-1',
      wazzup_status: 'waiting_qr',
    })
    expect(root.querySelector('[data-wazzup-qr]')).not.toBeNull()
    await click(root, 'Check connection')
    expect(mocks.call).toHaveBeenLastCalledWith('check_channel', {
      channel: 'PARTNER-1',
    })
    const diagnostics = root.querySelector('[data-wazzup-partner-diagnostics]')
    expect(
      diagnostics.querySelector('[data-diagnostic="remote_channel"]')
        .textContent,
    ).toContain('Channel Connected')
    expect(
      diagnostics.querySelector('[data-diagnostic="subscription"]').textContent,
    ).toContain('Configured')
    expect(
      diagnostics.querySelector('[data-diagnostic="subscription"]').textContent,
    ).toContain('Last checked: 2026-10-07 12:00:00')
    expect(
      diagnostics.querySelector('[data-diagnostic="delivery"]').textContent,
    ).toContain('No event observed')
    expect(root.querySelector('[data-wazzup-qr]')).toBeNull()
    expect(root.textContent).not.toContain('Wazzup')
    expect(root.textContent).not.toContain('API key')
    expect(updated.mock.lastCall[0]).toMatchObject({
      wazzup_status: 'active',
      integration: { wazzup_partner: { status: 'active' } },
    })
    expect(mocks.call.mock.calls.map(([method]) => method)).toEqual([
      'get_onboarding_state',
      'check_channel',
    ])
  })

  it('replaces confirmed webhook evidence after an unresolved check and clears missing diagnostics', async () => {
    let reads = 0
    mocks.call.mockImplementation(async () =>
      result('active', {
        ...(++reads < 3
          ? {
              integration: {
                wazzup_partner: {
                  status: 'active',
                  webhook_subscription: {
                    status: reads === 1 ? 'configured' : 'unknown',
                    last_checked_at: '2026-10-07 12:00:00',
                  },
                },
              },
            }
          : {}),
      }),
    )
    const { root } = await mount({ name: 'PARTNER-1', wazzup_status: 'active' })
    const subscription = () =>
      root.querySelector('[data-diagnostic="subscription"]').textContent
    expect(subscription()).toContain('Configured')
    await click(root, 'Check connection')
    expect(subscription()).toContain('Result unknown')
    expect(subscription()).not.toContain('Configured')
    await click(root, 'Refresh Status')
    expect(subscription()).toContain('Not checked')
    expect(subscription()).not.toContain('Last checked')
  })

  it('keeps lifecycle state visible when the provider read fails and recovers on refresh', async () => {
    let reads = 0
    mocks.call.mockImplementation(async () =>
      result('disabled', {
        onboarding: { can_reconnect: true },
        integration: {
          wazzup_partner: {
            status: 'disabled',
            reconciliation: { status: ++reads === 1 ? 'error' : 'verified' },
            account: { status: 'ready', enabled: true },
            webhook_subscription: { status: 'configured' },
          },
        },
      }),
    )
    const { root } = await mount({ name: 'PARTNER-1', wazzup_status: 'active' })
    expect(root.querySelector('[role="status"]').textContent).toContain(
      'Channel Disabled',
    )
    expect(
      root.querySelector('[data-diagnostic="remote_channel"]').textContent,
    ).toContain('Could not verify')
    expect(
      [...root.querySelectorAll('button')].some(
        (button) => button.textContent === 'Reconnect',
      ),
    ).toBe(true)
    await click(root, 'Refresh Status')
    expect(
      root.querySelector('[data-diagnostic="remote_channel"]').textContent,
    ).toContain('Channel Disabled')
  })

  it('rejects a stale polling response after reconnect and cancels polling on unmount', async () => {
    let resolvePoll
    let reads = 0
    mocks.call.mockImplementation((method) => {
      if (method === 'get_onboarding_state' && ++reads === 2)
        return new Promise((resolve) => {
          resolvePoll = resolve
        })
      return Promise.resolve(
        method === 'reconnect' ? result('active') : result(),
      )
    })
    const entry = await mount({
      name: 'PARTNER-1',
      wazzup_status: 'waiting_qr',
    })
    await vi.advanceTimersByTimeAsync(2500)
    await click(entry.root, 'Reconnect')
    resolvePoll(result('waiting_2fa'))
    await settle()
    expect(entry.root.textContent).toContain('Channel Connected')
    expect(entry.root.querySelector('[data-wazzup-2fa]')).toBeNull()
    const calls = mocks.call.mock.calls.length
    entry.app.unmount()
    entry.root.remove()
    mounted = []
    await vi.advanceTimersByTimeAsync(10000)
    expect(mocks.call).toHaveBeenCalledTimes(calls)
  })

  it('deletes only after confirmation, emits deletion and hides simulator controls in non-simulator responses', async () => {
    mocks.call.mockImplementation(async (method) =>
      result(method === 'delete_channel' ? 'deleted' : 'active', {
        simulator: false,
      }),
    )
    const { root, deleted } = await mount({
      name: 'PARTNER-1',
      wazzup_status: 'active',
    })
    expect(root.textContent).not.toContain('Local simulator')
    await click(root, 'Delete Channel')
    expect(mocks.call.mock.calls.map(([method]) => method)).not.toContain(
      'delete_channel',
    )
    root.querySelector('[data-wazzup-confirm-delete]').click()
    await settle()
    expect(mocks.call).toHaveBeenCalledWith('delete_channel', {
      channel: 'PARTNER-1',
    })
    expect(deleted).toHaveBeenCalledWith('PARTNER-1')
    const calls = mocks.call.mock.calls.length
    await vi.advanceTimersByTimeAsync(10000)
    expect(mocks.call).toHaveBeenCalledTimes(calls)
  })
})
