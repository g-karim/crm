import MessageContent from '@/components/LeadMessenger/MessageContent.vue'
import { getProviderExternalChatUrl } from '@/utils/messengerExternalLinks'
import {
  getMessengerMessageTextPresentation,
  shouldShowMessengerMessageText,
} from '@/utils/messengerMessagePresentation'
import { createApp } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('frappe-ui', () => ({
  Button: { template: '<button />' },
  Textarea: { template: '<textarea />' },
}))

let mounted = []

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
})

function mountMessage(message) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(MessageContent, {
    message,
    shouldShowText: shouldShowMessengerMessageText(message),
  })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return root
}

describe('messenger message presentation', () => {
  it('hides an image placeholder while its attachment is still loading', () => {
    let message = {
      message_type: 'image',
      text: '[image]',
      attachments: [{ type: 'image', status: 'pending', url: '' }],
    }

    expect(getMessengerMessageTextPresentation(message).text).toBe('')
    expect(mountMessage(message).textContent).not.toContain('[image]')
  })

  it('hides the image placeholder for every media state but keeps literal text', () => {
    let imageMessage = {
      message_type: 'image',
      text: '[image]',
      attachments: [{ type: 'image', status: 'failed', url: '' }],
    }

    expect(getMessengerMessageTextPresentation(imageMessage).text).toBe('')
    expect(
      getMessengerMessageTextPresentation({
        ...imageMessage,
        text: 'real caption',
      }).text,
    ).toBe('real caption')
    expect(
      getMessengerMessageTextPresentation({
        message_type: 'text',
        text: '[image]',
        attachments: [],
      }).text,
    ).toBe('[image]')
  })

  it('hides the Avito voice identifier while leaving the player label separate', () => {
    let message = {
      provider: 'avito_direct',
      message_type: 'audio',
      text: 'Голосовое сообщение: 36fd96c6-9a87-4f7e-a581-3fcad31bc723',
      attachments: [{ type: 'audio', is_voice: true }],
    }

    let root = mountMessage(message)

    expect(root.textContent).not.toContain('36fd96c6')
    expect(shouldShowMessengerMessageText(message)).toBe(false)
  })

  it('renders a graceful Avito video placeholder without inventing media', () => {
    let message = {
      provider: 'avito_direct',
      message_type: 'video',
      text: '[video]',
      attachments: [],
      external_chat_id: 'Avito~Chat_ID-123456789012',
    }

    let root = mountMessage(message)

    expect(root.textContent).toContain(
      'Video is unavailable through the Avito API.',
    )
    expect(root.textContent).not.toContain('[video]')
    expect(message.attachments).toEqual([])
    let action = root.querySelector('[data-provider-chat-action]')
    expect(action.textContent).toContain('Open chat in Avito')
    expect(action.href).toBe(
      'https://www.avito.ru/profile/messenger/channel/Avito~Chat_ID-123456789012',
    )
    expect(action.target).toBe('_blank')
    expect(action.rel).toBe('noopener noreferrer')
  })

  it('validates Avito chat IDs and falls back without embedding unsafe input', () => {
    expect(
      getProviderExternalChatUrl('avito_direct', 'Avito~Chat_ID-123456789012'),
    ).toBe(
      'https://www.avito.ru/profile/messenger/channel/Avito~Chat_ID-123456789012',
    )
    expect(
      getProviderExternalChatUrl('avito_direct', '../unsafe/chat?id=1'),
    ).toBe('https://www.avito.ru/profile/messenger')
    expect(getProviderExternalChatUrl('vk_direct', '123')).toBe('')
  })

  it('does not rewrite technical-looking text for other providers', () => {
    expect(
      getMessengerMessageTextPresentation({
        provider: 'vk_direct',
        message_type: 'video',
        text: '[video]',
        attachments: [],
      }).text,
    ).toBe('[video]')
  })
})
