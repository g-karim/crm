// Real message renderers and production Tailwind CSS; no site or provider I/O.
import { createApp, h, reactive } from 'vue'
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
  getMessengerPlatformLabel,
  shouldShowMessengerText,
} from '@/utils/messengerChannels'
import { isStickerOnlyForwardContext } from '@/utils/messengerForwarding'
import { createMessengerSyncController } from '@/utils/messengerSync'
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
const sizingBindings = {
  ...attachments,
  isStickerOnlyForwardContext,
}
function productionFunction(name) {
  const policy = conversationSource.match(
    new RegExp(`^function ${name}\\([\\s\\S]*?^\\}`, 'm'),
  )[0]
  return new Function(...Object.keys(sizingBindings), `return (${policy})`)(
    ...Object.values(sizingBindings),
  )
}
const bubbleWidth = productionFunction('messageBubbleWidthClass')
const surfacePolicy = conversationSource.match(
  /:class="\[\s*([\s\S]*?),\s*messageBubbleWidthClass\(/,
)[1]
const bubbleSurface = new Function('item', `return (${surfacePolicy})`)
const metadataPolicy = conversationSource.match(
  /:constrain-intrinsic-width="([^"]+)"/,
)[1]
const constrainMetadata = new Function(
  ...Object.keys(sizingBindings),
  `return (item) => (${metadataPolicy})`,
)(...Object.values(sizingBindings))
const picture = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="380" height="380"><rect width="380" height="380" fill="#334155"/><rect x="24" y="30" width="332" height="28" fill="#64748b"/><rect x="24" y="80" width="240" height="18" fill="#94a3b8"/><rect x="24" y="120" width="300" height="200" fill="#475569"/></svg>')}`
const portraitPicture = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="900"><rect width="100" height="900" fill="#334155"/></svg>')}`
const transparentWebpPicture =
  'data:image/webp;base64,UklGRjwAAABXRUJQVlA4TC8AAAAv/8F/EA8wgmM0tEMb8FDUtpE0wx/0vK5dAo7o/wQE//f1ffIf//Ef//Ef/x25PQA='
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
const params = new URLSearchParams(location.search)
const wazzupMedia = params.has('wazzupMedia')
const platform = params.get('platform') || 'whatsapp'
const provider =
  params.get('provider') || (wazzupMedia ? 'wazzup' : 'vk_direct')
const direction =
  new URLSearchParams(location.search).get('direction') || 'outbound'
