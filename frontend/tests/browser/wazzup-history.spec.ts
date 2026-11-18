import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'

// The real settings dialog and calendar; every RPC is intercepted locally.
const translations = Object.fromEntries(
  [
    ...readFileSync(
      new URL('../../../crm/translations.py', import.meta.url),
      'utf8',
    ).matchAll(/^\s*("(?:[^"\\]|\\.)*"):\s*("(?:[^"\\]|\\.)*"),?$/gm),
  ].map((match) => [JSON.parse(match[1]), JSON.parse(match[2])]),
)
test.use({ locale: 'ru-RU' })

const channel = {
  name: 'history-fixture',
  provider: 'wazzup',
  platform: 'whatsapp',
  custom_display_name: 'Wazzup UI fixture',
  enabled: true,
  state: 'connected',
  wazzup_api_mode: 'partner_api_v2',
  wazzup_status: 'active',
}
const avito = {
  name: 'avito-fixture',
  provider: 'avito_direct',
  platform: 'avito',
  custom_display_name: 'Avito UI fixture',
  enabled: true,
  state: 'connected',
  avito_import_mode: 'period',
  avito_import_from_date: '2026-11-01',
  avito_import_to_date: '2026-11-07',
}
const counts = {
  created: 4,
  duplicate: 0,
  tombstone: 0,
  unknown_conversation: 0,
  unresolved: 0,
  rejected: 0,
}
function importDto(
  completed = false,
  contacts = false,
  conversations = contacts,
) {
  return {
    ok: true,
    import_id: 'UI-IMPORT',
    channel: channel.name,
    generation: completed ? 9 : 1,
    state: completed ? 'completed' : 'queued',
    active: !completed,
    start_at: '2026-11-06T18:30:00.000Z',
    end_at: '2026-11-07T18:29:59.999Z',
    policy: { create_conversations: conversations, create_leads: contacts },
    processing: {
      enabled: true,
      phase: completed ? 'awaiting_followup' : 'validate',
      error: null,
    },
    result: completed
      ? {
          version: 1,
          outcome: 'succeeded',
          reason: null,
          total: 4,
          processed: 4,
          counts,
          conversations_created: 0,
          leads_created: 0,
        }
      : null,
    progress: null,
    file_status: completed ? 'ready' : null,
    file: completed ? { format: 'csv' } : null,
    error: null,
  }
}

async function fixture(
  page: Page,
  initial: ReturnType<typeof importDto> | null = null,
) {
  let saved = initial
  const calls: { method: string; params: Record<string, unknown> }[] = []
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.addInitScript((dictionary) => {
    Object.assign(window, { __fixtureTranslations: dictionary })
  }, translations)
  await page.clock.setFixedTime(new Date('2026-11-16T09:00:00Z'))
  await page.route('**/api/method/**', async (route) => {
    const method = route.request().url().split('/api/method/')[1]
    const params = route.request().postDataJSON() || {}
    calls.push({ method, params })
    let message: unknown
    if (method === 'crm_messenger.api.settings.get_settings')
      message = {
        settings: {
          enabled: true,
          auto_create_lead: true,
          wazzup_partner_available: true,
        },
        channels: [channel, avito],
      }
    else if (method === 'crm_messenger.api.diagnostics.get_health_summary')
      message = { channels: [] }
    else if (method === 'crm_messenger.api.wazzup_partner.get_onboarding_state')
      message = { ok: true, channel, onboarding: { status: 'active' } }
    else if (
      method === 'crm_messenger.api.wazzup_partner_history.get_channel_import'
    )
      message = { ok: true, import: saved }
    else if (
      method === 'crm_messenger.api.wazzup_partner_history.get_import_status'
    )
      message = saved
    else if (method === 'crm_messenger.api.wazzup_partner_history.start_import')
      message = saved = {
        ...importDto(
          false,
          Boolean(params.create_leads),
          Boolean(params.create_conversations),
        ),
        start_at: String(params.start_at),
        end_at: String(params.end_at),
      }
    else if (
      method === 'crm_messenger.api.provider_sync.get_channel_sync_status'
    )
      message = { ok: true, status: 'idle', counts: {} }
    else throw new Error(`Unexpected fixture RPC: ${method}`)
    await route.fulfill({ json: { message } })
  })
  await page.goto(
    '/tests/browser/messenger-settings.html?timezone=Asia%2FKolkata',
  )
  await page.getByRole('button', { name: /Wazzup UI fixture/ }).click()
  await expect(page.getByTestId('wazzup-history-import')).toBeVisible()
  return {
    calls,
    errors,
    setSaved: (value: ReturnType<typeof importDto>) => {
      saved = value
    },
  }
}

