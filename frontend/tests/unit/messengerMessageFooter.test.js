import { createApp } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/utils', () => ({
  formatDate: (value, format) => (format === 'HH:mm' ? '20:04' : value),
}))

vi.mock('frappe-ui', () => ({
  Button: { template: '<button><slot /></button>' },
  Textarea: { template: '<textarea />' },
  Tooltip: {
    props: ['text'],
    template: '<span data-test-tooltip :title="text"><slot /></span>',
  },
}))

import MessageContent from '@/components/LeadMessenger/MessageContent.vue'
import MessageFooterMetadata from '@/components/LeadMessenger/MessageFooterMetadata.vue'

let mounted = []

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
})

function mountComponent(component, props) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(component, props)
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return root
}

function message(overrides = {}) {
  return {
    name: 'MSG-1',
    text: 'Исправленный текст',
    message_datetime: '2026-07-19 20:04:00',
    direction: 'inbound',
    status: 'sent',
    is_edited: 1,
    ...overrides,
  }
}

function footerOrder(root) {
  return [
    ...root.querySelectorAll(
      '[data-message-edited], [data-message-time], [data-message-delivery]',
    ),
  ].map((element) =>
    element.hasAttribute('data-message-edited')
      ? 'edited'
      : element.hasAttribute('data-message-time')
        ? 'time'
        : 'delivery',
  )
}

describe('message footer metadata', () => {
  it('renders edited before time for inbound messages without delivery status', () => {
    let root = mountComponent(MessageFooterMetadata, {
      message: message(),
    })
    let footer = root.querySelector('[data-message-footer]')

    expect(footerOrder(root)).toEqual(['edited', 'time'])
    expect(footer.textContent).toContain('ред.')
    expect(footer.textContent).toContain('20:04')
    expect(root.querySelector('[data-message-delivery]')).toBeNull()
    expect(footer.className).toContain('whitespace-nowrap')
    expect(footer.className).not.toContain('flex-wrap')
  })

  it('renders edited, time and read status in strict outbound order', () => {
    let root = mountComponent(MessageFooterMetadata, {
      message: message({ direction: 'outbound', status: 'read' }),
    })

    expect(footerOrder(root)).toEqual(['edited', 'time', 'delivery'])
    expect(root.querySelector('[data-message-delivery]').className).toContain(
      'text-ink-blue-2',
    )
  })

  it('hides the edited marker for unedited and deleted messages', () => {
    let unedited = mountComponent(MessageFooterMetadata, {
      message: message({ is_edited: 0 }),
    })
    let deleted = mountComponent(MessageFooterMetadata, {
      message: message({ status: 'deleted' }),
    })

    expect(unedited.querySelector('[data-message-edited]')).toBeNull()
    expect(deleted.querySelector('[data-message-edited]')).toBeNull()
  })

  it('does not render the old edited label in message content', () => {
    let root = mountComponent(MessageContent, {
      message: message(),
      shouldShowText: true,
    })

    expect(root.textContent).toContain('Исправленный текст')
    expect(root.textContent).not.toContain('изменено')
    expect(
      root.querySelector('[class*="overflow-wrap:anywhere"]'),
    ).not.toBeNull()
  })
})