const longLabels = new URLSearchParams(location.search).has('longLabels')
const contentOnly = new URLSearchParams(location.search).get('case')
const wazzupCases = [
  {
    key: 'portrait-image',
    attachments: [
      image('PORTRAIT', { url: portraitPicture, width: null, height: null }),
    ],
  },
  {
    key: 'document',
    text: 'Договор.pdf',
    text_is_attachment_filename: true,
    display_text: 'Договор.pdf',
    attachments: [{ ...file('Договор.pdf'), display_title: 'Файл' }],
  },
  {
    key: 'document-caption',
    text: 'Реальная подпись '.repeat(12),
    attachments: [file('Договор.pdf')],
  },
  {
    key: 'opaque-file',
    attachments: [
      {
        ...file(),
        display_title: '0123456789abcdef0123456789abcdef.pdf',
        file_name: '0123456789abcdef0123456789abcdef.pdf',
      },
    ],
  },
  {
    key: 'saved-document-download',
    attachments: [
      {
        ...file('0123456789abcdef0123456789abcdef01234567'),
        id: 'SAVED-DOCUMENT',
        status: 'available',
        display_title: 'Исходный договор.docx',
        mime_type:
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        url: '/api/method/crm_messenger.api.attachments.stream?attachment=SAVED-DOCUMENT',
        download_url:
          '/api/method/crm_messenger.api.attachments.download?attachment=SAVED-DOCUMENT',
      },
    ],
  },
  {
    key: 'opus-voice',
    attachments: [
      {
        id: 'OPUS',
        type: 'audio',
        status: 'available',
        is_voice: true,
        mime_type: 'audio/ogg',
        waveform: Array.from({ length: 64 }, (_, i) => (i % 8) * 12 + 8),
        duration_ms: 1000,
        url: '/tests/browser/fixtures/messenger-voice.ogg',
      },
    ],
  },
  {
    key: 'portrait-video',
    attachments: [
      {
        id: 'VIDEO',
        type: 'video',
        status: 'available',
        mime_type: 'video/mp4',
        video_source: 'local_file',
        width: 160,
        height: 240,
        duration_ms: 1000,
        playback_url: '/tests/browser/fixtures/messenger-portrait.mp4',
        preview_url: picture,
      },
    ],
  },
  {
    key: 'image-sticker',
    attachments: [
      image('STICKER', { type: 'sticker', mime_type: 'image/png' }),
    ],
  },
  {
    key: 'image-sticker-webp',
    attachments: [
      image('STICKER-WEBP', {
        type: 'sticker',
        mime_type: 'image/webp',
      }),
    ],
  },
  {
    key: 'animated-image-sticker',
    attachments: [
      image('ANIMATED-STICKER', {
        type: 'sticker',
        mime_type: 'image/gif',
        is_animated: true,
        url: '/tests/browser/fixtures/messenger-animation.gif',
        width: 512,
        height: 512,
      }),
    ],
  },
  {
    key: 'video-sticker',
    attachments: [
      {
        id: 'VIDEO-STICKER',
        type: 'sticker',
        status: 'available',
        mime_type: 'video/mp4',
        is_animated: true,
        playback_url: '/tests/browser/fixtures/messenger-portrait.mp4',
        width: 512,
        height: 512,
      },
    ],
  },
  {
    key: 'transparent-webp-artwork',
    attachments: [
      image('WEBP-ARTWORK', {
        url: transparentWebpPicture,
        width: 512,
        height: 512,
        mime_type: 'image/webp',
        is_sticker_candidate: true,
      }),
    ],
  },
  {
    key: 'image-sticker-pending',
    attachments: [
      image('STICKER-PENDING', {
        type: 'sticker',
        status: 'pending',
        url: null,
        width: null,
        height: null,
        mime_type: 'image/webp',
      }),
    ],
  },
  {
    key: 'gif',
    attachments: [
      image('GIF', {
        mime_type: 'image/gif',
        is_animated: true,
        url: '/tests/browser/fixtures/messenger-animation.gif',
        width: 48,
        height: 48,
      }),
    ],
  },
  {
    key: 'tgs',
    attachments: [
      {
        id: 'TGS',
        type: 'sticker',
        status: 'available',
        mime_type: 'application/json',
        is_animated: true,
        url: '/tests/browser/fixtures/messenger-sticker.json',
      },
    ],
  },
  {
    key: 'failed-file',
    attachments: [
      {
        ...file('Документ.pdf'),
        status: 'failed',
        download_url: null,
        error: 'https://secret.invalid/private?token=hidden',
      },
    ],
  },
  {
    key: 'unsupported-file',
    attachments: [
      {
        id: 'UNSUPPORTED',
        type: 'unsupported',
        status: 'unsupported',
        error: 'private response body',
      },
    ],
  },
]
const messages = reactive(
  (wazzupMedia ? wazzupCases : cases)
    .filter((item) => !contentOnly || item.key === contentOnly)
    .map((item) =>
      params.has('shortReply') && item.key === 'long-reply'
        ? { ...item, text: 'Ответ', reply_context: reply('Изображение') }
        : item,
    )
    .map((item) => ({
      name: item.key,
      provider,
      channel_info: {
        platform,
        api_mode: 'partner_api_v2',
        label: wazzupMedia
          ? params.get('channelLabel') ||
            (platform === 'telegram'
              ? 'Telegram Personal Test 2'
              : 'WhatsApp Live Test 2')
          : undefined,
      },
      direction,
      status: 'sent',
      can_reply: true,
      can_delete: true,
      can_edit: true,
      message_datetime: '2026-10-12 19:14:00',
      attachments: [],
      text: '',
      creation: '2026-10-12 19:14:00.123456',
      modified: '2026-10-12 19:14:01.000001',
      ...item,
    })),
)
let storedMessages = JSON.parse(JSON.stringify(messages))
let fixtureRevision = 1
const sync = createMessengerSyncController({
  call: async (method) => ({
    contract_version: 1,
    sync_cursor: `fixture-${fixtureRevision}`,
    next_cursor: `fixture-${fixtureRevision}`,
    has_more: false,
    page: { has_more: false },
    [method.endsWith('get_message_changes') ? 'changes' : 'messages']:
      JSON.parse(JSON.stringify(storedMessages)),
  }),
  onChange: (state) => messages.splice(0, messages.length, ...state.messages),
})
if (wazzupMedia) {
  window.messengerMediaFixture = {
    async delta(status = 'available') {
      fixtureRevision += 1
      storedMessages = storedMessages.map((message) => ({
        ...message,
        modified: `2026-10-12 19:14:01.${String(fixtureRevision).padStart(6, '0')}`,
        attachments: message.attachments.map((attachment) =>
          ['failed-file', 'unsupported-file', 'image-sticker-pending'].includes(
            message.key,
          )
            ? attachment
            : { ...attachment, status },
        ),
      }))
      await sync.syncDelta()
    },
    refresh: () => sync.loadSnapshot(),
  }
  await sync.start('SYNTHETIC-LEAD')
}
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
                  class: `${bubbleClasses} ${bubbleWidth(message)} ${bubbleSurface({ message })}`,
                },
                [
                  h(MessageMetadata, {
                    message,
                    sender: longLabels
                      ? 'AdministratorWithAnUnusuallyLongName'.repeat(2)
                      : 'Administrator',
                    source: longLabels
                      ? 'VeryLongProviderChannelName'.repeat(3)
                      : wazzupMedia
                        ? getMessengerPlatformLabel(message.channel_info)
                        : 'VK - Test 1',
                    failed: getMessengerDeliveryState(message) === 'failed',
                    constrainIntrinsicWidth: constrainMetadata({ message }),
                    wrapSource: attachments.isSingleStickerAttachmentSet(
                      message.attachments,
                    ),
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
if (wazzupMedia)
  app.provide('refreshMessengerAttachments', () => sync.loadSnapshot())
app.mount('#app')