const popup = (page: Page) =>
  page.locator('[data-slot="content-body"].w-56:visible')
const input = (page: Page, side: string) =>
  page.locator(`[data-wazzup-history-${side}] input`)
async function chooseNovember7(page: Page, side: string) {
  await input(page, side).click()
  const panel = popup(page)
  await expect(panel).toBeVisible()
  await expect(
    panel.getByRole('button', { name: 'cycle-calendar-view', exact: true }),
  ).toContainText('Ноябрь 2026')
  await panel.locator('[data-value="2026-11-07"]').click()
  await expect(input(page, side)).toHaveValue('07.11.2026')
  await expect(panel).toHaveCount(0)
}

for (const viewport of [
  { width: 1280, height: 900 },
  { width: 390, height: 844 },
  { width: 320, height: 720 },
]) {
  test(`Russian Wazzup calendar remains stable and usable at ${viewport.width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize(viewport)
    const { calls, errors } = await fixture(page)
    await expect(input(page, 'from')).toHaveAttribute(
      'placeholder',
      'ДД.ММ.ГГГГ',
    )
    await input(page, 'from').click()
    const panel = popup(page)
    const header = panel.getByRole('button', {
      name: 'cycle-calendar-view',
      exact: true,
    })
    const next = panel.getByRole('button', { name: 'next', exact: true })
    await expect(header).toContainText('Ноябрь 2026')
    const initial = await panel.boundingBox()
    const navigation = await next.boundingBox()
    for (const month of ['Октябрь', 'Сентябрь', 'Август']) {
      await panel.getByRole('button', { name: 'previous', exact: true }).click()
      await expect(header).toContainText(month)
      const box = await panel.boundingBox()
      const arrow = await next.boundingBox()
      expect(Math.abs(box!.width - initial!.width)).toBeLessThan(1)
      expect(Math.abs(box!.height - initial!.height)).toBeLessThan(1)
      expect(Math.abs(arrow!.x - navigation!.x)).toBeLessThan(1)
      expect(Math.abs(arrow!.y - navigation!.y)).toBeLessThan(1)
    }
    await expect(
      panel.locator('[aria-label="Сегодня"], [aria-label="Today"]'),
    ).toBeHidden()
    await expect(panel.getByRole('grid')).toContainText('Пн')
    const dialog = await page
      .getByRole('dialog', { name: 'Настройка канала', exact: true })
      .boundingBox()
    const box = await panel.boundingBox()
    expect(box!.x).toBeGreaterThanOrEqual(dialog!.x - 1)
    expect(box!.x + box!.width).toBeLessThanOrEqual(
      dialog!.x + dialog!.width + 1,
    )
    expect(box!.y).toBeGreaterThanOrEqual(0)
    expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height)
    await page.screenshot({ path: testInfo.outputPath('calendar.png') })
    for (let index = 0; index < 3; index++) await next.click()
    await panel.locator('[data-value="2026-11-07"]').click()
    await expect(input(page, 'from')).toHaveValue('07.11.2026')
    await chooseNovember7(page, 'through')
    await expect(
      page.locator('[data-wazzup-history-mode="existing"]'),
    ).toBeChecked()
    await page
      .getByRole('button', { name: 'Запустить импорт истории', exact: true })
      .click()
    await expect(page.getByTestId('wazzup-history-phase')).toContainText(
      'Экспорт истории в очереди',
    )
    const start = calls.filter((call) => call.method.endsWith('.start_import'))
    expect(start).toHaveLength(1)
    expect(start[0].params).toEqual({
      channel: channel.name,
      start_at: '2026-11-06T18:30:00.000Z',
      end_at: '2026-11-07T18:29:59.999Z',
      create_conversations: false,
      create_leads: false,
    })
    expect(
      await page
        .getByRole('dialog', { name: 'Настройка канала', exact: true })
        .evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBe(true)
    expect(errors).toEqual([])
  })
}

test('explicit new contacts, completion, reload and repeat import retain accurate dates and a safe default', async ({
  page,
}) => {
  const state = await fixture(page)
  await chooseNovember7(page, 'from')
  await chooseNovember7(page, 'through')
  await page.locator('[data-wazzup-history-mode="contacts"]').check()
  await page
    .getByRole('button', { name: 'Запустить импорт истории', exact: true })
    .click()
  await expect(page.getByTestId('wazzup-history-phase')).toBeVisible()
  expect(
    state.calls.find((call) => call.method.endsWith('.start_import'))!.params,
  ).toMatchObject({ create_conversations: true, create_leads: true })
  state.setSaved(importDto(true, true))
  await page
    .getByTestId('wazzup-history-import')
    .getByRole('button', { name: 'Обновить статус', exact: true })
    .click()
  await expect(page.getByTestId('wazzup-history-phase')).toContainText(
    'Импорт истории завершён',
  )
  await expect(page.getByTestId('wazzup-history-period')).toHaveText(
    '07.11.2026 — 07.11.2026',
  )
  await expect(page.getByTestId('wazzup-history-counts')).toHaveText(
    'Загружено сообщений: 4',
  )
  await page.reload()
  await page.getByRole('button', { name: /Wazzup UI fixture/ }).click()
  await expect(page.getByTestId('wazzup-history-policy')).toHaveText(
    'Существующие и новые контакты',
  )
  await page
    .getByRole('button', { name: 'Новый импорт истории', exact: true })
    .click()
  await expect(input(page, 'from')).toHaveValue('07.11.2026')
  await expect(input(page, 'through')).toHaveValue('07.11.2026')
  await expect(
    page.locator('[data-wazzup-history-mode="existing"]'),
  ).toBeChecked()
  expect(
    state.calls.filter((call) => call.method.endsWith('.start_import')),
  ).toHaveLength(1)
  expect(state.errors).toEqual([])
})

test('a saved conversation-only policy stays read-only and does not opt into new leads', async ({
  page,
}) => {
  const { calls, errors } = await fixture(page, importDto(true, false, true))
  await expect(page.getByTestId('wazzup-history-policy')).toHaveText(
    'Переписки без создания новых лидов',
  )
  await page
    .getByRole('button', { name: 'Новый импорт истории', exact: true })
    .click()
  await expect(
    page.locator('[data-wazzup-history-mode="existing"]'),
  ).toBeChecked()
  expect(
    calls.some(
      (call) =>
        call.method.endsWith('.start_import') ||
        call.method.endsWith('.start_processing'),
    ),
  ).toBe(false)
  expect(errors).toEqual([])
})

test('Avito reuses the same localized calendar without changing its date values or launching a scan', async ({
  page,
}) => {
  const { calls, errors } = await fixture(page)
  await input(page, 'from').click()
  const wazzupWidth = (await popup(page).boundingBox())!.width
  await popup(page).locator('[data-value="2026-11-07"]').click()
  await page
    .getByRole('dialog', { name: 'Настройка канала', exact: true })
    .getByRole('button', { name: 'Close', exact: true })
    .first()
    .click()
  await page.getByRole('button', { name: /Avito UI fixture/ }).click()
  const fields = page.locator('[data-avito-import-date] input')
  await expect(fields.nth(0)).toHaveValue('01.11.2026')
  await expect(fields.nth(1)).toHaveValue('07.11.2026')
  await fields.nth(1).click()
  const panel = popup(page)
  await expect(
    panel.getByRole('button', { name: 'cycle-calendar-view', exact: true }),
  ).toContainText('Ноябрь 2026')
  expect((await panel.boundingBox())!.width).toBe(wazzupWidth)
  await panel.getByRole('button', { name: 'previous', exact: true }).click()
  await expect(
    panel.getByRole('button', { name: 'cycle-calendar-view', exact: true }),
  ).toContainText('Октябрь 2026')
  await panel.getByRole('button', { name: 'next', exact: true }).click()
  await panel.locator('[data-value="2026-11-06"]').click()
  await expect(fields.nth(1)).toHaveValue('06.11.2026')
  expect(
    calls.some((call) =>
      /save_channel|scan_channel|start_import/.test(call.method),
    ),
  ).toBe(false)
  expect(errors).toEqual([])
})
