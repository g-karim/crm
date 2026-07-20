<template>
  <video
    v-if="inline"
    :src="attachment.url"
    class="max-h-[22rem] w-full max-w-[28rem] rounded-lg bg-black object-contain"
    controls
    preload="metadata"
    playsinline
  />
  <a
    v-else-if="attachment.preview_url && action"
    :href="action"
    target="_blank"
    rel="noopener noreferrer"
    class="group relative block max-h-[22rem] w-full max-w-[28rem] overflow-hidden rounded-lg bg-surface-gray-2"
  >
    <img
      :src="attachment.preview_url"
      :alt="attachment.title || __('Видеосообщение')"
      class="max-h-[22rem] w-full object-contain"
    />
    <span class="absolute inset-0 flex items-center justify-center bg-black/15 transition-colors group-hover:bg-black/25">
      <span class="flex size-11 items-center justify-center rounded-full bg-black/65 text-white">
        <PlayIcon class="size-6" />
      </span>
    </span>
  </a>
  <AttachmentCard v-else :attachment="attachment" />
</template>

<script setup>
import {
  canRenderInlineVideo,
  getAttachmentAction,
} from '@/utils/messengerAttachments'
import { computed } from 'vue'
import PlayIcon from '~icons/lucide/play'
import AttachmentCard from './AttachmentCard.vue'

const props = defineProps({ attachment: { type: Object, required: true } })
const inline = computed(() => canRenderInlineVideo(props.attachment))
const action = computed(() => getAttachmentAction(props.attachment))
</script>
