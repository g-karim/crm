import { createApp } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('frappe-ui', () => ({
  Badge: {
    props: ['label'],
    template: '<span data-test-badge>{{ label }}</span>',
  },
  Button: {
    inheritAttrs: false,
    template: '<button data-test-action-button v-bind="$attrs"></button>',
  },
  Dropdown: {
    inheritAttrs: false,
    props: ['options'],
    template:
      '<div data-test-action-menu v-bind="$attrs"><slot /></div>',
  },
}))

import MessageMetadata from '@/components/LeadMessenger/MessageMetadata.vue'

let mounted = []

afterEach(() => {
  mounted.forEach(({ app, root }) => {
    app.unmount()
    root.remove()
  })
  mounted = []
})

function mountMetadata(overrides = {}) {
  let root = document.createElement('div')
  document.body.appendChild(root)
  let app = createApp(MessageMetadata, {
    message: {
      name: 'MSG-SHORT',
      text: 'Ок',
      can_edit: true,
      can_delete: true,
    },
    sender: 'Вы',
    source: 'VK',
    ...overrides,
  })
  app.config.globalProperties.__ = globalThis.__
  app.mount(root)
  mounted.push({ app, root })
  return root
}

describe('message metadata layout', () => {
  it('reserves a separate flex slot for actions on a short message', () => {
    let root = mountMetadata()
    let metadata = root.querySelector('[data-message-metadata]')
    let labels = root.querySelector('[data-message-labels]')
    let actions = root.querySelector('[data-message-actions]')
    let button = root.querySelector('[data-test-action-button]')

    expect(metadata.children[0]).toBe(labels)
    expect(metadata.children[1]).toBe(actions)
    expect(metadata.className).toContain('justify-between')
    expect(labels.className).toContain('flex-wrap')
    expect(labels.className).toContain('min-w-0')
    expect(actions.className).toContain('shrink-0')
    expect(button.className).not.toContain('absolute')
    expect(button.className).not.toMatch(/-top|-right/)
    expect(button.className).toContain('hover:opacity-100')
    expect(root.textContent).toContain('VK')
  })

	it('keeps long platform badges wrapping without an action overlap', () => {
    let root = mountMetadata({ source: 'WhatsApp Business' })
    expect(root.querySelector('[data-message-labels]').className).toContain(
      'flex-wrap',
    )
    expect(root.querySelector('[data-message-actions]')).not.toBeNull()
		expect(root.textContent).toContain('WhatsApp Business')
	})

	it('shows the existing edit action for a backend-eligible photo message', () => {
		let root = mountMetadata({
			message: {
				name: 'MSG-PHOTO',
				text: 'Подпись',
				message_type: 'image',
				attachments: [{ id: 'ATT-1', type: 'image' }],
				can_edit: true,
				can_delete: true,
			},
		})

		expect(root.querySelector('[data-test-action-menu]')).not.toBeNull()
		expect(root.querySelector('[data-message-actions]')).not.toBeNull()
	})

  it('does not reserve an empty action slot for inbound messages', () => {
    let root = mountMetadata({
      sender: 'Клиент',
      message: {
        name: 'MSG-INBOUND',
        text: 'Входящее',
        can_edit: false,
        can_delete: false,
      },
    })
    expect(root.querySelector('[data-message-actions]')).toBeNull()
    expect(root.querySelector('[data-message-labels]')).not.toBeNull()
  })
})
