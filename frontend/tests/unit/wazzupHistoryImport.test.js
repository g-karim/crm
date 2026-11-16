import { createApp, h, nextTick, reactive } from 'vue'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('frappe-ui', async () => {
  const { default: dayjs } = await import('dayjs')
  const { default: utc } = await import('dayjs/plugin/utc')
  const { default: timezone } = await import('dayjs/plugin/timezone')
  dayjs.extend(utc)
  dayjs.extend(timezone)
  return {
    dayjs,
    Button: {
      props: ['label', 'disabled', 'loading'],
      emits: ['click'],
      template:
        '<button type="button" :disabled="disabled || loading" @click="$emit(\'click\')">{{ label }}</button>',
    },
    FormControl: {
      props: ['modelValue', 'label', 'type', 'disabled'],
      emits: ['update:modelValue'],
      template:
        '<label>{{ label }}<input :data-label="label" :type="type" :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" /></label>',
    },
  }
})

import WazzupHistoryImport from '@/components/Settings/WazzupHistoryImport.vue'
import {
  callWazzupHistory,
  canResumeHistoryImport,
  historyImportPeriod,
  historyImportPolicy,
  historyImportPolicyLabel,
  formatHistoryImportTime,
  newHistoryImportForm,
  normalizeHistoryImport,
} from '@/utils/wazzupHistoryImport'

const API = 'crm_messenger.api.wazzup_partner_history'
let mounted = []
let handlers
let remote
let previousTimezone
let previousCsrf

const counts = (overrides = {}) => ({
  created: 0,
  duplicate: 0,
  tombstone: 0,
  unknown_conversation: 0,
  unresolved: 0,
  rejected: 0,
  ...overrides,
})
const progress = (overrides = {}) => ({
  total: 6,
  processed: 3,
  counts: counts({ created: 2, duplicate: 1 }),
  replay_processed: null,
  replay_total: null,
  conversations_created: 0,
  leads_created: 0,
  ...overrides,
})
const result = (outcome = 'succeeded') => ({
  version: 1,
  outcome,
  reason: outcome === 'failed' ? 'invalid_csv' : null,
  total: outcome === 'failed' ? null : 6,
  processed: outcome === 'failed' ? 0 : 6,
  counts: counts(
    outcome === 'failed'
      ? {}
      : outcome === 'partial'
        ? { created: 3, unknown_conversation: 1, unresolved: 1, rejected: 1 }
        : { created: 6 },
  ),
  conversations_created: outcome === 'failed' ? 0 : 2,
  leads_created: 0,
})

function channel(overrides = {}) {
  return {
    name: 'PARTNER-1',
    provider: 'wazzup',
    wazzup_api_mode: 'partner_api_v2',
    platform: 'whatsapp',
    enabled: true,
    state: 'connected',
    wazzup_status: 'active',
    ...overrides,
  }
}

function dto(overrides = {}) {
  const state = overrides.state || 'queued'
  return {
    ok: true,
    import_id: 'IMPORT-1',
    channel: 'PARTNER-1',
    generation: 1,
    state,
    active: !['completed', 'failed', 'cancelled'].includes(state),
    start_at: '2026-11-01T21:00:00Z',
    end_at: '2026-11-03T20:59:59.999Z',
    file_status: null,
    file: null,
    result: null,
    progress: null,
    error: null,
    ...overrides,
    policy: {
      create_conversations: true,
      create_leads: false,
      ...overrides.policy,
    },
    processing: {
      enabled: true,
      phase: 'validate',
      error: null,
      ...overrides.processing,
    },
  }
}

function ready(overrides = {}) {
  return dto({
    state: 'export_ready',
    file_status: 'ready',
    file: { format: 'csv' },
    generation: 17,
    processing: { phase: 'blocked', error: 'batch_failed' },
    progress: progress(),
    ...overrides,
  })
}

function response(message, status = 200, extra = {}) {
  return {
    ok: status === 200,
    status,
    json: async () => ({ message, ...extra }),
  }
}

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}

function requests(action) {
  return fetch.mock.calls
    .filter(([url]) => url === `/api/method/${API}.${action}`)
    .map(([, options]) => JSON.parse(options.body))
}

beforeEach(() => {
  previousTimezone = window.timezone
  previousCsrf = window.csrf_token
  window.timezone = { system: 'Europe/Moscow' }
  window.csrf_token = 'synthetic-csrf'
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-14T09:00:00Z'))
  remote = null
  handlers = {}
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url, options) => {
      const action = url.split('.').at(-1)
      const value = handlers[action]
        ? await handlers[action](JSON.parse(options.body))
        : remote
      return value?.json
        ? value
        : response(
            action === 'get_channel_import'
              ? { ok: true, import: value }
              : value,
          )
    }),
  )
})

