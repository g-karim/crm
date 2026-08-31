<template>
  <button
    type="button"
    data-message-reply-quote
    class="block w-full min-w-0 rounded border-l-2 border-outline-blue-3 bg-surface-gray-2 px-2 py-1 text-left"
    :disabled="!clickable"
    @click="$emit('navigate', context?.message)"
  >
    <div class="truncate text-xs font-medium text-ink-gray-6">
      {{ title }}
    </div>
    <div
      class="line-clamp-2 whitespace-pre-wrap break-words text-sm text-ink-gray-8"
    >
      {{ body }}
    </div>
  </button>
</template>

<script setup>
import { getMessengerReplyAttachmentLabel } from '@/utils/messengerAttachments'
import { computed } from 'vue'

const props = defineProps({
  context: { type: Object, default: null },
  clientName: { type: String, default: '' },
})

defineEmits(['navigate'])

const clickable = computed(
  () => props.context?.state === 'available' && Boolean(props.context?.message),
)
const title = computed(() => {
  if (props.context?.state === 'deleted') return __('Message deleted')
  if (props.context?.state === 'unavailable') return __('Message not loaded')
  let snapshot = props.context?.snapshot || {}
  let clientName = /^-?\d{5,}$/.test(props.clientName.trim())
    ? null
    : props.clientName.trim()
  if (snapshot.direction === 'inbound' && clientName) return clientName
  let senderName = /^-?\d{5,}$/.test(String(snapshot.sender_name || '').trim())
    ? null
    : snapshot.sender_name
  if (senderName === 'You') return __('You')
  if (senderName === 'Client') return __('Client')
  return (
    senderName || (snapshot.direction === 'outbound' ? __('You') : __('Client'))
  )
})
const body = computed(() => {
  if (props.context?.state === 'deleted') return __('Message deleted')
  let snapshot = props.context?.snapshot || {}
  if (snapshot.text) return snapshot.text
  if (snapshot.forwarded_content_kind === 'message') {
    return __('Forwarded message')
  }
  let attachmentLabel = getMessengerReplyAttachmentLabel(snapshot)
  if (attachmentLabel) return __(attachmentLabel)
  if (snapshot.forwarded_content_kind === 'attachment') return __('Attachment')
  return __('Original message unavailable')
})
</script>
