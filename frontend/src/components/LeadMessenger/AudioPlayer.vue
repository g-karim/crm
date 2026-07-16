<template>
  <div class="min-w-56 rounded-lg border border-outline-gray-1 bg-surface-white p-3">
    <div class="mb-2 flex items-center justify-between gap-3 text-sm">
      <div class="flex min-w-0 items-center gap-2 font-medium text-ink-gray-8">
        <AudioLinesIcon class="size-4 shrink-0" />
        <span class="truncate">{{ title }}</span>
      </div>
      <span v-if="duration" class="shrink-0 text-xs text-ink-gray-5">
        {{ duration }}
      </span>
    </div>
    <audio
      v-if="attachment.url && state.active"
      class="h-9 w-full"
      controls
      preload="metadata"
      :src="attachment.url"
    />
    <div v-else class="flex items-center gap-2 text-sm text-ink-gray-5">
      <LoadingIndicator v-if="state.busy" class="size-4" />
      <CircleAlertIcon v-else class="size-4" />
      <span>{{ __(state.label) }}</span>
    </div>
  </div>
</template>

<script setup>
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import {
  formatAttachmentDuration,
  getAttachmentState,
} from '@/utils/messengerAttachments'
import { computed } from 'vue'
import AudioLinesIcon from '~icons/lucide/audio-lines'
import CircleAlertIcon from '~icons/lucide/circle-alert'

const props = defineProps({ attachment: { type: Object, required: true } })
const state = computed(() => getAttachmentState(props.attachment))
const duration = computed(() =>
  formatAttachmentDuration(props.attachment.duration_ms),
)
const title = computed(() =>
  props.attachment.is_voice
    ? __('Голосовое сообщение')
    : props.attachment.title || props.attachment.file_name || __('Аудио'),
)
</script>
