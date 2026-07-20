<template>
  <component
    :is="action ? 'a' : 'div'"
    :href="action || undefined"
    :target="action ? '_blank' : undefined"
    :rel="action ? 'noopener noreferrer' : undefined"
    class="flex min-w-0 max-w-sm items-center gap-3 rounded-lg border border-outline-gray-1 bg-surface-white p-3 no-underline"
    :class="action ? 'hover:bg-surface-gray-1' : ''"
  >
    <div
      v-if="attachment.type === 'video' && attachment.preview_url"
      class="relative h-16 w-24 shrink-0 overflow-hidden rounded bg-surface-gray-2"
    >
      <img :src="attachment.preview_url" class="size-full object-cover" />
      <PlayIcon class="absolute inset-0 m-auto size-7 text-white drop-shadow" />
    </div>
    <div
      v-else
      class="flex size-10 shrink-0 items-center justify-center rounded bg-surface-gray-2 text-ink-gray-6"
    >
      <LoadingIndicator v-if="state.busy" class="size-5" />
      <component :is="cardIcon" v-else class="size-5" />
    </div>
    <div class="min-w-0 flex-1">
      <div class="truncate text-sm font-medium text-ink-gray-8">
        {{ title }}
      </div>
      <div
        class="mt-0.5 flex flex-wrap gap-x-2 text-xs"
        :class="state.failed ? 'text-ink-red-4' : 'text-ink-gray-5'"
      >
        <span v-if="size">{{ size }}</span>
        <span>{{ __(state.label) }}</span>
      </div>
    </div>
    <ExternalLinkIcon v-if="action" class="size-4 shrink-0 text-ink-gray-5" />
  </component>
</template>

<script setup>
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import {
  formatAttachmentSize,
  getAttachmentAction,
  getAttachmentState,
} from '@/utils/messengerAttachments'
import { computed } from 'vue'
import CircleHelpIcon from '~icons/lucide/circle-help'
import ExternalLinkIcon from '~icons/lucide/external-link'
import FileIcon from '~icons/lucide/file'
import LinkIcon from '~icons/lucide/link'
import PlayIcon from '~icons/lucide/play'
import StickerIcon from '~icons/lucide/sticker'
import VideoIcon from '~icons/lucide/video'

const props = defineProps({
  attachment: { type: Object, required: true },
  icon: { type: String, default: '' },
})
const state = computed(() => getAttachmentState(props.attachment))
const action = computed(() => getAttachmentAction(props.attachment))
const size = computed(() => formatAttachmentSize(props.attachment.size_bytes))
const title = computed(
  () =>
    props.attachment.title ||
    props.attachment.file_name ||
    props.attachment.fallback_text ||
    fallbackTitle(props.attachment.type),
)
const cardIcon = computed(() => {
  if (props.icon === 'sticker') return StickerIcon
  if (props.attachment.type === 'link') return LinkIcon
  if (props.attachment.type === 'video') return VideoIcon
  if (props.attachment.type === 'unsupported') return CircleHelpIcon
  return FileIcon
})

function fallbackTitle(type) {
  if (type === 'video') return __('Видео')
  if (type === 'link') return __('Ссылка')
  if (type === 'sticker') return __('Стикер')
  if (type === 'unsupported') return __('Неподдерживаемое вложение')
  return __('Файл')
}
</script>
