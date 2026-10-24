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
  it.each(['whatsapp', 'telegram'])(
    'keeps %s filenames separate from actual captions across canonical DTO updates',
    (platform) => {
      let message = {
        provider: 'wazzup',
        channel_info: { platform, api_mode: 'partner_api_v2' },
        message_type: 'file',
        text: null,
        display_text: 'Договор.pdf',
        attachments: [
          {
            id: 'FILE',
            type: 'file',
            status: 'pending',
            file_name: 'Договор.pdf',
          },
        ],
      }
      for (let status of ['pending', 'available', 'failed', 'unsupported']) {
        let dto = {
          ...message,
          attachments: [{ ...message.attachments[0], status }],
        }
        expect(shouldShowMessengerMessageText(dto)).toBe(false)
        expect(mountMessage(dto).textContent.trim()).toBe('')
      }
      // Even text equal to a filename is retained when it is real message text.
      expect(
        mountMessage({ ...message, text: 'Договор.pdf' }).textContent.trim(),
      ).toBe('Договор.pdf')
      expect(
        mountMessage({
          ...message,
          text: 'Подпись к документу',
        }).textContent.trim(),
      ).toBe('Подпись к документу')
    },
  )
  it.each([
    'wazzup',
    'telegram_bot',
    'vk_direct',
    'max_direct',
    'avito_direct',
  ])(
    'shows unavailable content for existing empty %s messages without changing them',
    (provider) => {
      let message = {
        provider,
        message_type: 'text',
        text: '   ',
        attachments: [],
      }
      let original = structuredClone(message)
      expect(getMessengerMessageTextPresentation(message)).toEqual({
        text: 'Content unavailable',
        translate: true,
      })
      expect(mountMessage(message).textContent).toContain('Content unavailable')
      expect(message).toEqual(original)
    },
  )

  it.each(['pending', 'available', 'failed', 'unsupported'])(
    'keeps attachment-only %s messages free of a redundant unavailable-content label',
    (status) => {
      let message = {
        provider: 'wazzup',
        message_type: 'image',
        text: '',
        attachments: [{ type: 'image', status }],
      }
      expect(shouldShowMessengerMessageText(message)).toBe(false)
      expect(mountMessage(message).textContent).not.toContain(
        'Content unavailable',
      )
    },
  )

  it('keeps forward-only messages free of an unavailable-content label', () => {
    let message = {
      provider: 'max_direct',
      text: '',
      forward_context: { items: [{ text: 'Forwarded' }] },
    }
    expect(shouldShowMessengerMessageText(message)).toBe(false)
  })

  it('renders supplied template values and inert button labels without inventing its body', () => {
    let message = {
      provider: 'wazzup',
      message_type: 'other',
      text: null,
      template_context: {
        values: ['<b>Parameter</b>'],
        buttons: [{ text: '<script>Button</script>' }],
      },
    }
    let root = mountMessage(message)
    expect(root.querySelector('[data-message-template]')).not.toBeNull()
    expect(root.textContent).toContain('Template message')
    expect(root.textContent).toContain(
      'The provider did not include the template text.',
    )
    expect(root.textContent).toContain('<b>Parameter</b>')
    expect(root.textContent).toContain('<script>Button</script>')
    expect(root.textContent).not.toContain('Content unavailable')
    expect(root.querySelector('script, b, button')).toBeNull()
    expect(
      mountMessage({ ...message, status: 'deleted' }).querySelector(
        '[data-message-template]',
      ),
    ).toBeNull()
  })

  it('renders normalized Wazzup incoming text literally in the native chat', () => {
    let message = {
      provider: 'wazzup',
      direction: 'inbound',
      message_type: 'text',
      text: 'Здравствуйте\n<b>Уточню заказ</b> [image]',
      attachments: [],
    }

    let root = mountMessage(message)

    expect(root.textContent.trim()).toBe(message.text)
    expect(root.querySelector('b')).toBeNull()
    expect(root.querySelector('[data-provider-chat-action]')).toBeNull()
  })

  it.each([
    'avito_direct',
    'telegram_bot',
    'vk_direct',
    'max_direct',
    'wazzup',
  ])('renders safe message and caption URLs for %s', (provider) => {
    let url = 'https://example.com/каталог?item=1&src=chat#заказ'
    let message = {
      provider,
      message_type: 'image',
      text: `Подпись\nСсылка: ${url}`,
      attachments: [{ type: 'image', url: '/private/image.png' }],
    }

    let root = mountMessage(message)
    let text = root.querySelector('[data-message-text]')
    let link = text.querySelector('a')

    expect(text.textContent).toBe(message.text)
    expect(link.textContent).toBe(url)
    expect(link.getAttribute('href')).toBe(url)
    expect(link.target).toBe('_blank')
    expect(link.rel).toBe('noopener noreferrer')
  })

  it('escapes HTML and attribute injection while rendering safe links', () => {
    let message = {
      message_type: 'text',
      text: '<img src=x onerror=alert(1)> <script>alert(1)</script> javascript:alert(1) data:text/html,x https://example.com/?q="onmouseover=alert(1)"',
    }
    let root = mountMessage(message)
    let text = root.querySelector('[data-message-text]')

    expect(text.textContent).toBe(message.text)
    expect(root.querySelector('img, script')).toBeNull()
    expect(root.querySelectorAll('a')).toHaveLength(1)
    expect(root.querySelector('a').hasAttribute('onmouseover')).toBe(false)
    expect(root.querySelector('a').protocol).toBe('https:')
  })

  it('does not show a deleted message URL or attachment placeholder', () => {
    let root = mountMessage({
      status: 'deleted',
      message_type: 'text',
      text: 'https://example.com/deleted',
    })

    expect(root.textContent.trim()).toBe('Message deleted')
    expect(root.querySelector('a')).toBeNull()
  })

  it('opening a message URL does not select the surrounding chat bubble', () => {
    let root = mountMessage({
      message_type: 'text',
      text: 'https://example.com/',
    })
    let selectMessage = vi.fn()
    root.addEventListener('click', selectMessage)

    root
      .querySelector('a')
      .dispatchEvent(new MouseEvent('click', { bubbles: true }))

    expect(selectMessage).not.toHaveBeenCalled()
  })

  it('keeps the native link context menu without opening the parent reaction picker', () => {
    let root = mountMessage({
      provider: 'vk_direct',
      can_react: true,
      message_type: 'text',
      text: 'https://example.com/',
    })
    let openReactionPicker = vi.fn((event) => event.preventDefault())
    root.addEventListener('contextmenu', openReactionPicker)
    let event = new MouseEvent('contextmenu', {
      bubbles: true,
      cancelable: true,
    })

    expect(root.querySelector('a').dispatchEvent(event)).toBe(true)
    expect(openReactionPicker).not.toHaveBeenCalled()
    expect(event.defaultPrevented).toBe(false)
  })

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
