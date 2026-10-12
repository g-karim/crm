// Real message renderers and production Tailwind CSS; no site or provider I/O.
import { createApp, h } from 'vue'
import conversationSource from '@/components/LeadMessenger/LeadConversation.vue?raw'
import AttachmentRenderer from '@/components/LeadMessenger/AttachmentRenderer.vue'
import MessageContent from '@/components/LeadMessenger/MessageContent.vue'
import MessageMetadata from '@/components/LeadMessenger/MessageMetadata.vue'
import MessageReplyQuote from '@/components/LeadMessenger/MessageReplyQuote.vue'
import MessageForwardStack from '@/components/LeadMessenger/MessageForwardStack.vue'
import MessageFooterMetadata from '@/components/LeadMessenger/MessageFooterMetadata.vue'
import * as attachments from '@/utils/messengerAttachments'
import {
  getMessengerDeliveryState,
  getMessengerFailureReason,
  shouldShowMessengerText,
} from '@/utils/messengerChannels'
import { isStickerOnlyForwardContext } from '@/utils/messengerForwarding'
import '@/index.css'

globalThis.__ = (message, args = []) =>
  args.reduce(
    (text, value, index) => text.replace(`{${index}}`, value),
    message,
  )
window.timezone = { system: 'UTC' }

// Read the actual bubble classes and sizing policy instead of copying CSS or
// maintaining a second implementation that can pass while production breaks.
const bubbleClasses = conversationSource.match(
  /data-message-bubble\s+class="([^"]+)"/,
)[1]
const widthPolicy = conversationSource.match(
  /^function messageBubbleWidthClass\(message\) \{[\s\S]*?^\}/m,
)[0]
const sizingBindings = { ...attachments, isStickerOnlyForwardContext }
const bubbleWidth = new Function(
  ...Object.keys(sizingBindings),
  `return (${widthPolicy})`,
)(...Object.values(sizingBindings))
const metadataPolicy = conversationSource.match(
  /:constrain-intrinsic-width="([^"]+)"/,
)[1]
const constrainMetadata = new Function('item', `return (${metadataPolicy})`)
const picture = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="380" height="380"><rect width="380" height="380" fill="#334155"/><rect x="24" y="30" width="332" height="28" fill="#64748b"/><rect x="24" y="80" width="240" height="18" fill="#94a3b8"/><rect x="24" y="120" width="300" height="200" fill="#475569"/></svg>')}`
const file = (
  title = 'ТПР-1-23_Хайруллин_Ильназ_Документ_с_длинным_названием_для_проверки.pdf',
) => ({
  id: 'FILE-1',
  type: 'file',
  status: 'uploaded',
  file_name: title,
  display_title: title,
  size_bytes: 1258291,
  download_url: '#download',
})
const image = (id, props = {}) => ({
  id,
  type: 'image',
  status: 'available',
  url: picture,
  width: 380,
  height: 380,
  ...props,
})
const reply = (text = 'Quoted message') => ({
  state: 'available',
  message: 'TARGET',
  snapshot: { direction: 'inbound', sender_name: 'Client', text },
})
const forward = (text) => ({
  version: 1,
  items: [
    {
      key: 'forward-1',
      relation: 'forward',
      sender_name: 'Client',
      message_datetime: '2026-10-12 12:00:00',
      text,
      attachments: [],
    },
  ],
})
const cases = [
  { key: 'file-images', attachments: [file(), image('I-1'), image('I-2')] },
  { key: 'images-file', attachments: [image('I-1'), image('I-2'), file()] },
  { key: 'file-only-long', attachments: [file()] },
  { key: 'file-only-short', attachments: [file('Проб.txt')] },
  { key: 'images-only', attachments: [image('I-1'), image('I-2')] },
  { key: 'single-image', attachments: [image('I-1')] },
  {
    key: 'tiny-image',
    attachments: [image('I-1', { width: 100, height: 70 })],
  },
  { key: 'portrait', attachments: [image('I-1', { width: 100, height: 900 })] },
  {
    key: 'landscape',
    attachments: [image('I-1', { width: 900, height: 100 })],
  },
  {
    key: 'sticker',
    attachments: [image('S-1', { type: 'sticker', mime_type: 'image/png' })],
  },
  {
    key: 'voice',
    attachments: [
      {
        id: 'VOICE-1',
        type: 'audio',
        is_voice: true,
        status: 'available',
        file_name: 'voice.ogg',
        duration_ms: 72000,
        mime_type: 'audio/ogg',
      },
    ],
  },
  {
    key: 'location',
    attachments: [
      {
        id: 'LOCATION-1',
        type: 'location',
        location: { latitude: 55.75, longitude: 37.61, title: 'Office' },
      },
    ],
  },
  {
    key: 'contact',
    attachments: [
      {
        id: 'CONTACT-1',
        type: 'contact',
        contact: {
          display_name: 'ContactWithAnUnusuallyLongName'.repeat(3),
          phones: ['+79990000000'],
        },
      },
    ],
  },
  {
    key: 'animation',
    attachments: [
      image('ANIMATION-1', { is_animated: true, mime_type: 'image/gif' }),
    ],
  },
  {
    key: 'video',
    attachments: [
      {
        id: 'VIDEO-1',
        type: 'video',
        status: 'available',
        file_name: 'video.mp4',
        mime_type: 'video/mp4',
        playback_url: picture,
        preview_url: picture,
        video_source: 'local_file',
        width: 380,
        height: 380,
      },
    ],
  },
  {
    key: 'three-images',
    attachments: [image('I-1'), image('I-2'), image('I-3')],
  },
  {
    key: 'caption-file-images',
    text: 'Short caption',
    attachments: [file(), image('I-1'), image('I-2')],
  },
  {
    key: 'long-caption-file',
    text: 'https://example.com/' + 'long-path'.repeat(36),
    attachments: [file()],
  },
  {
    key: 'file-long-reply',
    attachments: [file('Проб.txt')],
    reply_context: reply('https://example.com/' + 'long-path'.repeat(45)),
  },
  {
    key: 'long-reply',
    text: 'OK',
    reply_context: reply('unbrokenword'.repeat(50)),
  },
  {
    key: 'forward-file',
    forward_context: {
      version: 1,
      items: [
        {
          key: 'file',
          relation: 'forward',
          sender_name: 'Client',
          attachments: [file()],
        },
      ],
    },
  },
  {
    key: 'nested-forward',
    forward_context: {
      version: 1,
      items: [
        {
          key: 'parent',
          relation: 'forward',
          sender_name: 'Client',
          text: 'Parent',
          items: forward('unbrokenword'.repeat(50)).items,
          attachments: [],
        },
      ],
    },
  },
  {
    key: 'forward-sticker',
    forward_context: {
      version: 1,
      items: [
        {
          key: 'sticker',
          relation: 'forward',
          sender_name: 'Client',
          message_datetime: '2026-10-12 12:00:00',
          attachments: [
            image('S-1', { type: 'sticker', mime_type: 'image/png' }),
          ],
        },
      ],
    },
  },
  { key: 'short-text', text: 'OK' },
  { key: 'long-word', text: 'unbrokenword'.repeat(100) },
  {
    key: 'unknown-upload',
    attachments: [file(), image('I-1')],
    status: 'unknown',
    failure_reason:
      'VK image upload result is unknown. Automatic resend is disabled.',
  },
  {
    key: 'failed-upload',
    attachments: [file(), image('I-1', { status: 'failed' })],
    status: 'failed',
    failure_reason: 'Could not upload the image to VK. Try sending it again.',
  },
  { key: 'deleted', text: 'Hidden deleted text', status: 'deleted' },
]
const provider =
  new URLSearchParams(location.search).get('provider') || 'vk_direct'
