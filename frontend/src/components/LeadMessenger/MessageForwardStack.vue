<template>
  <div data-message-forward-stack class="w-fit max-w-full space-y-2">
    <div
      v-for="item in context?.items || []"
      :key="item.key"
      data-forward-item
      class="min-w-0 max-w-full rounded-md border-l-2 border-outline-blue-3 bg-surface-gray-2 px-2.5 py-2"
      :class="isStickerOnlyForwardItem(item) ? 'w-[14.5rem]' : 'w-[20rem]'"
    >
      <div
        class="mb-1 flex min-w-0 items-center gap-2 text-xs text-ink-gray-6"
        :class="isStickerOnlyForwardItem(item) ? 'flex-wrap' : ''"
      >
        <span class="shrink-0 font-medium">
          {{
            item.relation === 'reply'
              ? __('Original Message')
              : __('Forwarded Message')
          }}
        </span>
        <span v-if="formattedTime(item.message_datetime)" class="shrink-0">
          {{ formattedTime(item.message_datetime) }}
        </span>
      </div>
      <div
        v-if="item.sender_name"
        class="mb-1 truncate text-xs font-medium text-ink-gray-7"
      >
        {{ item.sender_name }}
      </div>
      <MessageForwardStack
        v-if="replyItems(item).length"
        class="mb-2"
        :context="{ version: 1, truncated: false, items: replyItems(item) }"
        :playback-scope="playbackScope"
        :provider="provider"
      />
      <div
        v-if="item.text"
        class="whitespace-pre-wrap break-words text-sm text-ink-gray-8 [overflow-wrap:anywhere]"
      >
        {{ item.text }}
      </div>
      <AttachmentRenderer
        v-if="item.attachments?.length"
        class="mt-2"
        :attachments="item.attachments"
        :playback-scope="`${playbackScope}:${item.key}`"
        :provider="provider"
        compact-preview
      />
      <div
        v-else-if="
          !item.text && !item.items?.length && item.attachment_types?.length
        "
        class="text-sm italic text-ink-gray-5"
      >
        {{ __('Attachment unavailable') }}
      </div>
      <MessageForwardStack
        v-if="forwardItems(item).length"
        class="mt-2"
        :context="{ version: 1, truncated: false, items: forwardItems(item) }"
        :playback-scope="playbackScope"
        :provider="provider"
      />
    </div>
    <div
      v-if="context?.truncated"
      data-forward-truncated
      class="text-xs italic text-ink-gray-5"
    >
      {{ __('Some forwarded messages are hidden') }}
    </div>
  </div>
</template>

<script setup>
import { isStickerOnlyForwardItem } from '@/utils/messengerForwarding'
import AttachmentRenderer from './AttachmentRenderer.vue'

defineProps({
  context: { type: Object, default: null },
  playbackScope: { type: String, default: '' },
  provider: { type: String, default: '' },
})

function formattedTime(value) {
  if (!value) return ''
  let match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
  return match
    ? `${match[3]}.${match[2]}.${match[1]} ${match[4]}:${match[5]}`
    : ''
}

function replyItems(item) {
  return (item.items || []).filter((child) => child.relation === 'reply')
}

function forwardItems(item) {
  return (item.items || []).filter((child) => child.relation !== 'reply')
}
</script>
