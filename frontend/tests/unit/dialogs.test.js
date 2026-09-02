import { createApp, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('frappe-ui', () => ({
  Button: {
    props: ['label'],
    template: '<button>{{ label }}</button>',
  },
  Dialog: {
    props: ['actions', 'open'],
    template:
      '<section v-if="open"><slot /><slot name="actions" :actions="actions" /></section>',
  },
  ErrorMessage: { template: '<span />' },
}))

import { createDialog, Dialogs } from '@/utils/dialogs'

let app
let host

afterEach(() => {
  app?.unmount()
  host?.remove()
})

describe('global dialogs', () => {
  it('wraps long action labels instead of overflowing the dialog', async () => {
    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(Dialogs)
    app.mount(host)

    createDialog({
      title: 'Check sending conversation',
      actions: [
        { label: 'Send through MAX - EXP Test Bot' },
        { label: 'Switch to VK - Test 1' },
        { label: 'Cancel' },
      ],
    })
    await new Promise((resolve) => setTimeout(resolve, 0))
    await nextTick()

    let actions = host.querySelector('[data-testid="dialog-actions"]')
    expect(actions).not.toBeNull()
    expect(actions.classList).toContain('flex-col')
    expect(actions.classList).toContain('sm:flex-wrap')
    expect(
      [...actions.querySelectorAll('button')].map(
        (button) => button.textContent,
      ),
    ).toEqual([
      'Send through MAX - EXP Test Bot',
      'Switch to VK - Test 1',
      'Cancel',
    ])
    expect(
      [...actions.querySelectorAll('button')].every((button) =>
        button.classList.contains('w-full'),
      ),
    ).toBe(true)
  })
})