afterEach(() => {
  for (const entry of mounted) {
    if (!entry.unmounted) entry.app.unmount()
    entry.root.remove()
  }
  mounted = []
  window.timezone = previousTimezone
  window.csrf_token = previousCsrf
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

async function settle() {
  for (let index = 0; index < 20; index++) await Promise.resolve()
  await nextTick()
}

async function mount(overrides = {}) {
  const props = reactive({
    channel: channel(),
    enabled: true,
    disabled: false,
    ...overrides,
  })
  const root = document.createElement('div')
  const busy = vi.fn()
  document.body.appendChild(root)
  const app = createApp({
    render: () => h(WazzupHistoryImport, { ...props, onBusy: busy }),
  })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  const entry = { app, root, props, busy }
  mounted.push(entry)
  await settle()
  entry.state = app._instance.subTree.component.setupState
  return entry
}

function button(root, label) {
  return [...root.querySelectorAll('button')].find(
    (item) => item.textContent.trim() === label,
  )
}

async function click(root, label) {
  expect(button(root, label)).toBeTruthy()
  button(root, label).click()
  await settle()
}

async function edit(root, label, value) {
  const input = root.querySelector(`[data-label="${label}"]`)
  expect(input).toBeTruthy()
  input.value = value
  input.dispatchEvent(new Event('input', { bubbles: true }))
  await settle()
}

async function selectPeriod(root, from = '2026-11-02', through = '2026-11-03') {
  await edit(root, 'From date', from)
  await edit(root, 'Through date', through)
}

async function toggle(root, selector) {
  root.querySelector(selector).click()
  await settle()
}

async function poll() {
  await vi.advanceTimersByTimeAsync(5000)
  await settle()
}

describe('history RPC and public DTO contract', () => {
  it.each([
    ['get_channel_import', { channel: 'PARTNER-1' }],
    ['get_import_status', { import_id: 'IMPORT-1' }],
    [
      'start_import',
      {
        channel: 'PARTNER-1',
        start_at: '2026-11-01T00:00:00Z',
        end_at: '2026-11-02T00:00:00Z',
        create_conversations: true,
        create_leads: false,
      },
    ],
    ['start_processing', { import_id: 'IMPORT-1', expected_generation: 17 }],
  ])(
    'calls the real %s RPC with its exact arguments and no transport retries',
    async (action, args) => {
      remote = dto()
      expect(await callWazzupHistory(action, args)).toMatchObject({
        import_id: 'IMPORT-1',
        generation: 1,
      })
      expect(fetch).toHaveBeenCalledExactlyOnceWith(
        `/api/method/${API}.${action}`,
        {
          method: 'POST',
          credentials: 'same-origin',
          redirect: 'error',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json; charset=utf-8',
            'X-Frappe-Site-Name': window.location.hostname,
            'X-Frappe-CSRF-Token': 'synthetic-csrf',
          },
          body: JSON.stringify(args),
        },
      )
    },
  )

  it('accepts a null channel lookup and omits an unresolved CSRF placeholder', async () => {
    window.csrf_token = '{{ csrf_token }}'
    expect(
      await callWazzupHistory('get_channel_import', { channel: 'PARTNER-1' }),
    ).toBeNull()
    expect(fetch.mock.calls[0][1].headers).not.toHaveProperty(
      'X-Frappe-CSRF-Token',
    )
  })

  it('rejects an ambiguous empty lookup response instead of enabling a new import', async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => ({}) })
    await expect(
      callWazzupHistory('get_channel_import', { channel: 'PARTNER-1' }),
    ).rejects.toThrow('History import is temporarily unavailable.')
    fetch.mockResolvedValue(response(null))
    await expect(
      callWazzupHistory('get_channel_import', { channel: 'PARTNER-1' }),
    ).rejects.toThrow('History import is temporarily unavailable.')
  })

  it.each([
    ['arbitrary_method', {}],
    ['configure_import_policy', {}],
    ['start_processing', { import_id: 'IMPORT-1' }],
    ['start_import', { channel: 'PARTNER-1' }],
    [
      'get_import_status',
      { import_id: 'IMPORT-1', private_url: 'synthetic-private' },
    ],
  ])(
    'rejects unsupported %s requests before sending HTTP',
    async (action, args) => {
      await expect(callWazzupHistory(action, args)).rejects.toThrow(
        'History import is temporarily unavailable.',
      )
      expect(fetch).not.toHaveBeenCalled()
    },
  )

  it.each([
    [403, 'You are not permitted to access this history import.'],
    [404, 'History import or channel was not found.'],
    [417, 'History import parameters or state are invalid.'],
    [500, 'History import is temporarily unavailable.'],
  ])(
    'renders a fixed error for HTTP %s and discards private exception content',
    async (status, message) => {
      fetch.mockResolvedValue(
        response('synthetic-private-url', status, {
          exc: 'synthetic-private-exception',
          _server_messages: 'synthetic-private-message',
        }),
      )
      const logs = ['log', 'warn', 'error', 'groupCollapsed'].map((name) =>
        vi.spyOn(console, name),
      )
      await expect(
        callWazzupHistory('get_import_status', { import_id: 'IMPORT-1' }),
      ).rejects.toThrow(message)
      expect(fetch).toHaveBeenCalledTimes(1)
      logs.forEach((log) => expect(log).not.toHaveBeenCalled())
    },
  )

  it.each([
    { generation: undefined },
    { generation: -1 },
    { channel: 'OTHER' },
    { import_id: 'OTHER' },
    { active: false },
    { policy: { create_conversations: 'false' } },
    { policy: { create_leads: undefined } },
    { progress: progress({ counts: counts({ created: -1 }) }) },
    { result: { ...result(), outcome: 'invented' } },
  ])(
    'rejects malformed, foreign or unsupported DTO fields %j',
    async (overrides) => {
      remote = dto(overrides)
      await expect(
        callWazzupHistory(
          overrides.channel ? 'get_channel_import' : 'get_import_status',
          overrides.channel
            ? { channel: 'PARTNER-1' }
            : { import_id: 'IMPORT-1' },
        ),
      ).rejects.toThrow('History import is temporarily unavailable.')
    },
  )

  it('does not expose unrecognized content or raw error messages in normalized DTOs', () => {
    const normalized = normalizeHistoryImport(
      dto({
        raw_csv: 'synthetic-private-text',
        url: 'https://synthetic.invalid/private',
        error: { code: 'batch_failed', message: 'synthetic-private-text' },
        progress: progress({
          counts: { ...counts(), raw_message: 'synthetic-private-text' },
        }),
      }),
    )
    expect(JSON.stringify(normalized)).not.toContain('synthetic-private')
    expect(normalized.error).toBe(
      'History processing stopped after the last saved batch.',
    )
  })

  it('does not retry a network failure or accept HTTP-success exceptions', async () => {
    fetch.mockRejectedValueOnce(new Error('synthetic-private-transport'))
    await expect(
      callWazzupHistory('get_channel_import', { channel: 'PARTNER-1' }),
    ).rejects.toThrow('History import is temporarily unavailable.')
    expect(fetch).toHaveBeenCalledTimes(1)
    fetch.mockResolvedValueOnce(
      response(dto(), 200, { exc: 'synthetic-private-exception' }),
    )
    await expect(
      callWazzupHistory('get_channel_import', { channel: 'PARTNER-1' }),
    ).rejects.toThrow('History import is temporarily unavailable.')
  })
})

