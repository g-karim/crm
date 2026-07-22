import {
  getMessengerClientDisplayName,
  isProviderIdentifierLabel,
} from '@/utils/messengerClientIdentity'
import { describe, expect, it } from 'vitest'

describe('messenger client display identity', () => {
  it('never exposes a VK identifier as a client name', () => {
    expect(isProviderIdentifierLabel('560784880')).toBe(true)
    expect(isProviderIdentifierLabel('VK 560784880')).toBe(true)
    expect(
      getMessengerClientDisplayName({
        lead: { lead_name: '560784880' },
        conversation: { client_name: '560784880' },
      }),
    ).toBe('Клиент')
  })

  it('keeps the editable lead name authoritative across channels', () => {
    expect(
      getMessengerClientDisplayName({
        lead: { lead_name: 'Имя менеджера' },
        conversation: { client_name: 'Псевдоним VK' },
      }),
    ).toBe('Имя менеджера')
  })

  it('uses the provider profile only while the lead has an identifier placeholder', () => {
    expect(
      getMessengerClientDisplayName({
        lead: { lead_name: '560784880' },
        conversation: { client_name: 'Иван Петров' },
      }),
    ).toBe('Иван Петров')
  })
})
