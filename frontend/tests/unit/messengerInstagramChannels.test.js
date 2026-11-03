import { describe, expect, it, vi } from 'vitest'
import {
  buildMessengerChannelOptions,
  getMessengerCapabilities,
  getMessengerChannelType,
  getMessengerPlatformLabel,
} from '@/utils/messengerChannels'
import {
  messengerConversationOption,
  resolveMessengerConversationSelection,
  resolveMessengerHandoffAction,
} from '@/utils/messengerRouting'

vi.mock('frappe-ui', () => ({ dayjsLocal: vi.fn() }))

describe('existing Instagram channels in shared Messenger', () => {
  it.each(['platform', 'channel_type', 'chat_type'])(
    'preserves Instagram from %s',
    (field) => {
      expect(getMessengerChannelType({ [field]: ' Instagram ' })).toBe(
        'instagram',
      )
      expect(getMessengerPlatformLabel({ [field]: 'instagram' })).toBe(
        'Instagram',
      )
    },
  )

  it('reads the platform from a conversation channel DTO', () => {
    expect(
      getMessengerChannelType({
        provider: 'wazzup',
        channel_info: { platform: 'instagram' },
      }),
    ).toBe('instagram')
    expect(
      messengerConversationOption({
        name: 'IG-CHAT',
        channel: 'IG-CHANNEL',
        provider: 'wazzup',
        channel_info: { platform: 'instagram' },
      }).label,
    ).toBe('Instagram Direct · IG-CHANNEL · IG-CHAT')
  })

  it('keeps named Instagram channels distinct without changing the platform', () => {
    expect(
      buildMessengerChannelOptions([
        { name: 'IG-A', platform: 'instagram', label: 'Sales Instagram' },
        { name: 'IG-B', platform: 'instagram', label: 'Sales Instagram' },
      ]),
    ).toEqual([
      { label: 'Sales Instagram', value: 'IG-A' },
      { label: 'Sales Instagram 2', value: 'IG-B' },
    ])
  })

  it('selects an existing opaque-ID Instagram dialog through shared routing', () => {
    const conversations = [
      { name: 'IG-CHAT', channel: 'IG-A', external_chat_id: '000opaque:IG' },
      { name: 'IG-OTHER', channel: 'IG-B', external_chat_id: '000opaque:IG' },
    ]
    expect(
      resolveMessengerConversationSelection({
        conversations,
        channel: 'IG-A',
      }).conversation?.name,
    ).toBe('IG-CHAT')
    expect(resolveMessengerHandoffAction(conversations, 'IG-A')).toMatchObject({
      state: 'switch',
      conversation: { name: 'IG-CHAT' },
    })
    expect(conversations[0].external_chat_id).toBe('000opaque:IG')
  })

  it('uses conservative Instagram defaults for a partial channel DTO', () => {
    expect(getMessengerCapabilities({ platform: 'instagram' })).toMatchObject({
      can_start_conversation: false,
      requires_inbound: true,
      requires_phone: false,
      supports_attachments: true,
      supported_attachment_types: ['image'],
      supported_attachment_file_types_by_type: {
        image: ['.jpg', '.jpeg', '.png', '.bmp'],
      },
      supports_image_caption: false,
      supports_attachment_captions: false,
      max_attachment_count: 1,
      max_attachment_size_bytes: 8_000_000,
      max_attachment_size_bytes_by_type: { image: 8_000_000 },
      max_text_length: 1000,
      voice: { send: false },
      location: { send: false },
      contact: { send: false },
    })
  })

  it('retains stricter backend limits and disabled attachments', () => {
    expect(
      getMessengerCapabilities({
        platform: 'instagram',
        capabilities: {
          supports_attachments: false,
          supported_attachment_types: [],
          supported_attachment_file_types_by_type: { image: ['.png'] },
          max_attachment_size_bytes: 2_000_000,
          max_attachment_size_bytes_by_type: { image: 1_000_000 },
          max_text_length: 500,
        },
      }),
    ).toMatchObject({
      supports_attachments: false,
      supported_attachment_types: [],
      supported_attachment_file_types_by_type: { image: ['.png'] },
      max_attachment_size_bytes: 2_000_000,
      max_attachment_size_bytes_by_type: { image: 1_000_000 },
      max_text_length: 500,
    })
  })

  it('does not broaden Direct restrictions when a DTO is too permissive', () => {
    expect(
      getMessengerCapabilities({
        platform: 'instagram',
        capabilities: {
          can_start_conversation: true,
          requires_phone: true,
          supported_attachment_types: ['image', 'file', 'audio', 'video'],
          supported_attachment_file_types_by_type: {
            image: ['.png', '.gif', '.webp', '.svg'],
          },
          max_attachment_size_bytes: 50_000_000,
          max_attachment_size_bytes_by_type: { image: 50_000_000 },
          max_text_length: 4096,
          voice: { send: true },
          location: { send: true },
        },
      }),
    ).toMatchObject({
      can_start_conversation: false,
      requires_phone: false,
      supported_attachment_types: ['image'],
      supported_attachment_file_types_by_type: { image: ['.png'] },
      max_attachment_size_bytes: 8_000_000,
      max_attachment_size_bytes_by_type: { image: 8_000_000 },
      max_text_length: 1000,
      voice: { send: false },
      location: { send: false },
    })
  })

  it.each([
    { supported_attachment_types: [] },
    { supported_attachment_types: ['file'] },
    { supported_attachment_file_types_by_type: { image: [] } },
    { supported_attachment_file_types_by_type: { image: ['.gif'] } },
  ])(
    'disables uploads when the backend allows no supported images: %j',
    (capabilities) => {
      expect(
        getMessengerCapabilities({ platform: 'instagram', capabilities })
          .supports_attachments,
      ).toBe(false)
    },
  )

  it.each(['whatsapp', 'telegram', 'max', 'viber'])(
    'leaves %s capabilities controlled by the existing backend DTO',
    (platform) => {
      expect(
        getMessengerCapabilities({
          platform,
          capabilities: {
            can_start_conversation: true,
            requires_phone: true,
            supports_attachments: true,
            supported_attachment_types: ['image', 'file', 'audio', 'video'],
            max_attachment_size_bytes: 10_000_000,
          },
        }),
      ).toMatchObject({
        can_start_conversation: true,
        requires_inbound: false,
        requires_phone: true,
        supported_attachment_types: ['image', 'file', 'audio', 'video'],
        max_attachment_size_bytes: 10_000_000,
        max_text_length: 0,
      })
    },
  )
})
