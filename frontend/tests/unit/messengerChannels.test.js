import dayjs from 'dayjs'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'
import {
  buildMessengerMessageItems,
  buildMessengerChannelOptions,
  getMessengerDateLabel,
  getMessengerDayKey,
  getMessengerChannelType,
  getMessengerDeliveryLabel,
  getMessengerDeliveryState,
  getMessengerCapabilities,
  getMessengerPlatformLabel,
  shouldShowMessengerText,
} from '@/utils/messengerChannels'

dayjs.extend(utc)
dayjs.extend(timezone)

vi.mock('frappe-ui', () => ({
  dayjsLocal(value) {
    if (!value) return dayjs().tz('Europe/Moscow')
    return dayjs.tz(value, 'UTC').tz('Europe/Moscow')
  },
}))

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
        direction: 'outbound',
        status: 'read',
        delivery_status: 'sent',
      }),
    ).toBe('read')
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

  it('shows text only for content or a deleted placeholder', () => {
    expect(shouldShowMessengerText({ text: null })).toBe(false)
    expect(shouldShowMessengerText({ text: '   ' })).toBe(false)
    expect(shouldShowMessengerText({ text: 'caption' })).toBe(true)
    expect(shouldShowMessengerText({ status: 'deleted', text: null })).toBe(true)
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

  it('adds one date separator for several messages on the same day', () => {
    let messages = [
      { name: 'message-1', message_datetime: '2026-07-16 07:00:00' },
      { name: 'message-2', message_datetime: '2026-07-16 08:00:00' },
    ]

    let items = buildMessengerMessageItems(messages, '2026-07-16 09:00:00')

    expect(items.map((item) => item.message)).toEqual(messages)
    expect(items.map((item) => item.dateLabel)).toEqual(['Сегодня', ''])
  })

  it('adds a new date separator when the next calendar day starts', () => {
    let items = buildMessengerMessageItems(
      [
        { name: 'message-1', message_datetime: '2026-07-15 18:00:00' },
        { name: 'message-2', message_datetime: '2026-07-16 07:00:00' },
      ],
      '2026-07-16 09:00:00',
    )

    expect(items.map((item) => item.dateLabel)).toEqual(['Вчера', 'Сегодня'])
  })

  it('formats today and yesterday labels', () => {
    let now = '2026-07-16 09:00:00'

    expect(getMessengerDateLabel('2026-07-16 08:00:00', now)).toBe('Сегодня')
    expect(getMessengerDateLabel('2026-07-15 08:00:00', now)).toBe('Вчера')
  })

  it('formats current-year dates without a year', () => {
    expect(
      getMessengerDateLabel('2026-07-15 08:00:00', '2026-08-01 09:00:00'),
    ).toBe('15 июля')
  })

  it('formats dates from another year with a year', () => {
    expect(
      getMessengerDateLabel('2025-07-15 08:00:00', '2026-07-16 09:00:00'),
    ).toBe('15 июля 2025')
  })

  it('uses the configured user timezone near midnight', () => {
    expect(getMessengerDayKey('2026-07-15 20:30:00')).toBe('2026-07-15')
    expect(getMessengerDayKey('2026-07-15 21:30:00')).toBe('2026-07-16')

    let items = buildMessengerMessageItems(
      [
        { name: 'message-1', message_datetime: '2026-07-15 20:30:00' },
        { name: 'message-2', message_datetime: '2026-07-15 21:30:00' },
      ],
      '2026-07-16 09:00:00',
    )

    expect(items.map((item) => item.dateLabel)).toEqual(['Вчера', 'Сегодня'])
  })

  it('handles an empty message list', () => {
    expect(buildMessengerMessageItems([])).toEqual([])
  })

  it('ignores missing or invalid message datetimes', () => {
    let messages = [
      { name: 'message-1' },
      { name: 'message-2', message_datetime: 'not-a-date' },
    ]

    expect(
      buildMessengerMessageItems(messages).map((item) => ({
        message: item.message,
        dayKey: item.dayKey,
        dateLabel: item.dateLabel,
      })),
    ).toEqual([
      { message: messages[0], dayKey: '', dateLabel: '' },
      { message: messages[1], dayKey: '', dateLabel: '' },
    ])
  })
})
