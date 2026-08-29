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
  getMessengerConversationNotice,
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

  it('prefers the effective server channel label', () => {
    expect(
      getMessengerPlatformLabel({
        platform: 'telegram',
        label: 'Telegram - EXP Bot',
      }),
    ).toBe('Telegram - EXP Bot')
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

  it('keeps effective labels and disambiguates duplicates', () => {
    expect(
      buildMessengerChannelOptions([
        { name: 'ch-1', platform: 'vk', label: 'VK - EXP' },
        { name: 'ch-2', platform: 'vk', label: 'VK - EXP' },
        { name: 'ch-3', platform: 'vk', label: 'Продажи' },
      ]),
    ).toEqual([
      { label: 'VK - EXP', value: 'ch-1' },
      { label: 'VK - EXP 2', value: 'ch-2' },
      { label: 'Продажи', value: 'ch-3' },
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
    ).toBe('sent')
    expect(
      getMessengerDeliveryState({
        direction: 'outbound',
        status: 'received',
        delivery_status: 'read',
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

  it.each(['sent', 'delivered', 'read', 'failed'])(
    'uses canonical delivery_status for %s',
    (deliveryStatus) => {
      expect(
        getMessengerDeliveryState({
          direction: 'outbound',
          status: 'received',
          delivery_status: deliveryStatus,
        }),
      ).toBe(deliveryStatus)
    },
  )

  it('shows text only for content or a deleted placeholder', () => {
    expect(shouldShowMessengerText({ text: null })).toBe(false)
    expect(shouldShowMessengerText({ text: '   ' })).toBe(false)
    expect(shouldShowMessengerText({ text: 'caption' })).toBe(true)
    expect(shouldShowMessengerText({ status: 'deleted', text: null })).toBe(
      true,
    )
  })

  it('returns delivery labels', () => {
    expect(
      getMessengerDeliveryLabel({
        direction: 'outbound',
        delivery_status: 'failed',
      }),
    ).toBe('Ошибка')

    expect(
      getMessengerDeliveryLabel({
        provider: 'telegram_bot',
        direction: 'outbound',
        status: 'sent',
        read_at: null,
      }),
    ).toBe('Отправлено в Telegram; статус прочтения недоступен')

    expect(
      getMessengerDeliveryLabel({
        provider: 'max_direct',
        direction: 'outbound',
        status: 'retrying',
        provider_status: 'attachment.not.ready',
        message_type: 'video',
      }),
    ).toBe('MAX обрабатывает видео')
  })

  it('describes MAX lifecycle states without affecting other providers', () => {
    expect(
      getMessengerConversationNotice({
        provider: 'max_direct',
        provider_state: 'removed',
      }),
    ).toMatchObject({ type: 'warning', blocksSend: true })
    expect(
      getMessengerConversationNotice({
        provider: 'max_direct',
        provider_history_cleared_at: '2026-07-30 18:00:00',
      }),
    ).toMatchObject({ type: 'info', blocksSend: false })
    expect(getMessengerConversationNotice({ provider: 'vk_direct' })).toEqual({
      type: '',
      message: '',
      blocksSend: false,
    })
  })

  it('reads provider capabilities with safe defaults', () => {
    expect(getMessengerCapabilities({})).toEqual({
      can_start_conversation: true,
      requires_inbound: false,
      requires_phone: false,
      supports_attachments: false,
      supported_attachment_types: [],
      max_attachment_count: 10,
      reactions: { receive: false, send: false },
      location: { receive: false, send: false },
      contact: { receive: false, send: false },
      typing: { receive: false, send: false },
      voice: {
        send: false,
        max_duration_seconds: 300,
        max_size_bytes: 10485760,
      },
      video: {
        receive: false,
        download: false,
        inline_playback: false,
        embed: false,
        native_send: false,
        send_fallback: '',
      },
    })
    expect(
      getMessengerCapabilities({
        capabilities: {
          can_start_conversation: false,
          requires_inbound: true,
          requires_phone: false,
          supports_attachments: true,
          supported_attachment_types: ['image', 'file'],
          reactions: { receive: true, send: true },
          location: { receive: true, send: true },
          contact: { receive: true, send: false },
          typing: { receive: true, send: true },
          voice: {
            send: true,
            max_duration_seconds: 120,
            max_size_bytes: 2048,
          },
          video: { receive: true, embed: true, send_fallback: 'document' },
        },
      }),
    ).toEqual({
      can_start_conversation: false,
      requires_inbound: true,
      requires_phone: false,
      supports_attachments: true,
      supported_attachment_types: ['image', 'file'],
      max_attachment_count: 10,
      reactions: { receive: true, send: true },
      location: { receive: true, send: true },
      contact: { receive: true, send: false },
      typing: { receive: true, send: true },
      voice: {
        send: true,
        max_duration_seconds: 120,
        max_size_bytes: 2048,
      },
      video: {
        receive: true,
        download: false,
        inline_playback: false,
        embed: true,
        native_send: false,
        send_fallback: 'document',
      },
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

  it('groups only adjacent MAX forward-only messages within five seconds', () => {
    let forward = (name, time, overrides = {}) => ({
      name,
      provider: 'max_direct',
      conversation: 'MAX-CONVERSATION',
      direction: 'inbound',
      sender_name: 'MAX Клиент',
      status: 'received',
      message_datetime: time,
      text: null,
      attachments: [],
      forward_context: { version: 1, items: [{ key: `${name}-forward` }] },
      ...overrides,
    })
    let first = forward('MAX-1', '2026-07-16 08:00:00')
    let second = forward('MAX-2', '2026-07-16 08:00:05')
    let tooLate = forward('MAX-3', '2026-07-16 08:00:11')
    let ordinary = {
      ...forward('MAX-TEXT', '2026-07-16 08:00:12'),
      text: 'Обычное сообщение',
      forward_context: null,
    }
    let afterBreak = forward('MAX-4', '2026-07-16 08:00:13')

    let items = buildMessengerMessageItems(
      [first, second, tooLate, ordinary, afterBreak],
      '2026-07-16 09:00:00',
    )

    expect(items).toHaveLength(4)
    expect(items[0].messages).toEqual([first, second])
    expect(items[0].message).toBe(second)
    expect(items.slice(1).map((item) => item.messages.length)).toEqual([
      1, 1, 1,
    ])
  })

  it('caps one visual MAX forwarding group at twenty provider messages', () => {
    let messages = Array.from({ length: 21 }, (_, index) => ({
      name: `MAX-${index}`,
      provider: 'max_direct',
      conversation: 'MAX-CONVERSATION',
      direction: 'inbound',
      sender_name: 'MAX Клиент',
      status: 'received',
      message_datetime: `2026-07-16 08:00:${String(index).padStart(2, '0')}`,
      attachments: [],
      forward_context: { items: [{ key: `forward-${index}` }] },
    }))

    let items = buildMessengerMessageItems(messages, '2026-07-16 09:00:00')
    expect(items.map((item) => item.messages.length)).toEqual([20, 1])
  })

  it('does not group MAX forwards across sender, direction, or day boundaries', () => {
    let base = {
      provider: 'max_direct',
      conversation: 'MAX-CONVERSATION',
      direction: 'inbound',
      sender_name: 'Первый клиент',
      status: 'received',
      attachments: [],
      forward_context: { items: [{ key: 'forward' }] },
    }
    let messages = [
      { ...base, name: 'MAX-1', message_datetime: '2026-07-16 08:00:00' },
      {
        ...base,
        name: 'MAX-2',
        sender_name: 'Другой клиент',
        message_datetime: '2026-07-16 08:00:01',
      },
      {
        ...base,
        name: 'MAX-3',
        direction: 'outbound',
        message_datetime: '2026-07-16 08:00:02',
      },
      { ...base, name: 'MAX-4', message_datetime: '2026-07-16 20:59:59' },
      { ...base, name: 'MAX-5', message_datetime: '2026-07-16 21:00:01' },
    ]

    expect(
      buildMessengerMessageItems(messages, '2026-07-16 09:00:00').map(
        (item) => item.messages.length,
      ),
    ).toEqual([1, 1, 1, 1, 1])
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
