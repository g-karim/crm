import {
  buildMessengerChannelOptions,
  getMessengerChannelType,
  getMessengerDeliveryLabel,
  getMessengerDeliveryState,
  getMessengerCapabilities,
  getMessengerPlatformLabel,
} from '@/utils/messengerChannels'

describe('messengerChannels', () => {
  it('normalizes known platform labels', () => {
    expect(
      getMessengerPlatformLabel({
        platform: 'avito',
      }),
    ).toBe('Avito')
    expect(
      getMessengerPlatformLabel({
        platform: 'whatsapp',
      }),
    ).toBe('WhatsApp')
    expect(
      getMessengerPlatformLabel({
        platform: 'telegram',
      }),
    ).toBe('Telegram')
    expect(getMessengerPlatformLabel({ platform: 'vk' })).toBe('VK')
    expect(getMessengerPlatformLabel({ platform: 'max' })).toBe('MAX')
  })

  it('humanizes custom platform labels', () => {
    expect(
      getMessengerPlatformLabel({
        platform: 'custom_platform',
      }),
    ).toBe('Custom Platform')
  })

  it('reads channel type from platform, channel_type, or chat_type', () => {
    expect(getMessengerChannelType({ platform: 'telegram' })).toBe('telegram')
    expect(getMessengerChannelType({ channel_type: 'avito' })).toBe('avito')
    expect(getMessengerChannelType({ chat_type: 'whatsapp' })).toBe('whatsapp')
  })

  it('builds unique select labels without technical names', () => {
    expect(
      buildMessengerChannelOptions([
        { name: 'ch-1', platform: 'avito' },
        { name: 'ch-2', platform: 'avito' },
        { name: 'ch-3', platform: 'whatsapp' },
      ]),
    ).toEqual([
      { label: 'Avito', value: 'ch-1' },
      { label: 'Avito 2', value: 'ch-2' },
      { label: 'WhatsApp', value: 'ch-3' },
    ])
  })

  it('maps delivery states only for outbound messages', () => {
    expect(
      getMessengerDeliveryState({
        direction: 'outbound',
        delivery_status: 'queued',
      }),
    ).toBe('queued')
    expect(
      getMessengerDeliveryState({
        direction: 'outbound',
        delivery_status: 'read',
      }),
    ).toBe('read')
    expect(
      getMessengerDeliveryState({
        direction: 'outbound',
        status: 'sent',
      }),
    ).toBe('sent')
    expect(
      getMessengerDeliveryState({
        direction: 'inbound',
        delivery_status: 'read',
      }),
    ).toBe('')
    expect(
      getMessengerDeliveryState({
        direction: 'outbound',
        delivery_status: 'unknown',
      }),
    ).toBe('unknown')
    expect(
      getMessengerDeliveryState({
        direction: 'outbound',
        delivery_status: 'provider_custom',
      }),
    ).toBe('')
  })

  it('returns delivery labels', () => {
    expect(
      getMessengerDeliveryLabel({
        direction: 'outbound',
        delivery_status: 'failed',
      }),
    ).toBe('Ошибка')
  })

  it('reads provider capabilities with safe defaults', () => {
    expect(getMessengerCapabilities({})).toEqual({
      can_start_conversation: true,
      requires_inbound: false,
      requires_phone: false,
      supports_attachments: false,
      supported_attachment_types: [],
    })
    expect(
      getMessengerCapabilities({
        capabilities: {
          can_start_conversation: false,
          requires_inbound: true,
          requires_phone: false,
          supports_attachments: true,
          supported_attachment_types: ['image', 'file'],
        },
      }),
    ).toEqual({
      can_start_conversation: false,
      requires_inbound: true,
      requires_phone: false,
      supports_attachments: true,
      supported_attachment_types: ['image', 'file'],
    })
  })
})
