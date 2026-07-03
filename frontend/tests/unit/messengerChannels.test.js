import {
  buildMessengerChannelOptions,
  getMessengerChannelType,
  getMessengerPlatformLabel,
} from '@/utils/messengerChannels'

describe('messengerChannels', () => {
  it('normalizes known platform labels', () => {
    expect(
      getMessengerPlatformLabel({
        channel_type: 'avito',
        display_name: 'Avito Test',
      }),
    ).toBe('Avito')
    expect(
      getMessengerPlatformLabel({
        channel_type: 'whatsapp',
        display_name: 'WhatsApp Test',
      }),
    ).toBe('WhatsApp')
  })

  it('falls back to display name for unknown channel types', () => {
    expect(
      getMessengerPlatformLabel({
        channel_type: 'other',
        display_name: 'Custom Channel',
      }),
    ).toBe('Custom Channel')
  })

  it('reads channel type from channel_type or chat_type', () => {
    expect(getMessengerChannelType({ channel_type: 'avito' })).toBe('avito')
    expect(getMessengerChannelType({ chat_type: 'whatsapp' })).toBe('whatsapp')
  })

  it('builds unique select labels without technical names', () => {
    expect(
      buildMessengerChannelOptions([
        { name: 'ch-1', channel_type: 'avito', display_name: 'Avito Test' },
        {
          name: 'ch-2',
          channel_type: 'avito',
          display_name: 'Avito Production',
        },
        {
          name: 'ch-3',
          channel_type: 'whatsapp',
          display_name: 'WhatsApp Test',
        },
      ]),
    ).toEqual([
      { label: 'Avito', value: 'ch-1' },
      { label: 'Avito 2', value: 'ch-2' },
      { label: 'WhatsApp', value: 'ch-3' },
    ])
  })
})