describe('history message period and explicit Lead approval', () => {
  it('renders the required Russian warning, controls, progress and errors from the CRM runtime dictionary', async () => {
    const source = readFileSync(
      resolve(process.cwd(), '../crm/translations.py'),
      'utf8',
    )
    const dictionary = Object.fromEntries(
      [
        ...source.matchAll(
          /^\s*("(?:[^"\\]|\\.)*"):\s*("(?:[^"\\]|\\.)*"),?$/gm,
        ),
      ].map((match) => [JSON.parse(match[1]), JSON.parse(match[2])]),
    )
    const translate = globalThis.__
    vi.stubGlobal('__', (message, args) =>
      translate(dictionary[message] || message, args),
    )
    const { root } = await mount()
    expect(root.textContent).toContain('Wazzup может вернуть не всю историю.')
    expect(root.textContent).toContain('Только существующие переписки')
    expect(root.textContent).toContain('Существующие и новые контакты')
    expect(button(root, 'Запустить импорт истории')).toBeTruthy()
    remote = ready()
    await click(root, 'Обновить статус')
    expect(root.textContent).toContain('Обработка истории требует внимания')
    expect(root.textContent).toContain('Загружено сообщений: 2')
    expect(root.textContent).toContain(
      'Обработка истории остановилась после последней сохранённой порции сообщений.',
    )
    expect(button(root, 'Возобновить сохранённую обработку')).toBeTruthy()
  })

  it('uses inclusive calendar dates in the CRM timezone and starts without a Lead opt-in', () => {
    expect(newHistoryImportForm()).toEqual({
      from: '',
      through: '2026-11-14',
      mode: 'existing',
    })
    expect(historyImportPeriod('2026-11-02', '2026-11-03')).toEqual({
      start_at: '2026-11-01T21:00:00.000Z',
      end_at: '2026-11-03T20:59:59.999Z',
    })
  })

  it('maps only the two explicit new-import modes and rejects an invented mode', () => {
    expect(historyImportPolicy('existing')).toEqual({
      create_conversations: false,
      create_leads: false,
    })
    expect(historyImportPolicy('contacts')).toEqual({
      create_conversations: true,
      create_leads: true,
    })
    expect(() => historyImportPolicy('other')).toThrow()
  })

  it('formats the saved period and a repeat-import draft in the site timezone', () => {
    window.timezone = { system: 'Asia/Kolkata' }
    const previous = dto({
      start_at: '2026-11-06T18:30:00Z',
      end_at: '2026-11-07T18:29:59.999Z',
      policy: { create_leads: true },
    })
    expect(formatHistoryImportTime(previous.start_at)).toBe('07.11.2026')
    expect(formatHistoryImportTime(previous.end_at)).toBe('07.11.2026')
    expect(newHistoryImportForm(previous)).toEqual({
      from: '2026-11-07',
      through: '2026-11-07',
      mode: 'existing',
    })
  })

  it.each([
    [false, false, 'Existing conversations only'],
    [true, false, 'Conversations without new leads'],
    [true, true, 'Existing and new contacts'],
    [false, true, 'New leads without new conversations'],
  ])(
    'preserves saved policy flags %s/%s in the DTO and label',
    (conversations, leads, label) => {
      const policy = {
        create_conversations: conversations,
        create_leads: leads,
      }
      expect(normalizeHistoryImport(dto({ policy })).policy).toEqual(policy)
      expect(historyImportPolicyLabel(policy)).toBe(label)
    },
  )

  it.each([
    ['', '2026-11-01'],
    ['2026-11-01', ''],
    ['2026-11-03', '2026-11-01'],
    ['2026-02-29', '2026-03-01'],
    ['2026-11-31', '2026-12-01'],
    ['01.11.2026', '2026-11-02'],
  ])('rejects invalid bounds %s / %s', (from, through) => {
    expect(() => historyImportPeriod(from, through)).toThrow(
      'Select an ordered date range for history import.',
    )
  })

  it.each([
    ['2026-03-08', 23],
    ['2026-11-01', 25],
  ])('uses the correct DST length for %s', (date, hours) => {
    const period = historyImportPeriod(date, date, 'America/New_York')
    expect(Date.parse(period.end_at) - Date.parse(period.start_at) + 1).toBe(
      hours * 3600000,
    )
  })

  it.each(['whatsapp', 'telegram', 'max', 'viber'])(
    'offers import for the saved %s Partner channel and performs only an initial lookup',
    async (platform) => {
      const { root } = await mount({ channel: channel({ platform }) })
      expect(root.textContent).toContain('Wazzup history import')
      expect(root.textContent).toContain(
        'Wazzup may return an incomplete history.',
      )
      expect(
        root.querySelector('[data-wazzup-history-mode="existing"]').checked,
      ).toBe(true)
      expect(
        root.querySelector('[data-wazzup-history-mode="contacts"]').checked,
      ).toBe(false)
      expect(requests('get_channel_import')).toEqual([{ channel: 'PARTNER-1' }])
      expect(requests('start_import')).toEqual([])
      expect(requests('start_processing')).toEqual([])
    },
  )

  it.each([
    channel({ platform: 'instagram' }),
    channel({ wazzup_api_mode: 'user_api_v3' }),
    channel({ provider: 'max_direct' }),
    null,
  ])(
    'does not expose the Partner import for unsupported channels',
    async (saved) => {
      const { root } = await mount({ channel: saved })
      expect(
        root.querySelector('[data-testid="wazzup-history-import"]'),
      ).toBeNull()
      expect(fetch).not.toHaveBeenCalled()
    },
  )

  it('validates date inputs without sending a start request', async () => {
    const { root } = await mount()
    await click(root, 'Start history import')
    expect(root.textContent).toContain(
      'Select an ordered date range for history import.',
    )
    await selectPeriod(root, '2026-11-03', '2026-11-01')
    await click(root, 'Start history import')
    expect(requests('start_import')).toEqual([])
  })

  it.each([false, true])(
    'sends the exact paired policy for the explicitly selected contacts mode=%s',
    async (optIn) => {
      const { root } = await mount()
      await selectPeriod(root)
      if (optIn) await toggle(root, '[data-wazzup-history-mode="contacts"]')
      handlers.start_import = () =>
        (remote = dto({
          policy: { create_conversations: optIn, create_leads: optIn },
        }))
      await click(root, 'Start history import')
      expect(requests('start_import')).toEqual([
        {
          channel: 'PARTNER-1',
          start_at: '2026-11-01T21:00:00.000Z',
          end_at: '2026-11-03T20:59:59.999Z',
          create_conversations: optIn,
          create_leads: optIn,
        },
      ])
      expect(root.querySelector('form')).toBeNull()
      expect(
        root.querySelector('[data-testid="wazzup-history-policy"]').textContent,
      ).toContain(
        optIn ? 'Existing and new contacts' : 'Existing conversations only',
      )
    },
  )

  it('clears Lead approval when returning to existing conversations only', async () => {
    const { root } = await mount()
    await toggle(root, '[data-wazzup-history-mode="contacts"]')
    await toggle(root, '[data-wazzup-history-mode="existing"]')
    expect(
      root.querySelector('[data-wazzup-history-mode="contacts"]').checked,
    ).toBe(false)
    expect(root.querySelectorAll('input[type="radio"]')).toHaveLength(2)
    expect(root.querySelector('input[type="checkbox"]')).toBeNull()
    await selectPeriod(root)
    handlers.start_import = () =>
      dto({ policy: { create_conversations: false } })
    await click(root, 'Start history import')
    expect(requests('start_import')[0]).toMatchObject({
      create_conversations: false,
      create_leads: false,
    })
  })

  it.each([
    { disabled: true },
    { enabled: false },
    { channel: channel({ enabled: false }) },
    { channel: channel({ state: 'unchecked', wazzup_status: 'unauthorized' }) },
  ])(
    'keeps status readable while unavailable settings disable mutations',
    async (props) => {
      const { root } = await mount(props)
      expect(requests('get_channel_import')).toHaveLength(1)
      expect(button(root, 'Start history import').disabled).toBe(true)
      expect(root.textContent).toContain(
        'Save settings and connect an enabled channel',
      )
    },
  )
})

