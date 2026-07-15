import { readFileSync } from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'

import { describe, expect, it, vi } from 'vitest'

const scriptPath = path.resolve(
  process.cwd(),
  '../../crm_messenger/crm_messenger/crm_messenger/doctype/messenger_channel/messenger_channel.js',
)

function loadChannelScript() {
  const context = {
    __: (value) => value,
    frappe: {
      ui: { form: { on: vi.fn() } },
      utils: {
        escape_html: (value) =>
          String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;'),
      },
    },
    window: { location: { href: 'https://crm.example.test' } },
  }
  vm.createContext(context)
  vm.runInContext(readFileSync(scriptPath, 'utf8'), context)
  return context
}

describe('Messenger Channel provider status popup', () => {
  it('uses only compact allowlisted data and never renders provider secrets', () => {
    const context = loadChannelScript()
    const result = {
      ok: true,
      state: 'connected',
      response: {
        registered: true,
        events_match: true,
        secret_key: 'vk-secret-value',
        webhook_token: 'webhook-secret-value',
        api_token: 'api-token-value',
        confirmation_code: 'confirmation-code-value',
        access_token: 'access-token-value',
        servers: [{ signed_url: 'https://upload.test/?signature=signed-secret' }],
      },
      integration: {
        state: 'connected',
        identity: { id: '10', name: 'Safe Community' },
        webhook: { registered: true, events_match: true },
        error: 'secret_key=legacy-popup-secret',
      },
    }

    const popupData = context.getProviderStatusPopupData(result, {})
    const popupMessage = context.formatProviderStatusMessage(result, {})
    const serialized = JSON.stringify(popupData)

    expect(Object.keys(popupData)).toEqual([
      'connected',
      'state',
      'webhook_registered',
      'events_match',
      'identity',
      'error',
    ])
    expect(popupData.identity).toBe('Safe Community · 10')
    expect(popupMessage).toContain('Подключён')
    expect(popupMessage).toContain('Webhook зарегистрирован')
    expect(popupMessage).toContain('События совпадают')
    expect(popupMessage).toContain(
      'Ошибка провайдера скрыта из соображений безопасности.',
    )
    for (const forbidden of [
      'vk-secret-value',
      'webhook-secret-value',
      'api-token-value',
      'confirmation-code-value',
      'access-token-value',
      'signed-secret',
      'legacy-popup-secret',
      'secret_key',
      'servers',
    ]) {
      expect(serialized).not.toContain(forbidden)
      expect(popupMessage).not.toContain(forbidden)
    }
  })
})