const direction =
  new URLSearchParams(location.search).get('direction') || 'outbound'
const longLabels = new URLSearchParams(location.search).has('longLabels')
const contentOnly = new URLSearchParams(location.search).get('case')
const messages = cases
  .filter((item) => !contentOnly || item.key === contentOnly)
  .map((item) => ({
    name: item.key,
    provider,
    direction,
    status: 'sent',
    can_reply: true,
    can_delete: true,
    can_edit: true,
    message_datetime: '2026-10-12 19:14:00',
    attachments: [],
    text: '',
    ...item,
  }))
const app = createApp({
  render: () =>
    h(
      'main',
      {
        class: 'mx-auto w-full max-w-[840px] space-y-6 p-4',
        'data-bubble-fixture': '',
      },
      messages.map((message) =>
        h('section', { 'data-case': message.key }, [
          h('div', { class: 'mb-1 text-xs text-ink-gray-5' }, message.key),
          h(
            'div',
            {
              class: `flex ${direction === 'outbound' ? 'justify-end' : 'justify-start'}`,
            },
            [
              h(
                'div',
                {
                  'data-message-bubble': '',
                  class: `${bubbleClasses} ${bubbleWidth(message)} bg-surface-blue-1 text-ink-gray-9`,
                },
                [
                  h(MessageMetadata, {
                    message,
                    sender: longLabels
                      ? 'AdministratorWithAnUnusuallyLongName'.repeat(2)
                      : 'Administrator',
                    source: longLabels
                      ? 'VeryLongProviderChannelName'.repeat(3)
                      : 'VK - Test 1',
                    failed: getMessengerDeliveryState(message) === 'failed',
                    constrainIntrinsicWidth: constrainMetadata({ message }),
                  }),
                  message.reply_context &&
                    h(MessageReplyQuote, {
                      context: message.reply_context,
                      class: 'mb-2',
                    }),
                  message.forward_context &&
                    h(MessageForwardStack, {
                      context: message.forward_context,
                      provider,
                      class: 'mb-2',
                    }),
                  h(MessageContent, {
                    message,
                    shouldShowText: shouldShowMessengerText(message),
                  }),
                  message.status !== 'deleted' &&
                    h(AttachmentRenderer, {
                      attachments: message.attachments,
                      provider,
                      outbound: direction === 'outbound',
                    }),
                  h(MessageFooterMetadata, { message }),
                  getMessengerFailureReason(message) &&
                    h(
                      'div',
                      { class: 'mt-1 border-t pt-1 text-xs text-ink-red-8' },
                      getMessengerFailureReason(message),
                    ),
                ],
              ),
            ],
          ),
        ]),
      ),
    ),
})
app.config.globalProperties.__ = globalThis.__
app.mount('#app')