describe('history polling, recovery and saved results', () => {
  it('prevents double clicks, form submission and direct repeated handlers while start is pending', async () => {
    const pending = deferred()
    handlers.start_import = () => pending.promise
    const { root, state, busy } = await mount()
    await selectPeriod(root)
    const first = state.start()
    state.start()
    root
      .querySelector('form')
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await click(root, 'Start history import')
    expect(requests('start_import')).toHaveLength(1)
    expect(button(root, 'Start history import').disabled).toBe(true)
    expect(busy).toHaveBeenLastCalledWith(true)
    pending.resolve(dto())
    await first
    await settle()
    expect(busy).toHaveBeenLastCalledWith(false)
  })

  it('shows the actual saved scope when the backend returns an existing active import', async () => {
    handlers.start_import = () =>
      dto({
        duplicate: true,
        start_at: '2026-10-01T00:00:00Z',
        policy: { create_conversations: false },
      })
    const { root } = await mount()
    await selectPeriod(root)
    await toggle(root, '[data-wazzup-history-mode="contacts"]')
    await click(root, 'Start history import')
    expect(root.textContent).toContain(
      'An import already exists for this channel.',
    )
    expect(root.textContent).toContain('01.10.2026')
    expect(
      root.querySelector('[data-testid="wazzup-history-policy"]').textContent,
    ).toContain('Existing conversations only')
    expect(root.querySelector('form')).toBeNull()
    expect(requests('start_import')).toHaveLength(1)
  })

  it('recovers the current import after remount without browser storage or mutations', async () => {
    remote = ready()
    const storage = vi.spyOn(Storage.prototype, 'setItem')
    const first = await mount()
    expect(first.root.textContent).toContain(
      'History processing needs attention',
    )
    first.app.unmount()
    first.unmounted = true
    remote = ready({ generation: 21 })
    const second = await mount()
    expect(second.state.status.generation).toBe(21)
    expect(second.root.textContent).toContain('CSV rows processed: 3 of 6')
    expect(requests('get_channel_import')).toHaveLength(2)
    expect(requests('start_import')).toEqual([])
    expect(requests('start_processing')).toEqual([])
    expect(storage).not.toHaveBeenCalled()
  })

  it.each([
    ['succeeded', 'History import completed'],
    ['partial', 'History import partially completed'],
    ['failed', 'History import failed'],
  ])(
    'renders the saved %s result and stops polling',
    async (outcome, label) => {
      remote = dto({
        state: outcome === 'failed' ? 'failed' : 'completed',
        result: result(outcome),
      })
      const { root } = await mount()
      expect(root.textContent).toContain(label)
      expect(
        root.querySelector('[data-testid="wazzup-history-counts"]'),
      ).not.toBeNull()
      if (outcome === 'partial') {
        expect(root.textContent).toContain('Messages imported: 3')
        expect(root.textContent).toContain('Messages without a conversation: 1')
        expect(root.textContent).toContain('Messages awaiting resolution: 1')
        expect(root.textContent).toContain('Rejected messages: 1')
        expect(root.textContent).toContain('Some messages were not imported.')
      }
      if (outcome === 'failed')
        expect(root.textContent).toContain(
          'The history CSV could not be validated.',
        )
      await poll()
      expect(fetch).toHaveBeenCalledTimes(1)
      expect(button(root, 'Resume saved processing')).toBeUndefined()
      const first = mounted.at(-1)
      first.app.unmount()
      first.unmounted = true
      const restored = await mount()
      expect(restored.root.textContent).toContain(label)
      if (outcome === 'partial') {
        expect(restored.root.textContent).toContain(
          'Messages awaiting resolution: 1',
        )
        expect(restored.root.textContent).toContain(
          'Messages without a conversation: 1',
        )
      }
      expect(restored.root.querySelector('form')).toBeNull()
      expect(requests('get_channel_import')).toHaveLength(2)
      expect(requests('start_import')).toEqual([])
      expect(requests('start_processing')).toEqual([])
    },
  )

  it('rejects a foreign-channel status response and retains the last confirmed import', async () => {
    remote = dto()
    const { root, state } = await mount()
    handlers.get_import_status = () =>
      dto({
        channel: 'FOREIGN-CHANNEL',
        state: 'completed',
        result: result('partial'),
      })
    await poll()
    expect(state.status.channel).toBe('PARTNER-1')
    expect(root.textContent).toContain('History export queued')
    expect(
      root.querySelector('[data-testid="wazzup-history-refresh-error"]'),
    ).not.toBeNull()
    expect(root.textContent).not.toContain('History import partially completed')
  })

  it('does not invent counters for an export failure without a final summary', async () => {
    remote = dto({
      state: 'failed',
      error: { code: 'provider_rejected', message: 'synthetic-private' },
    })
    const { root } = await mount()
    expect(root.textContent).toContain('History import failed')
    expect(root.textContent).toContain(
      'The provider rejected the export request.',
    )
    expect(
      root.querySelector('[data-testid="wazzup-history-counts"]'),
    ).toBeNull()
    expect(root.textContent).not.toContain('synthetic-private')
  })

  it('follows export, download, CSV and conversation phases with only confirmed counters', async () => {
    remote = dto()
    const { root } = await mount()
    expect(root.textContent).toContain('History export queued')
    expect(
      root.querySelector('[data-testid="wazzup-history-counts"]'),
    ).toBeNull()
    const phases = [
      [
        dto({ state: 'requesting_export', generation: 2 }),
        'Requesting history export',
      ],
      [
        dto({ state: 'waiting_export', generation: 3 }),
        'Exporting history in Wazzup',
      ],
      [
        dto({
          state: 'export_ready',
          file_status: 'downloading',
          generation: 4,
        }),
        'Downloading history export',
      ],
      [
        ready({ processing: { phase: 'validate' }, progress: null }),
        'Validating history CSV',
      ],
      [
        ready({ generation: 18, processing: { phase: 'existing' } }),
        'Importing messages into existing conversations',
      ],
      [
        ready({
          generation: 19,
          processing: { phase: 'replay' },
          progress: progress({
            processed: 6,
            counts: counts({
              created: 4,
              duplicate: 1,
              unknown_conversation: 1,
            }),
            replay_processed: 2,
            replay_total: 3,
            conversations_created: 1,
          }),
        }),
        'Creating missing conversations and importing messages',
      ],
      [
        ready({ generation: 20, processing: { phase: 'awaiting_followup' } }),
        'Finishing history import',
      ],
      [
        dto({ state: 'completed', generation: 21, result: result() }),
        'History import completed',
      ],
    ]
    for (const [next, label] of phases) {
      remote = next
      await poll()
      expect(
        root.querySelector('[data-testid="wazzup-history-phase"]').textContent,
      ).toContain(label)
      if (next.processing.phase === 'replay') {
        expect(root.textContent).toContain('Deferred rows processed: 2 of 3')
        expect(root.textContent).toContain('Conversations created: 1')
      }
    }
    expect(requests('get_import_status')).toHaveLength(phases.length)
    expect(requests('start_import')).toEqual([])
    expect(requests('start_processing')).toEqual([])
    await poll()
    expect(requests('get_import_status')).toHaveLength(phases.length)
  })

  it('coalesces refreshes and waits for a slow read before scheduling the next poll', async () => {
    remote = dto()
    const { root, state } = await mount()
    const pending = deferred()
    handlers.get_import_status = () => pending.promise
    await poll()
    state.refresh()
    state.refresh()
    await click(root, 'Refresh import status')
    await vi.advanceTimersByTimeAsync(30000)
    expect(requests('get_import_status')).toHaveLength(1)
    pending.resolve(dto({ state: 'waiting_export', generation: 2 }))
    await settle()
    await vi.advanceTimersByTimeAsync(4999)
    expect(requests('get_import_status')).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(requests('get_import_status')).toHaveLength(2)
  })

  it('keeps confirmed state and counters after a read failure and recovers on the next poll', async () => {
    remote = ready({ processing: { phase: 'existing' } })
    const { root } = await mount()
    handlers.get_import_status = () => {
      throw new Error('synthetic-private')
    }
    await poll()
    expect(root.textContent).toContain(
      'Could not refresh the Wazzup history import status.',
    )
    expect(root.textContent).toContain('Messages imported: 2')
    expect(root.textContent).not.toContain('synthetic-private')
    handlers.get_import_status = () =>
      dto({ generation: 19, state: 'completed', result: result('partial') })
    await poll()
    expect(
      root.querySelector('[data-testid="wazzup-history-refresh-error"]'),
    ).toBeNull()
    expect(root.textContent).toContain('History import partially completed')
  })

  it('keeps launch disabled until the initial channel lookup has succeeded', async () => {
    handlers.get_channel_import = () => {
      throw new Error('synthetic-private')
    }
    const { root } = await mount()
    expect(button(root, 'Start history import').disabled).toBe(true)
    handlers.get_channel_import = () => null
    await click(root, 'Refresh import status')
    expect(button(root, 'Start history import').disabled).toBe(false)
    expect(
      root.querySelector('[data-testid="wazzup-history-refresh-error"]'),
    ).toBeNull()
  })

  it('ignores a response from an older server generation', async () => {
    remote = ready({ generation: 19 })
    const { root, state } = await mount()
    remote = dto({ generation: 18 })
    await poll()
    expect(state.status.generation).toBe(19)
    expect(root.textContent).toContain('Messages imported: 2')
  })

  it('does not reset the import when connection polling replaces the same channel object', async () => {
    remote = dto()
    const { props } = await mount()
    props.channel = channel({ custom_display_name: 'Updated name' })
    await settle()
    expect(requests('get_channel_import')).toHaveLength(1)
    await poll()
    expect(requests('get_import_status')).toHaveLength(1)
  })

  it('discards the old channel response after switching channels and resets local opt-ins', async () => {
    const pending = deferred()
    remote = dto()
    const { props, root, state } = await mount()
    handlers.get_import_status = () => pending.promise
    await poll()
    handlers.get_channel_import = () =>
      dto({ channel: 'PARTNER-2', import_id: 'IMPORT-2' })
    props.channel = channel({ name: 'PARTNER-2' })
    await settle()
    pending.resolve(dto({ state: 'completed', result: result() }))
    await settle()
    expect(state.status.channel).toBe('PARTNER-2')
    expect(state.status.import_id).toBe('IMPORT-2')
    expect(root.textContent).toContain('History export queued')
    expect(root.textContent).not.toContain('History import completed')
  })

  it('discards a late start response after the channel changes', async () => {
    const pending = deferred()
    handlers.start_import = () => pending.promise
    const { root, props, state, busy } = await mount()
    await selectPeriod(root)
    const starting = state.start()
    props.channel = channel({ name: 'PARTNER-2' })
    await settle()
    pending.resolve(dto())
    await starting
    await settle()
    expect(state.status).toBeNull()
    expect(busy).toHaveBeenLastCalledWith(false)
    expect(button(root, 'Start history import').disabled).toBe(false)
    expect(
      root.querySelector('[data-wazzup-history-mode="contacts"]').checked,
    ).toBe(false)
  })

  it('ignores pending reads after unmount and clears every polling timer', async () => {
    remote = dto()
    const entry = await mount()
    const pending = deferred()
    handlers.get_import_status = () => pending.promise
    await poll()
    entry.app.unmount()
    entry.unmounted = true
    pending.resolve(dto({ state: 'completed', result: result() }))
    await settle()
    await vi.advanceTimersByTimeAsync(30000)
    expect(requests('get_import_status')).toHaveLength(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('ignores pending mutations after unmount and restores their result on the next mount', async () => {
    const pending = deferred()
    handlers.start_import = () => pending.promise
    const first = await mount()
    await selectPeriod(first.root)
    const starting = first.state.start()
    first.app.unmount()
    first.unmounted = true
    remote = dto({ state: 'export_unknown' })
    pending.resolve(remote)
    await starting
    await settle()
    const second = await mount()
    expect(second.root.textContent).toContain('History export result unknown')
    expect(requests('start_import')).toHaveLength(1)
    expect(requests('start_processing')).toEqual([])
  })

  it('never automatically repeats an uncertain start or offers export retry controls', async () => {
    handlers.start_import = () => {
      throw new Error('synthetic-private')
    }
    const { root, state } = await mount()
    await selectPeriod(root)
    await click(root, 'Start history import')
    expect(root.textContent).toContain(
      'The start request could not be confirmed.',
    )
    expect(root.textContent).not.toContain('synthetic-private')
    state.start()
    expect(requests('start_import')).toHaveLength(1)
    remote = dto({ state: 'export_unknown' })
    await poll()
    await poll()
    expect(root.textContent).toContain(
      'The export request will not be repeated automatically.',
    )
    expect(button(root, 'Start history import')).toBeUndefined()
    expect(button(root, 'Resume saved processing')).toBeUndefined()
    expect(requests('start_import')).toHaveLength(1)
    expect(requests('start_processing')).toEqual([])
  })

  it('requires a separate new-import action and resets a previous Lead opt-in', async () => {
    remote = dto({
      state: 'completed',
      result: result(),
      policy: { create_leads: true },
    })
    const { root } = await mount()
    expect(root.querySelector('form')).toBeNull()
    await click(root, 'New history import')
    expect(root.querySelector('[data-label="From date"]').value).toBe(
      '2026-11-02',
    )
    expect(root.querySelector('[data-label="Through date"]').value).toBe(
      '2026-11-03',
    )
    expect(
      root.querySelector('[data-wazzup-history-mode="contacts"]').checked,
    ).toBe(false)
    expect(requests('start_import')).toEqual([])
    expect(
      root.querySelector('[data-testid="wazzup-history-period"]'),
    ).toBeNull()
    await click(root, 'Cancel')
    expect(root.querySelector('form')).toBeNull()
    expect(
      root.querySelector('[data-testid="wazzup-history-policy"]').textContent,
    ).toContain('Existing and new contacts')
    await click(root, 'New history import')
    handlers.start_import = () =>
      dto({
        import_id: 'IMPORT-2',
        policy: { create_conversations: false, create_leads: false },
      })
    await click(root, 'Start history import')
    expect(requests('start_import')[0]).toEqual({
      channel: 'PARTNER-1',
      start_at: '2026-11-01T21:00:00.000Z',
      end_at: '2026-11-03T20:59:59.999Z',
      create_conversations: false,
      create_leads: false,
    })
  })

  it.each(['queued', 'completed'])(
    'restores a legacy conversation-only %s import without changing its policy',
    async (state) => {
      remote = dto({ state, result: state === 'completed' ? result() : null })
      const { root } = await mount()
      expect(
        root.querySelector('[data-testid="wazzup-history-policy"]').textContent,
      ).toContain('Conversations without new leads')
      expect(root.querySelector('form')).toBeNull()
      await poll()
      expect(requests('start_import')).toEqual([])
      expect(requests('start_processing')).toEqual([])
      if (state === 'completed') {
        await click(root, 'New history import')
        expect(
          root.querySelector('[data-wazzup-history-mode="existing"]').checked,
        ).toBe(true)
        expect(remote.policy).toEqual({
          create_conversations: true,
          create_leads: false,
        })
      }
    },
  )

  it('keeps the successful result compact while preserving nonzero duplicate and unresolved counts', async () => {
    remote = dto({
      state: 'completed',
      result: { ...result(), conversations_created: 0 },
    })
    const { root } = await mount()
    const counterText = root.querySelector(
      '[data-testid="wazzup-history-counts"]',
    ).textContent
    expect(counterText).toContain('Messages imported: 6')
    for (const label of [
      'CSV rows',
      'Duplicate messages',
      'Messages awaiting resolution',
      'Conversations created',
      'Leads created',
    ]) {
      expect(counterText).not.toContain(label)
    }
    remote = dto({
      state: 'completed',
      generation: 2,
      result: {
        ...result('partial'),
        counts: counts({ duplicate: 2, unresolved: 4 }),
        conversations_created: 0,
      },
    })
    await click(root, 'Refresh import status')
    expect(root.textContent).toContain('Duplicate messages: 2')
    expect(root.textContent).toContain('Messages awaiting resolution: 4')
    expect(root.textContent).toContain('Messages imported: 0')
  })
})

describe('explicit saved-processing resume', () => {
  it.each([
    { enabled: false, phase: null, error: null },
    { enabled: true, phase: 'blocked', error: 'batch_failed' },
  ])(
    'resumes only after an explicit click using the current generation',
    async (processing) => {
      remote = ready({ processing })
      const pending = deferred()
      handlers.start_processing = () => pending.promise
      const { root, state } = await mount()
      expect(requests('start_processing')).toEqual([])
      await click(root, 'Resume saved processing')
      state.resume()
      expect(requests('start_processing')).toEqual([
        { import_id: 'IMPORT-1', expected_generation: 17 },
      ])
      expect(requests('start_import')).toEqual([])
      pending.resolve(
        ready({ generation: 18, processing: { phase: 'validate' } }),
      )
      await settle()
      expect(root.textContent).toContain('Validating history CSV')
      expect(button(root, 'Resume saved processing')).toBeUndefined()
    },
  )

  it.each([
    dto({ state: 'export_unknown' }),
    dto({ state: 'failed' }),
    dto({ state: 'completed', result: result('partial') }),
    ready({ processing: { phase: 'existing' } }),
    ready({ processing: { phase: 'blocked', error: 'invalid_csv' } }),
    ready({ file: { format: 'zip' } }),
    ready({ file_status: 'failed' }),
  ])(
    'does not offer resume for unavailable, fatal, active or finished processing',
    async (status) => {
      remote = status
      const { root, state } = await mount()
      expect(canResumeHistoryImport(state.status)).toBe(false)
      expect(button(root, 'Resume saved processing')).toBeUndefined()
      state.resume()
      expect(requests('start_processing')).toEqual([])
    },
  )

  it('refreshes the generation after a resume failure and never retries it automatically', async () => {
    remote = ready()
    handlers.start_processing = () => {
      throw new Error('synthetic-private')
    }
    const { root } = await mount()
    await click(root, 'Resume saved processing')
    expect(root.textContent).toContain('Could not resume saved processing.')
    remote = ready({ generation: 22 })
    await poll()
    expect(requests('start_processing')).toHaveLength(1)
    handlers.start_processing = () =>
      ready({ generation: 23, processing: { phase: 'validate' } })
    await click(root, 'Resume saved processing')
    expect(requests('start_processing')).toEqual([
      { import_id: 'IMPORT-1', expected_generation: 17 },
      { import_id: 'IMPORT-1', expected_generation: 22 },
    ])
  })
})
