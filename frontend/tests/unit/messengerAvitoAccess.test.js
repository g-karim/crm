import { describe, expect, it } from 'vitest'
import {
  isAvitoChatRestricted,
  restrictedAvitoChats,
} from '@/utils/messengerAvitoAccess'

describe('Avito message access', () => {
  const channel = {
    name: 'AVITO',
    provider: 'avito_direct',
    capabilities: { messenger_access: 'subscription_required' },
  }
  const conversation = {
    name: 'CHAT',
    provider: 'avito_direct',
    channel: 'AVITO',
    external_chat_id: 'A'.repeat(26),
    channel_info: channel,
  }

  it('uses current channel state and preserves the exact chat link', () => {
    expect(restrictedAvitoChats([conversation])[0].externalUrl).toContain(
      `/channel/${'A'.repeat(26)}`,
    )
    expect(
      restrictedAvitoChats(
        [conversation],
        [{ ...channel, capabilities: { messenger_access: 'available' } }],
      ),
    ).toHaveLength(0)
    expect(isAvitoChatRestricted({ ...channel, provider: 'vk_direct' })).toBe(
      false,
    )
  })

  it('falls back to the Avito inbox for an invalid chat ID', () => {
    expect(
      restrictedAvitoChats([
        { ...conversation, external_chat_id: 'javascript:alert(1)' },
      ])[0].externalUrl,
    ).toBe('https://www.avito.ru/profile/messenger')
  })
})
