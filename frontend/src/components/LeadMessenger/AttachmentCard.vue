<template>
  <component
    :is="cardAction ? 'a' : 'div'"
    :href="cardAction || undefined"
    :target="cardAction ? '_blank' : undefined"
    :rel="cardAction ? 'noopener noreferrer' : undefined"
    data-attachment-card
    class="flex w-full min-w-0 max-w-full items-center gap-3 rounded-lg border border-outline-gray-1 bg-surface-base p-3 no-underline"
    :class="
      cardAction
        ? 'hover:bg-surface-gray-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3'
        : ''
    "
  >
    <div
      v-if="attachment.type === 'video' && attachment.preview_url"
      class="relative h-16 w-24 shrink-0 overflow-hidden rounded bg-surface-gray-2"
    >
      <img
        :src="attachment.preview_url"
        alt=""
        class="size-full object-cover"
      />
      <PlayIcon class="absolute inset-0 m-auto size-7 text-white drop-shadow" />
    </div>
    <div
      v-else
      class="flex size-10 shrink-0 items-center justify-center rounded bg-surface-gray-2 text-ink-gray-6"
    >
      <LoadingIndicator v-if="state.busy && !waitingForUpdate" class="size-5" />
      <ClockIcon v-else-if="state.busy" class="size-5" />
      <component :is="cardIcon" v-else class="size-5" />
    </div>
    <div class="min-w-0 flex-1">
      <div
        data-attachment-card-title
        class="truncate text-sm font-medium text-ink-gray-8"
        :title="__(title)"
      >
        {{ __(title) }}
      </div>
      <div
        class="mt-0.5 flex flex-wrap gap-x-2 text-xs"
        :class="state.failed ? 'text-ink-red-8' : 'text-ink-gray-5'"
      >
        <span v-if="size">{{ size }}</span>
        <span>{{ __(state.label) }}</span>
      </div>
      <div
        v-if="refreshError"
        class="mt-1 text-xs text-ink-red-8"
        role="status"
      >
        {{ refreshError }}
      </div>
    </div>
    <Button
      v-if="canRefresh"
      :label="__('Refresh')"
      :disabled="refreshing"
      variant="outline"
      class="shrink-0"
      @click="refresh"
    />
    <ExternalLinkIcon
      v-else-if="cardAction && attachment.type !== 'file'"
      class="size-4 shrink-0 text-ink-gray-5"
    />
  </component>
</template>

<script setup>
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import {
  formatAttachmentSize,
  getMessengerAttachmentTitle,
  getAttachmentAction,
  getAttachmentState,
} from '@/utils/messengerAttachments'
import { Button } from 'frappe-ui'
import { computed, inject, onBeforeUnmount, ref, watch } from 'vue'
import CircleHelpIcon from '~icons/lucide/circle-help'
import ClockIcon from '~icons/lucide/clock-3'
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
const refreshAttachments = inject('refreshMessengerAttachments', null)
const canRefresh = computed(() =>
  Boolean(refreshAttachments && (state.value.busy || state.value.failed)),
)
const cardAction = computed(() => (canRefresh.value ? '' : action.value))
const waitingForUpdate = ref(false)
const refreshing = ref(false)
const refreshError = ref('')
let waitingTimer = null
const size = computed(() => formatAttachmentSize(props.attachment.size_bytes))
const title = computed(() => getMessengerAttachmentTitle(props.attachment))
const cardIcon = computed(() => {
  if (props.icon === 'sticker') return StickerIcon
  if (props.attachment.type === 'link') return LinkIcon
  if (props.attachment.type === 'video') return VideoIcon
  if (props.attachment.type === 'unsupported') return CircleHelpIcon
  return FileIcon
})

async function refresh() {
  if (!canRefresh.value || refreshing.value) return
  refreshing.value = true
  refreshError.value = ''
  try {
    await refreshAttachments()
  } catch {
    refreshError.value = __('Could not refresh messages.')
  } finally {
    refreshing.value = false
  }
}

watch(
  () => [props.attachment.id, state.value.status],
  () => {
    clearTimeout(waitingTimer)
    waitingForUpdate.value = false
    refreshError.value = ''
    if (state.value.busy) {
      waitingTimer = setTimeout(() => (waitingForUpdate.value = true), 30000)
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => clearTimeout(waitingTimer))
</script>
