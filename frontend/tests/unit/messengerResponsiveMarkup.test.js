import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const conversationSource = readFileSync(
  resolve(process.cwd(), 'src/components/LeadMessenger/LeadConversation.vue'),
  'utf8',
)
const composerAttachmentsSource = readFileSync(
  resolve(
    process.cwd(),
    'src/components/LeadMessenger/ComposerAttachments.vue',
  ),
  'utf8',
)
const desktopNotificationsSource = readFileSync(
  resolve(process.cwd(), 'src/components/Notifications.vue'),
  'utf8',
)
const mobileNotificationsSource = readFileSync(
  resolve(process.cwd(), 'src/pages/MobileNotification.vue'),
  'utf8',
)

describe('messenger responsive markup', () => {
  it('applies reply highlighting to the bubble instead of the full row', () => {
    let rowStart = conversationSource.indexOf(
      ':data-message-id="item.message.name"',
    )
    let bubbleStart = conversationSource.indexOf(
      'data-message-bubble',
      rowStart,
    )
    let bubbleEnd = conversationSource.indexOf('@contextmenu', bubbleStart)

    expect(rowStart).toBeGreaterThan(-1)
    expect(bubbleStart).toBeGreaterThan(rowStart)
    expect(conversationSource.slice(rowStart, bubbleStart)).not.toContain(
      'ring-2',
    )
    expect(conversationSource.slice(bubbleStart, bubbleEnd)).toContain('ring-2')
  })

  it('allows the composer controls to wrap on narrow screens', () => {
    expect(conversationSource).toContain(
      'class="flex flex-wrap items-center justify-between gap-3"',
    )
    expect(conversationSource).toContain(
      'class="ml-auto flex flex-wrap items-center justify-end gap-2"',
    )
  })

  it('keeps direct and forwarded sticker bubbles at their media widths', () => {
    expect(conversationSource).toContain(
      "return 'w-[14.5rem] !max-w-[94%] sm:!max-w-[14.5rem]'",
    )
    expect(conversationSource).toContain(
      "return 'w-64 !max-w-[94%] sm:!max-w-64'",
    )
  })

  it('keeps upload progress visible with the current semantic palette', () => {
    expect(composerAttachmentsSource).toContain('bg-surface-blue-7')
    expect(composerAttachmentsSource).not.toContain('bg-surface-blue-3')
  })

  it('lets long notification previews shrink and wrap on every layout', () => {
    for (let source of [
      desktopNotificationsSource,
      mobileNotificationsSource,
    ]) {
      expect(source).toContain('<div class="min-w-0 flex-1">')
      expect(source).toContain('class="[overflow-wrap:anywhere]"')
    }
  })

  it('gates every mutation surface with backend operator permissions', () => {
    expect(conversationSource).toContain('v-if="permissions.can_operate"')
    expect(conversationSource).toContain("{{ __('Только чтение') }}")
    expect(conversationSource).toContain(
      "__('Для этого лида пока нет доступных сообщений.')",
    )
    expect(conversationSource).toContain(
      ':can-send="Boolean(item.message.can_react)"',
    )
    expect(conversationSource).toContain(
      "reference_doctype: 'CRM Lead',\n      reference_name: props.leadName",
    )
    expect(conversationSource).toContain('voiceRecorder.value?.reset?.()')
    expect(conversationSource).toContain('locationPickerOpen.value = false')
    expect(conversationSource).toContain('onPermissions: applyPermissions')
  })
})
